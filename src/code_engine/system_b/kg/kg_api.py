"""Standard-library local JSON API for the System B KG."""

from __future__ import annotations

import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from .kg_query import KGQueryEngine


def cytoscape(subgraph, engine=None, detail="summary", mode="overview", show_unavailable=False):
    """Project stored records into readable canvas data; raw labels require debug."""
    debug = detail == "debug"
    source_nodes = subgraph["nodes"]
    if not debug:
        source_nodes = [item for item in source_nodes if item["type"] not in {"evidence", "paper"}]
        if not show_unavailable:
            source_nodes = [item for item in source_nodes if not (item["type"] == "validator" and item.get("metadata", {}).get("status") == "recommended_unavailable")]
    kept = {item["id"] for item in source_nodes}
    source_edges = subgraph["edges"] if debug else [item for item in subgraph["edges"] if item["source"] in kept and item["target"] in kept]
    type_numbers = {}
    nodes = []
    for item in source_nodes:
        full_label = str(item.get("label") or item["id"])
        type_numbers[item["type"]] = type_numbers.get(item["type"], 0) + 1
        short = full_label if debug else _short_label(item, type_numbers[item["type"]])
        nodes.append({"data": {**item, "label": short, "short_label": short, "full_label": full_label}})
    focused = mode in {"entity", "triple", "path"}
    edges = []
    for item in source_edges:
        compact = str(item.get("predicate") or "")[:24]
        label = compact if debug or focused else ""
        evidence = []
        if engine:
            for evidence_id in item.get("evidence_ids", []):
                value = engine.evidence.get(evidence_id)
                if value:
                    evidence.append({"evidence_id": value["id"], "case_id": value.get("case_id"), "pmid": value.get("pmid"), "pmcid": value.get("pmcid"), "source_scope": value.get("source_scope"), "section_title": value.get("section_title"), "evidence_sentence": value.get("evidence_sentence"), "provenance_artifact": value.get("provenance_artifact")})
        edges.append({"data": {**item, "label": label, "compact_label": compact, "evidence_count": len(evidence), "evidence": evidence}})
    result = {"nodes": nodes, "edges": edges, "detail": detail, "mode": mode}
    if debug:
        result["warning"] = "Debug graph may be visually cluttered."
    return result


def _short_label(item, number):
    label, node_type = str(item.get("label") or item["id"]), item["type"]
    if node_type == "evidence": return f"Evidence {number}"
    if node_type == "paper":
        pmid = item.get("metadata", {}).get("pmid")
        return f"PMID:{pmid}" if pmid else f"Paper {number}"
    if node_type == "hypothesis" and len(label) > 32: return f"Hypothesis {number}"
    return label if len(label) <= 32 else label[:29].rstrip() + "..."


class KGAPI:
    def __init__(self, kg_root): self.engine = KGQueryEngine(kg_root)

    def dispatch(self, path: str, params: dict[str, list[str]] | None = None):
        params = params or {}
        one = lambda key, default=None: params.get(key, [default])[0]
        detail = one("detail", "summary")
        show_unavailable = str(one("show_unavailable", "false")).lower() == "true"
        if path == "/api/health": return 200, {"status": "OK"}
        if path == "/api/graph/overview": return 200, cytoscape(self.engine.overview(), self.engine, detail, "overview", show_unavailable)
        if path.startswith("/api/graph/case/"): return 200, cytoscape(self.engine.get_case_subgraph(unquote(path.removeprefix("/api/graph/case/"))), self.engine, detail, "case", show_unavailable)
        if path == "/api/entity/search": return 200, {"results": self.engine.search_entity(one("q", ""))}
        if path.startswith("/api/entity/") and path.endswith("/neighborhood"):
            entity = unquote(path.removeprefix("/api/entity/").removesuffix("/neighborhood"))
            return 200, cytoscape(self.engine.get_entity_neighborhood(entity, int(one("depth", "1"))), self.engine, detail, "entity", show_unavailable)
        if path == "/api/triple/search": return 200, cytoscape(self.engine.triple_subgraph(one("subject"), one("predicate"), one("object")), self.engine, detail, "triple", show_unavailable)
        if path == "/api/path":
            paths = self.engine.find_paths(one("source", ""), one("target", ""), int(one("max_depth", "3")))
            nodes, edges = {}, {}
            for route in paths:
                nodes.update((item["id"], item) for item in route["nodes"]); edges.update((item["id"], item) for item in route["edges"])
            return 200, {**cytoscape({"nodes": list(nodes.values()), "edges": list(edges.values())}, self.engine, detail, "path", show_unavailable), "paths": paths, "path_interpretation": "context-mediated path; not a direct biological assertion" if any(node.get("type") == "context" for node in nodes.values()) else "graph path"}
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
