# Charging Planner (ChatGPT Task App)

Charging Planner is a single-purpose MCP task app that makes one deterministic EV decision:

- **Charge now** or **charge near destination**
- with one **best station**, one **optional backup**, up to **3 reasons**,
- **detour needed** flag, and **estimated charging minutes**.

This v1 intentionally uses **fixed mock station data** (no real APIs) to validate Task App flow.

## Scope

This app does **not** provide lists, maps, or discovery UX. It returns one decision-card-style result.

## Files

- `server.py` — HTTP server with required web routes and MCP JSON-RPC handler.
- `README.md` — setup and usage.
- `DELIVERY_REPORT.md` — implementation and self-test notes.

## Run

```bash
python server.py
```

## Required Endpoints

- `GET /health`
- `GET /privacy`
- `GET /terms`
- `GET /support`
- `GET /.well-known/openai-apps-challenge`
- `GET /mcp`
- `POST /mcp`

## MCP Methods Supported (`POST /mcp`)

- `initialize`
- `notifications/initialized`
- `tools/list`
- `tools/call`

## Single Tool Contract

### Tool name

`charging_planner`

### Inputs

- `battery_percent` (required)
- `destination` (required)
- `urgency_level` (optional: `low|medium|high`, default `medium`)

### Output (deterministic)

- `best_station`
- `backup_station`
- `reasons`
- `recommendation`
- `detour_needed`
- `estimated_charge_minutes`

## Quick cURL Examples

### initialize

```bash
curl -s http://localhost:8000/mcp \
  -H 'content-type: application/json' \
  -d '{"jsonrpc":"2.0","id":"1","method":"initialize","params":{}}'
```

### tools/list

```bash
curl -s http://localhost:8000/mcp \
  -H 'content-type: application/json' \
  -d '{"jsonrpc":"2.0","id":"2","method":"tools/list","params":{}}'
```

### tools/call

```bash
curl -s http://localhost:8000/mcp \
  -H 'content-type: application/json' \
  -d '{"jsonrpc":"2.0","id":"3","method":"tools/call","params":{"name":"charging_planner","arguments":{"battery_percent":22,"destination":"Downtown Office","urgency_level":"high"}}}'
```

The response includes a short card-style text summary plus deterministic structured data.
