from __future__ import annotations

import json
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class Station:
    name: str
    address: str
    power_kw: int
    distance_from_user_km: float
    distance_from_destination_km: float
    detour_minutes: int


# Fixed deterministic data for v1 (no external APIs).
STATIONS: List[Station] = [
    Station("Midway Fast Charge Hub", "1250 River Ave", 250, 3.2, 11.8, 4),
    Station("Downtown ChargePoint Plaza", "18 Market St", 150, 1.1, 16.3, 2),
    Station("Destination Mall Supercharger", "5500 Grand Center Blvd", 120, 14.9, 1.4, 1),
    Station("South Loop HyperCharge", "320 South Loop Dr", 350, 5.7, 8.4, 6),
]

TOOL_DEFINITION: Dict[str, Any] = {
    "name": "charging_planner",
    "title": "Charging Planner",
    "description": "Choose the best EV charging plan right now based on battery, destination, and urgency.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "battery_percent": {"type": "integer", "minimum": 0, "maximum": 100},
            "destination": {"type": "string", "minLength": 1},
            "urgency_level": {"type": "string", "enum": ["low", "medium", "high"], "default": "medium"},
        },
        "required": ["battery_percent", "destination"],
        "additionalProperties": False,
    },
}


def estimate_minutes(battery_percent: int, power_kw: int, charge_now: bool) -> int:
    target = 80 if charge_now else 60
    needed = max(0, target - battery_percent)
    if needed == 0:
        return 0
    minutes_per_percent = 0.9 if power_kw >= 250 else (1.2 if power_kw >= 150 else 1.6)
    return max(8, int(round(needed * minutes_per_percent)))


def choose_stations(battery_percent: int, urgency_level: str) -> Tuple[Station, Optional[Station], bool, str, int, List[str]]:
    must_charge_now = battery_percent <= 25 or (urgency_level == "high" and battery_percent <= 40)

    if must_charge_now:
        ranked = sorted(STATIONS, key=lambda s: (s.detour_minutes, -s.power_kw, s.distance_from_user_km, s.name))
        recommendation = "charge now"
    else:
        ranked = sorted(
            STATIONS,
            key=lambda s: (s.distance_from_destination_km, s.detour_minutes, -s.power_kw, s.name),
        )
        recommendation = "charge near destination"

    best = ranked[0]
    backup = ranked[1] if len(ranked) > 1 else None
    detour_needed = best.detour_minutes > 3
    minutes = estimate_minutes(battery_percent, best.power_kw, recommendation == "charge now")
    reasons = [
        f"{best.name} balances speed ({best.power_kw} kW) with low route impact.",
        f"Estimated stop is about {minutes} minutes for this battery level.",
        (
            "Battery is low for current urgency, so immediate charging reduces risk."
            if recommendation == "charge now"
            else "Current battery can reach destination area; charging later minimizes interruption."
        ),
    ]
    return best, backup, detour_needed, recommendation, minutes, reasons[:3]


def build_tool_result(arguments: Dict[str, Any]) -> Dict[str, Any]:
    battery = int(arguments["battery_percent"])
    if battery < 0 or battery > 100:
        raise ValueError("battery_percent must be between 0 and 100")

    destination = str(arguments["destination"]).strip()
    if not destination:
        raise ValueError("destination is required")

    urgency = str(arguments.get("urgency_level", "medium")).lower()
    if urgency not in {"low", "medium", "high"}:
        urgency = "medium"

    best, backup, detour_needed, recommendation, minutes, reasons = choose_stations(battery, urgency)

    return {
        "best_station": {"name": best.name, "address": best.address, "power_kw": best.power_kw},
        "backup_station": {"name": backup.name, "address": backup.address, "power_kw": backup.power_kw} if backup else None,
        "reasons": reasons,
        "recommendation": recommendation,
        "detour_needed": detour_needed,
        "estimated_charge_minutes": minutes,
    }


def mcp_success(request_id: Any, result: Any) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def mcp_error(request_id: Any, code: int, message: str) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def handle_mcp(payload: Dict[str, Any]) -> Dict[str, Any]:
    method = payload.get("method")
    request_id = payload.get("id")
    params = payload.get("params", {})

    if method == "initialize":
        return mcp_success(
            request_id,
            {
                "protocolVersion": "2025-03-26",
                "serverInfo": {"name": "charging-planner", "version": "1.0.0"},
                "capabilities": {"tools": {"listChanged": False}},
            },
        )

    if method == "notifications/initialized":
        return mcp_success(request_id, {"acknowledged": True})

    if method == "tools/list":
        return mcp_success(request_id, {"tools": [TOOL_DEFINITION]})

    if method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments", {})
        if name != "charging_planner":
            return mcp_error(request_id, -32602, f"Unknown tool: {name}")
        try:
            result = build_tool_result(arguments)
        except Exception as exc:
            return mcp_error(request_id, -32602, f"Invalid arguments: {exc}")

        card_text = (
            f"Best: {result['best_station']['name']}. "
            f"Backup: {result['backup_station']['name'] if result['backup_station'] else 'None'}. "
            f"Recommendation: {result['recommendation']}. "
            f"Detour needed: {'yes' if result['detour_needed'] else 'no'}. "
            f"Est. charge: {result['estimated_charge_minutes']} min."
        )
        return mcp_success(
            request_id,
            {
                "content": [{"type": "text", "text": card_text}],
                "structuredContent": result,
            },
        )

    return mcp_error(request_id, -32601, f"Method not found: {method}")


class ChargingPlannerHandler(BaseHTTPRequestHandler):
    server_version = "ChargingPlannerHTTP/1.0"

    def _send_json(self, payload: Dict[str, Any], status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_text(self, text: str, status: int = 200) -> None:
        body = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/health":
            self._send_json({"status": "ok", "app": "charging-planner", "version": "1.0.0"})
            return
        if self.path == "/privacy":
            self._send_text("Charging Planner v1 stores no personal data server-side and uses fixed mock station data.")
            return
        if self.path == "/terms":
            self._send_text("Charging Planner v1 provides deterministic planning guidance for testing only, not driving safety advice.")
            return
        if self.path == "/support":
            self._send_text("Support: charging-planner@example.com")
            return
        if self.path == "/.well-known/openai-apps-challenge":
            self._send_text("charging-planner-v1-challenge")
            return
        if self.path == "/mcp":
            self._send_json(
                {
                    "name": "charging-planner-mcp",
                    "transport": "HTTP JSON-RPC 2.0",
                    "endpoint": "/mcp",
                    "supports": ["initialize", "notifications/initialized", "tools/list", "tools/call"],
                }
            )
            return

        self._send_text("Not Found", status=404)

    def do_POST(self) -> None:
        if self.path != "/mcp":
            self._send_text("Not Found", status=404)
            return

        content_length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(content_length)
        try:
            payload = json.loads(raw.decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("payload must be object")
        except Exception:
            self._send_json(mcp_error(None, -32700, "Parse error"), status=400)
            return

        response = handle_mcp(payload)
        self._send_json(response)


def run_server(host: str = "0.0.0.0", port: int = 8000) -> None:
    httpd = ThreadingHTTPServer((host, port), ChargingPlannerHandler)
    print(f"Charging Planner listening on http://{host}:{port}")
    httpd.serve_forever()


if __name__ == "__main__":
    run_server()
