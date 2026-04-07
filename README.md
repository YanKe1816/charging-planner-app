# Charging Planner (ChatGPT Task App)

Charging Planner 是一个单用途 MCP 工具应用，业务决策逻辑保持不变：

- 在 **charge now** 与 **charge near destination** 之间二选一
- 返回 1 个最佳站点 + 1 个备选（可为空）
- 最多 3 条理由
- `detour_needed` 与 `estimated_charge_minutes`

## 本次修复范围（仅接入层）

本次只升级 MCP transport，未改动充电决策业务逻辑：

- 保留原有工具名与输入/输出结构
- 增加与官方 examples 一致的 MCP 接入形态兼容：
  - `GET /mcp`（SSE 建链）
  - `POST /mcp/messages?sessionId=...`（会话消息）
- 同时保留 `POST /mcp` 直连 JSON-RPC，便于调试

## 运行

```bash
python server.py
```

## 必要 HTTP 路由

- `GET /health`
- `GET /privacy`
- `GET /terms`
- `GET /support`
- `GET /.well-known/openai-apps-challenge`
- `GET /mcp`
- `POST /mcp/messages?sessionId=...`
- `POST /mcp`

## Developer Mode 创建页 URL（必须填）

在 ChatGPT Developer Mode 创建页中，MCP URL 请填写：

**`https://<your-ngrok-subdomain>.ngrok-free.app/mcp`**

> 不要填 `/health` 或根路径，必须是 `/mcp`。

## Tool Contract（保持不变）

### Tool name

`charging_planner`

### Inputs

- `battery_percent`（必填）
- `destination`（必填）
- `urgency_level`（可选：`low|medium|high`，默认 `medium`）

### Output

- `best_station`
- `backup_station`
- `reasons`
- `recommendation`
- `detour_needed`
- `estimated_charge_minutes`
