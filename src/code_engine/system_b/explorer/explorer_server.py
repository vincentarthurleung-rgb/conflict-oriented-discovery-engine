"""Standard-library HTTP server for Knowledge Explorer."""
from __future__ import annotations
import json,mimetypes
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs,urlparse
from .explorer_api import ExplorerAPI

def make_handler(display_kg_root,review_root=None):
    api=ExplorerAPI(display_kg_root,review_root);static=Path(__file__).parent/"static"
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed=urlparse(self.path)
            if parsed.path.startswith("/api/"):
                try:status,value=api.dispatch(parsed.path,parse_qs(parsed.query))
                except (ValueError,TypeError) as error:status,value=400,{"error":str(error)}
                body=json.dumps(value,ensure_ascii=False).encode();self.send_response(status);self.send_header("Content-Type","application/json; charset=utf-8");self.send_header("Content-Length",str(len(body)));self.end_headers();self.wfile.write(body);return
            relative=parsed.path.lstrip("/")
            path=static/relative if relative in {"app.js","style.css"} else static/"index.html"
            body=path.read_bytes();self.send_response(200);self.send_header("Content-Type",mimetypes.guess_type(path.name)[0] or "text/html");self.send_header("Content-Length",str(len(body)));self.end_headers();self.wfile.write(body)
        def log_message(self,format,*args):pass
    Handler.api=api
    return Handler

def serve(display_kg_root,review_root=None,host="127.0.0.1",port=8765,on_ready=None):
    server=ThreadingHTTPServer((host,port),make_handler(display_kg_root,review_root));on_ready and on_ready();server.serve_forever()
