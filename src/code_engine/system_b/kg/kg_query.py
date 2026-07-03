"""In-memory bounded queries over a locally built System B KG."""

from __future__ import annotations

from collections import deque
from pathlib import Path
from typing import Any

from .kg_schema import normalize_entity
from .kg_store import KGStore


class KGQueryEngine:
    def __init__(self, kg_root: str | Path):
        self.store = KGStore(kg_root)
        nodes, edges, evidence = self.store.load()
        self.nodes = {item["id"]: item for item in nodes}
        self.edges = edges
        self.evidence = {item["id"]: item for item in evidence}

    def search_entity(self, query: str) -> list[dict[str, Any]]:
        needle = normalize_entity(query)
        matches = []
        for item in self.nodes.values():
            if item["type"] != "entity": continue
            terms = [item["label"], *item.get("aliases", [])]
            normalized = [normalize_entity(term) for term in terms]
            if any(needle in term or term in needle for term in normalized):
                matches.append((0 if needle in normalized else 1, len(item["label"]), item))
        return [item for _, _, item in sorted(matches, key=lambda value: (value[0], value[1], value[2]["id"]))]

    def get_entity_neighborhood(self, entity: str, depth: int = 1, edge_types: list[str] | None = None) -> dict[str, list[dict]]:
        seeds = self._entity_ids(entity)
        if not seeds: return {"nodes": [], "edges": []}
        return self._bounded_subgraph(seeds, max(0, min(depth, 5)), edge_types)

    def search_triples(self, subject: str | None = None, predicate: str | None = None, object: str | None = None) -> list[dict]:
        subject_ids = set(self._entity_ids(subject)) if subject else None
        object_ids = set(self._entity_ids(object)) if object else None
        result = []
        for item in self.edges:
            if item["edge_type"] != "claim_relation": continue
            if subject_ids is not None and item["source"] not in subject_ids: continue
            if object_ids is not None and item["target"] not in object_ids: continue
            if predicate and not self._predicate_matches(predicate, item["predicate"]): continue
            result.append(item)
        return result

    def triple_subgraph(self, subject=None, predicate=None, object_=None) -> dict[str, list[dict]]:
        matches = self.search_triples(subject, predicate, object_)
        node_ids = {value for item in matches for value in (item["source"], item["target"])}
        for item in matches:
            node_ids.update(item.get("paper_ids", [])); node_ids.update(item.get("evidence_ids", []))
        related = [edge for edge in self.edges if edge["id"] in {item["id"] for item in matches} or (edge["source"] in node_ids and edge["target"] in node_ids)]
        return {"nodes": [self.nodes[item] for item in node_ids if item in self.nodes], "edges": related}

    def find_paths(self, source_entity: str, target_entity: str, max_depth: int = 3) -> list[dict]:
        sources, targets = self._route_node_ids(source_entity), set(self._route_node_ids(target_entity))
        limit = max(1, min(max_depth, 6))
        adjacency: dict[str, list[tuple[str, dict]]] = {}
        for item in self.edges:
            if item["edge_type"] not in {"claim_relation", "has_context"}: continue
            adjacency.setdefault(item["source"], []).append((item["target"], item))
            adjacency.setdefault(item["target"], []).append((item["source"], item))
        paths = []
        queue = deque((source, [source], []) for source in sources)
        while queue and len(paths) < 100:
            current, node_path, edge_path = queue.popleft()
            if current in targets and edge_path:
                paths.append({"nodes": [self.nodes[item] for item in node_path], "edges": edge_path, "length": len(edge_path)})
                continue
            if len(edge_path) >= limit: continue
            for neighbor, relation in adjacency.get(current, []):
                if neighbor not in node_path:
                    queue.append((neighbor, node_path + [neighbor], edge_path + [relation]))
        return paths

    def get_case_subgraph(self, case_id: str) -> dict[str, list[dict]]:
        edges = [item for item in self.edges if item.get("case_id") == case_id]
        node_ids = {f"case:{case_id}"}
        for item in edges: node_ids.update((item["source"], item["target"])); node_ids.update(item.get("paper_ids", [])); node_ids.update(item.get("evidence_ids", []))
        nodes = [item for item in self.nodes.values() if item["id"] in node_ids or case_id in item.get("case_ids", [])]
        return {"nodes": nodes, "edges": edges}

    def overview(self) -> dict[str, list[dict]]:
        return {"nodes": list(self.nodes.values()), "edges": self.edges}

    def _bounded_subgraph(self, seeds, depth, edge_types):
        visited, frontier, chosen = set(seeds), set(seeds), []
        for _ in range(depth):
            next_frontier = set()
            for item in self.edges:
                if edge_types and item["edge_type"] not in edge_types: continue
                if item["source"] in frontier or item["target"] in frontier:
                    chosen.append(item); next_frontier.update((item["source"], item["target"]))
            next_frontier -= visited; visited |= next_frontier; frontier = next_frontier
        unique = {item["id"]: item for item in chosen}
        return {"nodes": [self.nodes[item] for item in visited if item in self.nodes], "edges": list(unique.values())}

    def _entity_ids(self, query):
        if not query: return []
        if query in self.nodes and self.nodes[query]["type"] == "entity": return [query]
        return [item["id"] for item in self.search_entity(query)]

    def _route_node_ids(self, query):
        if query in self.nodes: return [query]
        needle = normalize_entity(query)
        candidates = []
        for item in self.nodes.values():
            if item["type"] not in {"entity", "context", "pathway"}: continue
            terms = [item["label"], *item.get("aliases", [])]
            if any(needle in normalize_entity(term) or normalize_entity(term) in needle for term in terms):
                candidates.append(item["id"])
        return sorted(candidates)

    @staticmethod
    def _predicate_matches(query, value):
        def root(text):
            text = normalize_entity(text)
            for suffix in ("ation", "ions", "ion", "ates", "ate", "ing", "ed", "s"):
                if text.endswith(suffix) and len(text) > len(suffix) + 2: return text[:-len(suffix)]
            return text
        return root(query) == root(value) or normalize_entity(query) in normalize_entity(value)
