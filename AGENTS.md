# model-download-tool — Agent 说明

本目录已接入「Pi + Qwen 协调者 + Orca 编排」架构。

## 新会话必读

跨会话完整上下文在：`~/.pi/agent/coordinator-plan.md`（架构、路由策略、订阅监控、已验证状态、POC 计划）。

## 关键事实速览

- Pi 默认模型：`Qwen3.8-27B-OptiQ-4bit`（本地 oMLX，**用户锁定，禁止切换**）
- 本地推理：oMLX `http://127.0.0.1:8088/v1`（不是 LM Studio）
- Orca repo id：`7c1ead41-3076-40ef-bb00-5b8780909438`
- 外部 workers：Codex / Claude / Antigravity（CLI `agy`）/ DeepSeek（Pi 直连）
- 协调日志：`~/.pi/agent/coordinator-log.jsonl`
