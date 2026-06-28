"""Build a renderer-neutral graph view from knowledge-store records."""

from code_engine.visualization.graph_models import GraphView


def build_graph_view(store: dict) -> GraphView:
    nodes = [{"id": entity, "label": entity} for entity in store.get("entities", [])]
    edges = [
        {"source": pair.get("subject"), "target": pair.get("object")}
        for pair in store.get("pairs", {}).values()
    ]
    return GraphView(nodes=nodes, edges=edges)

