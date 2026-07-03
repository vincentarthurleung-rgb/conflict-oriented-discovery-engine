"""Standard-library HTTP server for dashboard and KG routes."""

from __future__ import annotations

import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .dashboard_api import DashboardAPI


def make_handler(system_b_root, kg_root):
    api, static = DashboardAPI(system_b_root, kg_root), Path(__file__).parent / "static"
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urlparse(self.path)
            if parsed.path.startswith("/api/"):
                try: status, value = api.dispatch(parsed.path, parse_qs(parsed.query))
                except (ValueError, TypeError) as error: status, value = 400, {"error": str(error)}
                body = json.dumps(value, ensure_ascii=False).encode("utf-8")
                self.send_response(status); self.send_header("Content-Type", "application/json; charset=utf-8"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body); return
            relative = "index.html" if parsed.path == "/" else parsed.path.lstrip("/")
            path = static / relative
            if not path.is_file() or static not in path.resolve().parents:
                self.send_error(404); return
            body = path.read_bytes(); self.send_response(200); self.send_header("Content-Type", mimetypes.guess_type(path.name)[0] or "application/octet-stream"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
        def log_message(self, format, *args): pass
    return Handler


def serve(system_b_root, kg_root, host="127.0.0.1", port=8765, on_ready=None):
    server = ThreadingHTTPServer((host, port), make_handler(system_b_root, kg_root))
    if on_ready:
        on_ready()
    server.serve_forever()
