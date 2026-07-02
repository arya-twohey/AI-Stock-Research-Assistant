from __future__ import annotations

import json
import mimetypes
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from app import alpaca_service
from app.config import STATIC_ROOT, load_env_file


def _json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict | list):
    body = json.dumps(payload, indent=2).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _read_body(handler: BaseHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length", "0"))
    if length == 0:
        return {}
    return json.loads(handler.rfile.read(length).decode("utf-8"))


class TraderBotHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        return

    def do_GET(self):
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)

        try:
            if parsed.path == "/api/account":
                return _json_response(self, 200, alpaca_service.account_summary())
            if parsed.path == "/api/positions":
                return _json_response(self, 200, alpaca_service.positions())
            if parsed.path == "/api/orders":
                status = query.get("status", ["all"])[0]
                limit = int(query.get("limit", ["25"])[0])
                return _json_response(self, 200, alpaca_service.orders(status=status, limit=limit))
            if parsed.path == "/api/research":
                symbol = query.get("symbol", ["AAPL"])[0]
                return _json_response(self, 200, alpaca_service.research(symbol))
        except Exception as exc:
            return _json_response(self, 500, {"error": str(exc)})

        return self._static(parsed.path)

    def do_POST(self):
        parsed = urlparse(self.path)
        try:
            body = _read_body(self)
            if parsed.path == "/api/trade/preview":
                return _json_response(
                    self,
                    200,
                    alpaca_service.trade_preview(
                        body.get("symbol", "AAPL"),
                        body.get("side", "buy"),
                        body.get("qty", 1),
                    ),
                )
            if parsed.path == "/api/trade/submit":
                return _json_response(
                    self,
                    200,
                    alpaca_service.submit_market_order(
                        body.get("symbol", "AAPL"),
                        body.get("side", "buy"),
                        body.get("qty", 1),
                    ),
                )
        except Exception as exc:
            return _json_response(self, 500, {"error": str(exc)})

        return _json_response(self, 404, {"error": "Not found"})

    def _static(self, request_path: str):
        if request_path in ("", "/"):
            file_path = STATIC_ROOT / "index.html"
        else:
            candidate = (STATIC_ROOT / request_path.lstrip("/")).resolve()
            if STATIC_ROOT.resolve() not in candidate.parents and candidate != STATIC_ROOT.resolve():
                return _json_response(self, 403, {"error": "Forbidden"})
            file_path = candidate

        if not file_path.exists() or not file_path.is_file():
            file_path = STATIC_ROOT / "index.html"

        content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        body = Path(file_path).read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main():
    load_env_file()
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))
    server = ThreadingHTTPServer((host, port), TraderBotHandler)
    print(f"AI Stock Research Assistant running at http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
