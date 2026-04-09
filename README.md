# 🎁 TaobaoApis — 淘宝第三方 API 集成库，AI 客服智能体底座（fork 增强版）

[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/)
[![Node.js](https://img.shields.io/badge/node.js-18%2B-green)](https://nodejs.org/)
[![License](https://img.shields.io/badge/license-MIT-orange)](LICENSE)

> 在 AI 大模型爆发的时代，每一个淘宝卖家都值得拥有一个 7×24 小时不下线的智能客服。  
> 本项目封装了淘宝平台完整的消息通信能力，为开发者构建 AI 客服智能体提供可靠、稳定的底层 API 支撑。

⚠️ 严禁用于发布不良信息、违法内容！如有侵权请联系作者删除。

---

## 这个 fork 做了什么

这个仓库基于原项目继续做了两条可直接落地的自动回复方案：

1. 本地模型自动回复版
   - 适合本机部署 Ollama / 本地模型
   - 已加入基础风控、自动重连、随机延迟、连续消息合并

2. API 大模型自动回复版
   - 适合接阿里云百炼 / DashScope 等在线模型
   - 已加入基础风控、自动重连、随机延迟、连续消息合并

当前仓库里额外保留了两个可直接替换的运行文件：

- `taobao_live -taobao跑通本地自动回复文件（应用这个就改为taobao_live.py）.py`
- `taobao_live -taobao跑通大模型API自动回复文件（应用这个就改为taobao_live.py）.py`

如果你只是想快速跑起来，不需要自己从零改逻辑，直接选其中一个文件覆盖为 `taobao_live.py` 即可。

---

## 为什么需要这个项目？

```text
用户私信 ──► [TaobaoApis] ──► 你的 AI Agent（LLM / RAG / 规则引擎）──► 自动回复
               ▲                                                          │
               └──────────────── 发送消息 / 图片 ◄────────────────────────┘
```

淘宝官方没有开放 IM 消息接口。想要接入 GPT、Claude、本地大模型来做智能客服，首先需要能稳定收发消息。TaobaoApis 解决的正是这个前置问题：

- 逆向还原淘宝 WebSocket 私信协议（sign 签名 + base64 + Protobuf）
- 封装主要 HTTP 接口（sign 参数已解密）
- 提供统一的消息收发抽象层，开发者只需关注业务逻辑

你负责接 AI 大脑，这个项目负责打通淘宝的神经。

---

## 已实现功能

| 模块 | 功能 | 状态 |
|------|------|------|
| HTTP API | 淘宝 HTTP 接口封装（sign 签名已解密） | ✅ |
| WebSocket | 私信实时收发（sign + base64 + Protobuf 协议） | ✅ |
| 消息类型 | 文字、图片消息 | ✅ |
| 会话管理 | 获取历史聊天记录 | ✅ |
| 主动发送 | 主动向指定用户发消息 | ✅ |
| Token 维持 | 可常驻进程运行 | ✅ |
| 商品信息 | 获取商品详情 | ✅ |
| 媒体上传 | 上传图片并发送 | ✅ |
| 本地模型自动回复 | Ollama 本地模型接入 | ✅ |
| API 模型自动回复 | 百炼 / DashScope 接入 | ✅ |
| 连续消息合并 | 5 秒窗口内合并消息再回复 | ✅ |
| 随机延迟回复 | 随机 3-5 秒 / 4-7 秒延迟 | ✅ |
| 自动重连 | WebSocket 断线自动重连 | ✅ |

---

## 快速开始

### 环境要求

- Python 3.9+
- Node.js 18+（用于执行签名算法 JS）

### 安装依赖

```bash
pip install -r requirements.txt
```

### 配置 Cookie

登录 [taobao.com](https://www.taobao.com) 后，从浏览器开发者工具中复制完整 Cookie 字符串，填入代码底部：

```python
cookies_str = r'your_cookie_string_here'
```

注意：Cookie 必须是登录后的完整状态，至少应包含这些关键字段：

- `unb`
- `_nk_`
- `_m_h5_tk`

否则程序无法完成初始化。

---

## 你应该运行哪个文件

### 方案 A：本地模型自动回复（Ollama）

适合：
- 想离线 / 本地部署
- 已经在本机跑 Ollama
- 接入的是 `gemma` / `qwen` / 其他本地模型

使用文件：

```text
taobao_live -taobao跑通本地自动回复文件（应用这个就改为taobao_live.py）.py
```

步骤：

1. 把这个文件复制或重命名为：

```text
taobao_live.py
```

2. 确认本机 Ollama 在运行，例如：

```bash
ollama list
```

3. 在代码里确认：
- `self.ollama_url`
- `self.ollama_model`

4. 运行：

```bash
python taobao_live.py
```

---

### 方案 B：API 大模型自动回复（百炼 / DashScope）

适合：
- 想要更快的回复速度
- 不想让本地大模型占机器资源
- 已有百炼 API Key

使用文件：

```text
taobao_live -taobao跑通大模型API自动回复文件（应用这个就改为taobao_live.py）.py
```

步骤：

1. 把这个文件复制或重命名为：

```text
taobao_live.py
```

2. 配置环境变量（Windows CMD 示例）：

```bat
set DASHSCOPE_API_KEY=你的百炼APIKey
```

3. 在代码里确认模型名，例如：

```python
self.llm_model = "qwen-turbo"
```

4. 运行：

```bash
python taobao_live.py
```

---

## 项目结构

```text
TaobaoApis/
├── taobao_live.py
├── taobao_live -taobao跑通本地自动回复文件（应用这个就改为taobao_live.py）.py
├── taobao_live -taobao跑通大模型API自动回复文件（应用这个就改为taobao_live.py）.py
├── taobao_apis.py
├── message/
│   └── types.py
├── utils/
│   └── taobao_utils.py
├── static/
│   └── taobao_js_*.js
├── requirements.txt
└── Dockerfile
```

说明：

- `taobao_live.py`：主入口，默认运行文件
- `taobao_live -本地自动回复文件...py`：本地 Ollama 版本
- `taobao_live -大模型API自动回复文件...py`：在线 API 版本
- `taobao_apis.py`：HTTP API 封装
- `utils/taobao_utils.py`：Cookie、签名、消息解密等工具函数
- `message/types.py`：消息类型定义

---

## 自动回复增强点（fork 版本）

与原始版本相比，这个 fork 增加了更接近实战的客服逻辑：

### 1. 连续消息合并后再回复
客户在短时间内连续发多条消息时，不是每条都单独回复，而是：

- 先缓冲
- 在 5 秒窗口内合并
- 合并后交给模型一次性生成回复

这样更像真人客服。

### 2. 随机延迟回复
为了避免回复过快过机械，加入了随机延迟：

- 短消息：约 2 ~ 3.5 秒
- 普通消息：约 3 ~ 5 秒
- 长消息：约 4 ~ 7 秒

### 3. 自动重连
WebSocket 被淘宝侧或网络中断时：

- 自动记录错误
- 等待 5 秒
- 自动重连

### 4. 基础风控
内置了一层非常基础的敏感问题兜底，适合先用于 MVP：

例如命中这些词时，不让模型自由发挥：

- 退款
- 退货
- 投诉
- 发票
- 物流
- 售后

而是先走保守回复。

### 5. 过滤明显非客户正文的消息
淘宝的推送消息里除了聊天正文，还混有：

- ACK / 控制消息
- 回执消息
- 系统状态消息
- 自己发送出去的消息回流

fork 版本加入了基础过滤，尽量只处理真正的客户文本消息。

---

## 接入 AI 智能体的理解方式

核心接入点仍然是 `handle_message`。

原始思路：

```python
reply = f'{send_user_name} 说了: {send_message}'
```

改造成 AI 后，本质上就是：

```python
reply = await your_ai_agent(send_message)
await self.send_msg(websocket, cid, send_user_id, f"cntaobao{self.nk}", make_text(reply))
```

区别只在于：

- 本地模型版：`your_ai_agent()` 调本地 Ollama
- API 版：`your_ai_agent()` 调百炼 / DashScope API

---

## 如何测试是否接通成功

### 测试 1：程序能否初始化
理想日志：

```text
准备连接 WebSocket...
WebSocket 连接成功
init
```

### 测试 2：是否收到客户消息
理想日志：

```text
user: xxx, send_user_id=xxx, message=你好
```

### 测试 3：是否成功调用模型
理想日志：

```text
准备调用 AI，用户消息: 你好
AI 回复内容: ...
```

### 测试 4：是否准备发回淘宝
理想日志：

```text
准备发送消息给 xxx, cid=xxx, type=text
```

---

## 已知问题 / 当前边界

这份 fork 虽然已经能跑通“消息接入 + 大模型自动回复”，但目前仍然属于 MVP + 可实测版，还不是最终工业级版本。

当前边界：

1. 淘宝推送消息结构很多，仍可能混入少量系统 / 回执消息
2. 多会话同时高频进线时，仍建议继续加强消息状态管理
3. 当前没有完整的人工接管中台
4. 当前没有知识库检索（RAG）
5. 售后 / 投诉 / 退款类问题只做了基础兜底，不建议完全无人值守上线

如果你要继续往下做，优先建议补：

- 客户异议处理知识库
- 茶叶知识库注入提示词
- 客户上下文记忆
- 多会话状态锁
- 人工接管开关

---

## 注意事项

- `taobao_live.py` 是消息收发主入口，所有 AI 回复逻辑都在此扩展
- `taobao_apis.py` 包含 HTTP 接口模板，可按需添加其他接口
- 如果你只是想快速试跑，不要自己从零改，直接使用仓库里这两个已跑通版本

---

## 致谢

- 原项目作者：`cv-cat`
- 本仓库在原项目基础上做了自动回复、API 接入、本地模型接入、连续消息合并与稳定性增强

---

## Star 趋势

<a href="https://www.star-history.com/#cv-cat/TaoBaoApis&Date">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=cv-cat/TaoBaoApis&type=Date&theme=dark" />
    <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=cv-cat/TaoBaoApis&type=Date" />
    <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=cv-cat/TaoBaoApis&type=Date" />
  </picture>
</a>
