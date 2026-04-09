# Changelog

All notable changes to this fork will be documented in this file.

This project is based on `cv-cat/TaoBaoApis` and extended for practical AI auto-reply use cases.

---

## 2026-04-08

### Added

- Added a local-model auto-reply runnable variant:
  - `taobao_live -taobao跑通本地自动回复文件（应用这个就改为taobao_live.py）.py`
- Added an API-model auto-reply runnable variant:
  - `taobao_live -taobao跑通大模型API自动回复文件（应用这个就改为taobao_live.py）.py`
- Added continuous-message merge logic:
  - messages from the same session can be merged within a short time window before generating a reply
- Added random delayed reply behavior to make replies feel less mechanical
- Added basic risk-word fallback handling for sensitive after-sales topics
- Added auto-reconnect logic for websocket disconnects
- Added README documentation for:
  - local Ollama mode
  - DashScope / 百炼 API mode
  - message merge / delay / reconnect capabilities

### Changed

- Refactored the reply entry from simple echo behavior into model-based reply generation
- Reworked the main websocket loop to support reconnect after connection loss
- Improved message handling to better filter obvious non-chat and self-sent messages
- Updated README to clarify fork-specific runnable files and deployment paths

### Notes

Current fork status:
- Core chain is available: receive message -> call model -> build reply -> send message
- Still belongs to MVP / practical test stage, not final production-grade version

Current known limitations:
- Taobao push payloads contain multiple message structure variants; filtering still needs continued strengthening
- Customer / system / assistant-side mixed message structures may still appear in logs
- No full manual takeover system yet
- No RAG / product knowledge injection yet
- After-sales issues only have lightweight fallback protection for now

### Recommended next steps

- Add stricter message-type classification before AI invocation
- Inject tea knowledge / FAQ / objection-handling prompts into model context
- Add per-session state management to improve multi-conversation stability
- Add manual takeover switch and audit logging
- Add better send-confirmation / retry logic after reconnect

---

## Fork Positioning

This fork focuses on turning the original protocol-research project into a more practical AI auto-reply runtime for Taobao customer-service scenarios.

Compared with the upstream project, this fork emphasizes:
- runnable examples
- local model integration
- API model integration
- message merge + delayed reply
- reconnect resilience
- practical README guidance
