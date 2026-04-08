import base64
import json
import asyncio
import threading
import time
import requests
import os
import random
from collections import defaultdict

from loguru import logger
import websockets
from taobao_apis import TaobaoApis

from utils.taobao_utils import (
    generate_mid,
    generate_uuid,
    trans_cookies,
    generate_device_id,
    decrypt,
    get_session_cookies_str,
)
from message import Message, make_text, make_image


class taobaoLive:
    def __init__(self, cookies_str):
        self.base_url = "wss://wss-cntaobao.dingtalk.com/"
        self.cookies_str = cookies_str
        self.cookies = trans_cookies(cookies_str)

        if "unb" not in self.cookies:
            raise ValueError("cookies_str 缺少 unb，请确认复制的是完整淘宝登录 Cookie")
        if "_nk_" not in self.cookies:
            raise ValueError("cookies_str 缺少 _nk_，请确认复制的是完整淘宝登录 Cookie")
        if "_m_h5_tk" not in self.cookies:
            raise ValueError("cookies_str 缺少 _m_h5_tk，请确认复制的是完整淘宝登录 Cookie")

        self.myid = self.cookies["unb"]
        self.nk = self.cookies["_nk_"]
        self.device_id = generate_device_id(self.myid)
        self.taobao = TaobaoApis(self.cookies, self.device_id)
        self.ws = None

        # 百炼 / DashScope 兼容 OpenAI 接口配置
        self.llm_api_key = os.getenv("DASHSCOPE_API_KEY", "这里填入你百炼的api")
        self.llm_model = "qwen-turbo"
        self.llm_api_url = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"

        # 简单风控关键词
        self.risky_words = [
            "退款", "退货", "投诉", "发票", "物流", "快递",
            "售后", "赔偿", "差评", "举报", "平台介入"
        ]

        # 连续消息合并缓冲
        self.pending_messages = defaultdict(list)
        self.pending_tasks = {}
        self.merge_window = 5  # 5秒内连续消息合并

    async def your_ai_agent(self, user_text: str) -> str:
        if not self.llm_api_key:
            logger.error("未配置 DASHSCOPE_API_KEY")
            return "收到，你方便的话告诉我预算、口味，或者是自己喝还是送礼，我帮你缩小范围。"

        system_prompt = """
你是一个淘宝凤凰单丛茶客服助理。

回复要求：
1. 用中文回复
2. 口语化，像真人，不要机械
3. 尽量简短，优先控制在60字以内，最多不要超过100字
4. 不要乱承诺库存、发货时间、优惠、效果
5. 如果用户在问选茶，优先围绕“口味、预算、用途（自喝/送礼）”引导
6. 如果用户问价格差异，可以解释产区、海拔、树龄、工艺
7. 如果信息不足，就引导客户补充预算、口味或用途
8. 不要胡编细节，不确定就保守回答
9. 风格：专业、稳、不过度推销
10. 不要使用表情包，不要太啰嗦
"""

        def call_api():
            payload = {
                "model": self.llm_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_text}
                ],
                "temperature": 0.4,
                "max_tokens": 120
            }

            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.llm_api_key}"
            }

            resp = requests.post(
                self.llm_api_url,
                headers=headers,
                json=payload,
                timeout=40
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()

        try:
            logger.info(f"开始请求百炼 API, model={self.llm_model}")
            reply = await asyncio.to_thread(call_api)

            if not reply:
                return "收到，你方便的话告诉我预算、口味，或者是自己喝还是送礼，我帮你缩小范围。"

            reply = reply.replace("\n", " ").strip()
            if len(reply) > 100:
                reply = reply[:100].rstrip("，。；;,. ") + "。"

            return reply
        except Exception as e:
            logger.exception(f"百炼 API 调用失败: {e}")
            return "收到，你方便的话告诉我预算、口味，或者是自己喝还是送礼，我帮你缩小范围。"

    def safe_ack(self, message):
        ack = {
            "code": 200,
            "headers": {
                "mid": message["headers"]["mid"] if "mid" in message["headers"] else generate_mid(),
                "sid": message["headers"]["sid"] if "sid" in message["headers"] else "",
            },
        }
        if "app-key" in message["headers"]:
            ack["headers"]["app-key"] = message["headers"]["app-key"]
        if "ua" in message["headers"]:
            ack["headers"]["ua"] = message["headers"]["ua"]
        if "dt" in message["headers"]:
            ack["headers"]["dt"] = message["headers"]["dt"]
        return ack

    async def process_buffered_messages(self, session_key, websocket, cid, send_user_id):
        try:
            await asyncio.sleep(self.merge_window)

            messages = self.pending_messages.get(session_key, [])
            if not messages:
                return

            merged_text = " ".join(messages).strip()
            logger.info(f"合并后的消息: {merged_text}")

            # 先清空缓冲，避免重复处理
            self.pending_messages.pop(session_key, None)
            self.pending_tasks.pop(session_key, None)

            if any(word in merged_text for word in self.risky_words):
                reply = "收到，这个问题我先帮你看一下，你方便的话也可以再具体说一下情况，我再给你更准确的答复。"
                logger.info(f"命中敏感词，使用兜底回复: {reply}")
            else:
                logger.info(f"准备调用 AI，合并后消息: {merged_text}")
                reply = await self.your_ai_agent(merged_text)
                logger.info(f"AI 回复内容: {reply}")

            if not reply:
                reply = "收到，你方便的话告诉我预算、口味，或者是自己喝还是送礼，我帮你缩小范围。"

            reply = reply.replace("\n", " ").strip()
            if len(reply) > 100:
                reply = reply[:100].rstrip("，。；;,. ") + "。"

            # 随机延迟回复
            if len(merged_text) <= 5:
                delay = random.uniform(2, 3.5)
            elif len(merged_text) <= 20:
                delay = random.uniform(3, 5)
            else:
                delay = random.uniform(4, 7)

            logger.info(f"随机延迟 {delay:.2f} 秒后回复")
            await asyncio.sleep(delay)

            await self.send_msg(
                websocket,
                cid,
                send_user_id,
                f"cntaobao{self.nk}",
                make_text(reply)
            )
        except Exception as e:
            logger.exception(f"process_buffered_messages 处理失败: {e}")
            self.pending_messages.pop(session_key, None)
            self.pending_tasks.pop(session_key, None)

    async def list_all_conversations(self, cid):
        headers = {
            "Cookie": get_session_cookies_str(self.taobao.session),
            "Host": "wss-cntaobao.dingtalk.com",
            "Connection": "Upgrade",
            "Pragma": "no-cache",
            "Cache-Control": "no-cache",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
            "Origin": "https://www.cntaobao.com",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        async with websockets.connect(self.base_url, extra_headers=headers) as websocket:
            asyncio.create_task(self.init(websocket))
            send_mid = generate_mid()
            msg = {
                "lwp": "/r/MessageManager/listUserMessages",
                "headers": {
                    "mid": send_mid
                },
                "body": [
                    f"{cid}@cntaobao",
                    False,
                    9007199254740991,
                    20,
                    False
                ]
            }
            user_message_models = []
            async for raw_message in websocket:
                try:
                    message = json.loads(raw_message)
                    ack = self.safe_ack(message)
                    await websocket.send(json.dumps(ack))
                except Exception:
                    continue

                try:
                    if "lwp" in message and message["lwp"] == "/s/vulcan":
                        await websocket.send(json.dumps(msg))
                    recv_mid = message["headers"]["mid"] if "mid" in message["headers"] else ""
                    if recv_mid == send_mid:
                        logger.info(f"user history message: {message}")
                        has_more = message["body"]["hasMore"] == 1
                        next_cursor = message["body"]["nextCursor"]
                        for user_message in message["body"]["userMessageModels"]:
                            send_user_name = user_message["message"]["extension"]["sender_nick"]
                            send_user_id = user_message["message"]["sender"]["uid"]
                            send_message = None
                            if user_message["message"]["content"]["contentType"] == 1:
                                send_message = user_message["message"]["content"]
                            elif user_message["message"]["content"]["contentType"] == 101:
                                send_message = user_message["message"]["content"]["custom"]["data"]
                                send_message = base64.b64decode(send_message)
                            user_message_models.insert(0, {
                                "send_user_id": send_user_id,
                                "send_user_name": send_user_name,
                                "message": send_message
                            })
                        if has_more:
                            logger.info(f"has more history messages, next cursor: {next_cursor}")
                            send_mid = generate_mid()
                            msg["headers"]["mid"] = send_mid
                            msg["body"][2] = next_cursor
                            await websocket.send(json.dumps(msg))
                        else:
                            return user_message_models
                except Exception:
                    return user_message_models

    async def create_chat(self, ws, encrypt_uid):
        msg = {
            "lwp": "/r/SingleChatConversation/create",
            "headers": {
                "mid": generate_mid()
            },
            "body": [
                {
                    "pairFirst": f"{self.myid}@cntaobao",
                    "bizType": "11001",
                    "ctx": {
                        "createConversationCtx": '{"encryptUid":"' + encrypt_uid + '"}',
                        "selfBizDomain": "taobao"
                    }
                }
            ]
        }
        logger.info(f"create_chat => {json.dumps(msg, ensure_ascii=False)}")
        await ws.send(json.dumps(msg))

    async def send_msg(self, ws, cid, toid, sender_nick, message: Message):
        msg_type = message["type"]
        msg = {
            "lwp": "/r/MessageSend/sendByReceiverScope",
            "headers": {
                "mid": generate_mid()
            },
            "body": [
                {
                    "cid": cid,
                    "uuid": generate_uuid(),
                    "conversationType": 1,
                    "redPointPolicy": 0,
                    "extension": {
                        "senderBizDomain": "taobao",
                        "receiverBizDomain": "taobao",
                        "sender_nick": sender_nick
                    },
                    "content": {
                        "contentType": None,
                    },
                    "ctx": {
                        "senderBizDomain": "taobao",
                        "receiverBizDomain": "taobao"
                    }
                },
                {
                    "actualReceivers": [
                        f"{self.myid}@cntaobao",
                        f"{toid}@cntaobao",
                    ]
                }
            ]
        }

        if msg_type == "text":
            msg["body"][0]["content"]["contentType"] = 1
            msg["body"][0]["content"]["text"] = {
                "extension": {
                    "sender_nick": sender_nick
                },
                "content": message["text"]
            }
        elif msg_type == "image":
            del msg["body"][0]["extension"]["sender_nick"]
            data = {
                "fileId": message["file_id"],
                "size": message["size"],
                "url": message["image_url"],
                "width": message["width"],
                "height": message["height"],
                "isOriginal": 1,
                "suffix": "png"
            }
            msg["body"][0]["content"]["contentType"] = 101
            image_base64 = str(base64.b64encode(json.dumps(data).encode("utf-8")), "utf-8")
            msg["body"][0]["content"]["custom"] = {}
            msg["body"][0]["content"]["custom"]["type"] = 7
            msg["body"][0]["content"]["custom"]["data"] = image_base64
        elif msg_type == "audio":
            logger.error(f"不支持的消息类型: {msg_type}")
            return
        else:
            logger.error(f"不支持的消息类型: {msg_type}")
            return

        logger.info(f"准备发送消息给 {toid}, cid={cid}, type={msg_type}")
        await ws.send(json.dumps(msg))

    async def init(self, ws):
        data = self.taobao.get_token()
        token = (
            data["data"]["result"]["accessToken"]
            if "data" in data and "result" in data["data"] and "accessToken" in data["data"]["result"]
            else ""
        )
        if not token:
            logger.error("获取token失败")
            raise RuntimeError("获取token失败")

        msg = {
            "lwp": "/reg",
            "headers": {
                "cache-header": "app-key token ua wv",
                "app-key": "3ce2dacdc7c0c43ad7bc7f9bc7d7a1b8",
                "token": token,
                "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36 DingTalk(2.1.5) OS(Windows/10) Browser(Chrome/146.0.0.0) DingWeb/2.1.5 IMPaaS DingWeb/2.1.5",
                "dt": "j",
                "wv": "im:3,au:3,sy:6",
                "sync": "0,0;0;0;",
                "did": self.device_id,
                "mid": generate_mid()
            }
        }
        await ws.send(json.dumps(msg))

        current_time = int(time.time() * 1000)
        msg = {
            "lwp": "/r/SyncStatus/ackDiff",
            "headers": {"mid": generate_mid()},
            "body": [
                {
                    "pipeline": "sync",
                    "tooLong2Tag": "PNM,1",
                    "channel": "sync",
                    "topic": "sync",
                    "highPts": 0,
                    "pts": current_time * 1000,
                    "seq": 0,
                    "timestamp": current_time
                }
            ]
        }
        await ws.send(json.dumps(msg))
        logger.info("init")

    async def heart_beat(self, ws):
        while True:
            try:
                msg = {
                    "lwp": "/!",
                    "headers": {
                        "mid": generate_mid()
                    }
                }
                await ws.send(json.dumps(msg))
                await asyncio.sleep(15)
            except Exception as e:
                logger.warning(f"心跳发送失败: {e}")
                return

    def user_alive(self):
        while True:
            time.sleep(600)

    async def handle_message(self, message, websocket):
        try:
            if "body" not in message:
                return

            body = message.get("body")
            if not isinstance(body, dict):
                return

            sync_pkg = body.get("syncPushPackage")
            if not isinstance(sync_pkg, dict):
                return

            sync_data = sync_pkg.get("data")
            if not isinstance(sync_data, list) or not sync_data:
                return

            first_item = sync_data[0]
            if not isinstance(first_item, dict):
                return

            raw_data = first_item.get("data")
            if not raw_data:
                return

            # 先尝试直接 json 解析；一般这种不是聊天正文
            try:
                decoded_data = json.loads(raw_data)
                logger.info(f"无需解密 message: {decoded_data}")
                return
            except Exception:
                pass

            decrypted = decrypt(raw_data)
            message_obj = json.loads(decrypted)

            root = message_obj.get("1")
            if not isinstance(root, dict):
                logger.info(f"忽略非聊天结构消息: {message_obj}")
                return

            sender_wrap = root.get("1")
            sender_info = root.get("10")
            content_info = root.get("6")
            cid = root.get("2")

            if not isinstance(sender_wrap, dict):
                logger.info(f"忽略 sender_wrap 非 dict 消息: {message_obj}")
                return

            if not isinstance(sender_info, dict):
                logger.info(f"忽略 sender_info 非 dict 消息: {message_obj}")
                return

            if not isinstance(content_info, dict):
                logger.info(f"忽略 content_info 非 dict 消息: {message_obj}")
                return

            sender_full = sender_wrap.get("1")
            if not isinstance(sender_full, str) or "@" not in sender_full:
                logger.info(f"忽略 sender uid 非法消息: {message_obj}")
                return

            content_type = content_info.get("1")
            content_body = content_info.get("2")

            if content_type != 1:
                logger.info(f"忽略非文本消息, content_type={content_type}")
                return

            if not isinstance(content_body, dict):
                logger.info(f"忽略文本体非 dict 消息: {message_obj}")
                return

            send_message = content_body.get("1")
            send_user_name = sender_info.get("sender_nick")
            send_user_id = sender_full.split("@")[0]

            if not isinstance(send_message, str) or not send_message.strip():
                logger.info("空文本消息，忽略")
                return

            if not isinstance(send_user_name, str) or not send_user_name.strip():
                logger.info(f"缺少 sender_nick，忽略: {message_obj}")
                return

            if not isinstance(cid, str) or not cid.strip():
                logger.info(f"缺少 cid，忽略: {message_obj}")
                return

            if send_user_name == f"cntaobao{self.nk}":
                logger.info(f"这是自己发的消息，忽略 message: {message_obj}")
                return

            logger.info(f"user: {send_user_name}, send_user_id={send_user_id}, message={send_message}")

            ignore_phrases = [
                "稍等我下哦",
                "同一时间进线人数过多",
                "稍后我给您看好留言给您",
                "感谢您的咨询",
                "早付款早安排发货",
                "期待为您服务",
                "您好 看到了哦",
                "我在的呢",
                "小客服在的哦",
                "在的呢 宝宝~",
                "嗨宝宝，小客服在的哦"
            ]
            if any(p in send_message for p in ignore_phrases):
                logger.info(f"疑似客服模板话术，忽略: {send_message}")
                return

            session_key = f"{cid}:{send_user_id}"
            self.pending_messages[session_key].append(send_message)
            logger.info(f"已加入消息缓冲 session={session_key}, 当前条数={len(self.pending_messages[session_key])}")

            if session_key not in self.pending_tasks:
                self.pending_tasks[session_key] = asyncio.create_task(
                    self.process_buffered_messages(session_key, websocket, cid, send_user_id)
                )

        except Exception as e:
            logger.exception(f"handle_message 处理失败: {e}")

    async def main(self):
        headers = {
            "Cookie": get_session_cookies_str(self.taobao.session),
            "Host": "wss-cntaobao.dingtalk.com",
            "Connection": "Upgrade",
            "Pragma": "no-cache",
            "Cache-Control": "no-cache",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
            "Origin": "https://www.cntaobao.com",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }

        threading.Thread(target=self.user_alive, daemon=True).start()

        while True:
            try:
                logger.info("准备连接 WebSocket...")
                async with websockets.connect(
                    self.base_url,
                    extra_headers=headers,
                    ping_interval=20,
                    ping_timeout=20,
                    close_timeout=10,
                ) as websocket:
                    self.ws = websocket
                    logger.info("WebSocket 连接成功")

                    asyncio.create_task(self.init(websocket))
                    asyncio.create_task(self.heart_beat(websocket))

                    async for raw_message in websocket:
                        try:
                            message = json.loads(raw_message)
                        except Exception as e:
                            logger.warning(f"消息 JSON 解析失败: {e}, raw={raw_message}")
                            continue

                        try:
                            ack = self.safe_ack(message)
                            await websocket.send(json.dumps(ack))
                        except Exception as e:
                            logger.warning(f"ACK 发送失败: {e}")
                            continue

                        await self.handle_message(message, websocket)

            except Exception as e:
                logger.exception(f"WebSocket 断开，5秒后重连: {e}")
                await asyncio.sleep(5)


if __name__ == "__main__":
    cookies_str = r"这里改为你自己淘宝的cookie"
    # 示例：
    # cookies_str = r"unb=xxx; _nk_=xxx; _m_h5_tk=xxx; ..."

    # 建议先在系统里设置环境变量：
    # set DASHSCOPE_API_KEY=你的百炼APIKey

    tb_live = taobaoLive(cookies_str)
    asyncio.run(tb_live.main())
