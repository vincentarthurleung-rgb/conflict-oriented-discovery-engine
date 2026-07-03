"""Standard-library local JSON API for the System B KG."""

from __future__ import annotations

import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from .kg_query import KGQueryEngine


def cytoscape(subgraph):
    return {"nodes": [{"data": {**item, "label": item["label"]}} for item in subgraph["nodes"]], "edges": [{"data": {**item, "label": item["predicate"]}} for item in subgraph["edges"]]}


class KGAPI:
    def __init__(self, kg_root): self.engine = KGQueryEngine(kg_root)

    def dispatch(self, path: str, params: dict[str, list[str]] | None = None):
        params = params or {}
        one = lambda key, default=None: params.get(key, [default])[0]
        if path == "/api/health": return 200, {"status": "OK"}
        if path == "/api/graph/overview": return 200, cytoscape(self.engine.overview())
        if path.startswith("/api/graph/case/"): return 200, cytoscape(self.engine.get_case_subgraph(unquote(path.removeprefix("/api/graph/case/"))))
        if path == "/api/entity/search": return 200, {"results": self.engine.search_entity(one("q", ""))}
        if path.startswith("/api/entity/") and path.endswith("/neighborhood"):
            entity = unquote(path.removeprefix("/api/entity/").removesuffix("/neighborhood"))
            return 200, cytoscape(self.engine.get_entity_neighborhood(entity, int(one("depth", "1"))))
        if path == "/api/triple/search": return 200, cytoscape(self.engine.triple_subgraph(one("subject"), one("predicate"), one("object")))
        if path == "/api/path":
            paths = self.engine.find_paths(one("source", ""), one("target", ""), int(one("max_depth", "3")))
            nodes, edges = {}, {}
            for route in paths:
                nodes.update((item["id"], item) for item in route["nodes"]); edges.update((item["id"], item) for item in route["edges"])
            return 200, {**cytoscape({"nodes": list(nodes.values()), "edges": list(edges.values())}), "paths": paths}
        if path.startswith("/api/evidence/"):
            value = self.engine.store.get_evidence(unquote(path.removeprefix("/api/evidence/")))
            return (200, value) if value else (404, {"error": "evidence_not_found"})
        return 404, {"error": "not_found"}


def make_handler(kg_root):
    api, static = KGAPI(kg_root), Path(__file__).parent / "static"
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urlparse(self.path)
            if parsed.path.startswith("/api/"):
                try: status, value = api.dispatch(parsed.path, parse_qs(parsed.query))
                except (ValueError, TypeError) as error: status, value = 400, {"error": str(error)}
                body = json.dumps(value, ensure_ascii=False).encode()
                self.send_response(status); self.send_header("Content-Type", "application/json; charset=utf-8"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body); return
            relative = "index.html" if parsed.path == "/" else parsed.path.lstrip("/")
            file = static / relative
            if not file.is_file() or static not in file.resolve().parents:
                self.send_error(404); return
            body = file.read_bytes(); self.send_response(200); self.send_header("Content-Type", mimetypes.guess_type(file.name)[0] or "application/octet-stream"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
        def log_message(self, format, *args): pass
    return Handler


def serve(kg_root, host="127.0.0.1", port=8765):
    server = ThreadingHTTPServer((host, port), make_handler(kg_root))
    server.serve_forever()
