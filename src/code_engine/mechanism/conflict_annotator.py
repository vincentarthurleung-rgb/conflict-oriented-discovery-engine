"""Map existing L3 conflict decisions onto mechanism objects without recomputation."""

from __future__ import annotations

import hashlib

from code_engine.mechanism.models import MechanismConflictAnnotation, MechanismGraph
from code_engine.mechanism.path_finder import find_mechanism_paths


def annotate_mechanism_graph_with_conflicts(mechanism_graph: MechanismGraph, conflict_edges: list[dict], context_attributions: list[dict] | None = None) -> MechanismGraph:
    graph = mechanism_graph.model_copy(deep=True)
    attribution = {str(item.get("conflict_edge_id")): item for item in (context_attributions or [])}
    annotations = []
    for conflict in conflict_edges:
        conflict_type = str(conflict.get("conflict_type") or conflict.get("conflict_attribution_type") or "Uncontested")
        is_conflict = conflict.get("conflict_status") == "conflicting" or conflict_type not in {"", "None", "Uncontested"}
        if not is_conflict:
            continue
        subject_id = str(conflict.get("subject_canonical_id") or "")
        object_id = str(conflict.get("object_canonical_id") or "")
        if not subject_id or not object_id:
            continue
        conflict_id = str(conflict.get("edge_id") or f"{subject_id}->{object_id}")
        for edge in graph.edges:
            if (str(edge.subject_canonical_id or ""), str(edge.object_canonical_id or "")) != (subject_id, object_id):
                continue
            relation = conflict.get("relation_type")
            direction = conflict.get("direction")
            if relation and str(relation) != edge.relation_type:
                continue
            if direction and str(direction) != edge.direction:
                continue
            pair_level = not relation or not direction
            warning = ["pair_level_annotation=true"] if pair_level else []
            edge.conflict_edge_ids = list(dict.fromkeys(edge.conflict_edge_ids + [conflict_id]))
            edge.conflict_types = list(dict.fromkeys(edge.conflict_types + [conflict_type]))
            edge.has_conflict = True
            edge.warnings = list(dict.fromkeys(edge.warnings + warning))
            attr = attribution.get(conflict_id, {})
            annotation_id = hashlib.sha256(f"{edge.edge_id}|{conflict_id}".encode()).hexdigest()[:16]
            annotations.append(MechanismConflictAnnotation(annotation_id=annotation_id, mechanism_edge_id=edge.edge_id, conflict_edge_id=conflict_id, conflict_type=conflict_type, entropy=conflict.get("entropy") or conflict.get("marginal_entropy_H_R"), attribution_summary=dict(attr.get("score_components") or attr), context_explanation={"ranked_contexts": attr.get("ranked_contexts", []), "primary_driver": conflict.get("primary_driver")}, warnings=warning))
    graph.conflict_annotations = annotations
    max_length = max((path.path_length for path in graph.paths), default=3)
    graph.paths = find_mechanism_paths(graph, max_path_length=max_length)
    graph.counts["conflict_annotation_count"] = len(annotations)
    return graph
