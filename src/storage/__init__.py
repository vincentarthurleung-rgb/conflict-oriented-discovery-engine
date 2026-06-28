"""Legacy storage namespace mapped to package-owned responsibilities."""

from code_engine.acquisition.manifest import build_artifact_inventory, load_artifact_inventory
from code_engine.graph.knowledge_store import build_knowledge_store, load_knowledge_store

__all__ = [
    "build_artifact_inventory", "load_artifact_inventory",
    "build_knowledge_store", "load_knowledge_store",
]

