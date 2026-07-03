"""Build a provenance-preserving KG from exported case bundle artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .kg_exporter import KGExporter
from .kg_schema import edge, entity_id, node, stable_id
from .kg_store import KGStore


class KGBuilder:
    def __init__(self, bundle_root: str | Path, output_root: str | Path):
        self.bundle_root, self.output_root = Path(bundle_root), Path(output_root)
        self.nodes: dict[str, dict] = {}
        self.edges: dict[str, dict] = {}
        self.evidence: dict[str, dict] = {}
        self.aliases: dict[str, set[str]] = {}
        self.warnings: list[dict] = []
        self.case_ids: set[str] = set()
        self.fulltext_claim_count = 0

    def build(self) -> dict[str, Any]:
        bundles = sorted(path.parent for path in self.bundle_root.glob("*/case_bundle_manifest.json"))
        for bundle in bundles:
            self._build_case(bundle)
        for entity, aliases in self.aliases.items():
            self.nodes[entity]["aliases"] = sorted(aliases, key=str.lower)
        KGStore(self.output_root).write(self.nodes.values(), self.edges.values(), self.evidence.values(), self.warnings)
        summary = self._summary()
        KGExporter(self.output_root).write_metadata(summary, self.aliases)
        return summary

    def _build_case(self, bundle: Path) -> None:
        manifest = self._json(bundle / "case_bundle_manifest.json")
        case_id = manifest.get("case_id") or bundle.name
        self.case_ids.add(case_id)
        case_node = f"case:{case_id}"
        self._add_node(node(case_node, case_id, "case", [case_id], metadata={"case_role": manifest.get("case_type"), "bundle_path": str(bundle), "scientific_output_class": manifest.get("scientific_output_class"), "is_zero_claim_case": manifest.get("is_zero_claim_case", False), "zero_claim_reason": manifest.get("zero_claim_reason"), "case_execution_outcome": manifest.get("case_execution_outcome")}))
        for name, scope in (("core_observations.jsonl", "abstract"), ("l35_fulltext_l1_claims.jsonl", "full_text")):
            self._read_claims(bundle / name, case_id, case_node, scope)
        self._add_hypotheses(bundle / "hypothesis_summary.json", case_id, case_node)
        self._add_validators(bundle, case_id, case_node)
        output_class = manifest.get("scientific_output_class")
        if output_class:
            status_id = f"status:{output_class}"
            self._add_node(node(status_id, output_class, "status", [case_id], metadata={"non_biological_metadata": True, "explanation": manifest.get("zero_claim_reason")}))
            self._link(stable_id("edge", case_node, status_id), case_node, status_id, "has_status", "has_status", case_id, metadata={"non_biological_metadata": True})

    def _read_claims(self, path: Path, case_id: str, case_node: str, scope: str) -> None:
        if not path.is_file():
            return
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as error:
                self._warn(path, number, "invalid_json", str(error))
                continue
            subject = self._first(record, "subject_name", "subject", "entity_a", "source_entity")
            predicate = self._first(record, "predicate", "relation", "direction", "relation_family")
            object_ = self._first(record, "object_name", "object", "entity_b", "target_entity")
            subject, object_ = self._label(subject), self._label(object_)
            if not all((subject, predicate, object_)):
                self._warn(path, number, "missing_subject_predicate_object", record.get("observation_id") or record.get("claim_id"))
                continue
            self._add_claim(record, case_id, case_node, scope, path.name, str(subject), str(predicate), str(object_))
            if scope == "full_text":
                self.fulltext_claim_count += 1

    def _add_claim(self, record, case_id, case_node, scope, artifact, subject, predicate, object_):
        source_id, target_id = self._entity(subject, case_id), self._entity(object_, case_id)
        observation_id = record.get("observation_id") or record.get("claim_id") or stable_id("record", case_id, subject, predicate, object_, record.get("evidence_sentence"))
        evidence_id = f"evidence:{observation_id}"
        raw_paper = record.get("paper_id") or record.get("pmid") or record.get("pmcid")
        paper_id = self._paper_id(record)
        if paper_id:
            self._add_node(node(paper_id, record.get("title") or str(raw_paper), "paper", [case_id], metadata={"pmid": record.get("pmid"), "pmcid": record.get("pmcid"), "publication_year": record.get("publication_year")}))
        evidence = {"id": evidence_id, "case_id": case_id, "paper_id": paper_id, "pmid": record.get("pmid"), "pmcid": record.get("pmcid"), "source_scope": scope, "evidence_sentence": record.get("evidence_sentence") or record.get("claim_text") or record.get("text"), "section_title": record.get("section_title"), "observation_id": record.get("observation_id"), "claim_id": record.get("claim_id"), "chunk_hash": record.get("chunk_hash"), "provenance_artifact": artifact}
        self.evidence[evidence_id] = evidence
        self._add_node(node(evidence_id, evidence["evidence_sentence"] or evidence_id, "evidence", [case_id], metadata={"source_scope": scope}))
        relation_id = stable_id("edge", case_id, observation_id, source_id, predicate, target_id)
        self.edges[relation_id] = edge(relation_id, source_id, target_id, predicate, "claim_relation", case_id, polarity=record.get("direction_polarity") or record.get("polarity"), paper_ids=[paper_id] if paper_id else [], evidence_ids=[evidence_id], confidence=record.get("confidence"), source_scope=scope, metadata={"observation_id": observation_id})
        self._link(stable_id("edge", evidence_id, relation_id), evidence_id, source_id, "derived_from", "derived_from", case_id, evidence_ids=[evidence_id])
        if paper_id:
            self._link(stable_id("edge", evidence_id, paper_id), evidence_id, paper_id, "mentioned_in", "mentioned_in", case_id, evidence_ids=[evidence_id])
        self._link(stable_id("edge", relation_id, case_node), source_id, case_node, "part_of_case", "part_of_case", case_id, metadata={"claim_edge_id": relation_id})
        for context in self._terms(record, "context_terms", "cancer_context_terms", "context"):
            context_id = stable_id("context", context.lower())
            self._add_node(node(context_id, context, "context", [case_id]))
            self._link(stable_id("edge", target_id, context_id, observation_id), target_id, context_id, "has_context", "has_context", case_id, evidence_ids=[evidence_id])
        for pathway in self._terms(record, "pathway", "pathway_name", "pathway_terms"):
            pathway_id = stable_id("pathway", pathway.lower())
            self._add_node(node(pathway_id, pathway, "pathway", [case_id]))
            self._link(stable_id("edge", target_id, pathway_id, observation_id), target_id, pathway_id, "has_context", "has_context", case_id, evidence_ids=[evidence_id])

    def _add_hypotheses(self, path: Path, case_id: str, case_node: str) -> None:
        data = self._json(path)
        seen = set()
        hypotheses = list(data.get("top_hypotheses", [])) + list(data.get("manual_review_followups", []))
        for item in hypotheses:
            hypothesis_id = item.get("hypothesis_id")
            if not hypothesis_id or hypothesis_id in seen:
                continue
            seen.add(hypothesis_id)
            node_id = f"hypothesis:{hypothesis_id}"
            label = item.get("hypothesis_text") or item.get("reason") or hypothesis_id
            self._add_node(node(node_id, label, "hypothesis", [case_id], metadata=item))
            self._link(stable_id("edge", node_id, case_node), node_id, case_node, "part_of_case", "part_of_case", case_id)
            for entity in self._terms(item, "involved_entities", "entities"):
                entity_node = self._entity(entity, case_id)
                self._link(stable_id("edge", node_id, entity_node), node_id, entity_node, "derived_from", "derived_from", case_id)

    def _add_validators(self, bundle: Path, case_id: str, case_node: str) -> None:
        selection = self._json(bundle / "validator_selection_report.json").get("validator_selection", {})
        external = self._json(bundle / "l7_external_validation_summary.json")
        executed = set(selection.get("executed_validators", external.get("executed_validators", [])))
        skipped = set(selection.get("skipped_validators", external.get("skipped_validators", [])))
        unavailable = set(selection.get("recommended_but_unavailable", []))
        results = external.get("validator_results", {})
        for validator in sorted(executed | skipped | unavailable | set(results)):
            validator_id = f"validator:{validator}"
            result = results.get(validator, {})
            status = result.get("status") or ("executed" if validator in executed else "skipped" if validator in skipped else "recommended_unavailable")
            metadata = {"status": status, "interpretation": result.get("interpretation"), "mapping_status": result.get("mapping_status"), "non_biological_metadata": True}
            if validator in executed:
                metadata.update({"external_validation_status": external.get("status"), "interpretation_distribution": external.get("interpretation_distribution", {}), "biological_interpretation": external.get("biological_interpretation"), "overall_validation_score": external.get("overall_validation_score")})
            self._add_node(node(validator_id, validator, "validator", [case_id], metadata=metadata))
            self._link(stable_id("edge", case_node, validator_id), case_node, validator_id, "has_validator_result", "has_validator_result", case_id, metadata=metadata)

    def _entity(self, label: str, case_id: str) -> str:
        node_id = entity_id(label)
        self.aliases.setdefault(node_id, set()).add(label)
        self._add_node(node(node_id, label, "entity", [case_id], aliases=[label]))
        return node_id

    def _add_node(self, value: dict) -> None:
        existing = self.nodes.get(value["id"])
        if existing:
            existing["case_ids"] = sorted(set(existing["case_ids"]) | set(value["case_ids"]))
            existing["source_count"] += 1
            existing["metadata"].update({key: item for key, item in value["metadata"].items() if item is not None})
        else:
            value["source_count"] = 1
            self.nodes[value["id"]] = value

    def _link(self, edge_id, source, target, predicate, edge_type, case_id, **values):
        self.edges[edge_id] = edge(edge_id, source, target, predicate, edge_type, case_id, **values)

    def _summary(self):
        return {"schema_version": "system_b_kg_v1", "case_count": len(self.case_ids), "node_count": len(self.nodes), "edge_count": len(self.edges), "evidence_count": len(self.evidence), "entity_count": sum(item["type"] == "entity" for item in self.nodes.values()), "paper_count": sum(item["type"] == "paper" for item in self.nodes.values()), "case_count_indexed": len(self.case_ids), "claim_relation_count": sum(item["edge_type"] == "claim_relation" for item in self.edges.values()), "fulltext_claim_count": self.fulltext_claim_count, "skipped_record_count": len(self.warnings)}

    def _warn(self, path, line, reason, detail=None):
        self.warnings.append({"artifact": str(path), "line": line, "reason": reason, "detail": detail})

    @staticmethod
    def _json(path):
        if not path.is_file(): return {}
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _first(record, *names):
        return next((record.get(name) for name in names if record.get(name) not in (None, "")), None)

    @staticmethod
    def _label(value):
        if isinstance(value, dict): return value.get("name") or value.get("label") or value.get("text")
        return value

    @staticmethod
    def _paper_id(record):
        if record.get("pmid"): return f"paper:PMID:{record['pmid']}"
        if record.get("pmcid"): return f"paper:PMCID:{record['pmcid']}"
        if record.get("paper_id"): return f"paper:{record['paper_id']}"
        return None

    @staticmethod
    def _terms(record, *names):
        values = []
        for name in names:
            value = record.get(name)
            if isinstance(value, str) and value.strip(): values.append(value.strip())
            elif isinstance(value, list):
                values.extend(str(item).strip() for item in value if isinstance(item, (str, int, float)) and str(item).strip())
            elif isinstance(value, dict):
                values.extend(str(item).strip() for item in value.values() if isinstance(item, (str, int, float)) and str(item).strip())
        return list(dict.fromkeys(values))
