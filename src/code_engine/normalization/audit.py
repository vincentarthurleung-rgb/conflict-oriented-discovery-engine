"""Run-scoped append-only entity resolution audit."""

from __future__ import annotations

import json
from pathlib import Path

from code_engine.normalization.candidates import EntityCandidate, EntityResolutionResult


class EntityResolutionAuditWriter:
    def __init__(self, run_dir: str | Path):
        self.artifacts = Path(run_dir) / "artifacts"
        self.artifacts.mkdir(parents=True, exist_ok=True)
        self.candidates_path = self.artifacts / "entity_resolution_candidates.jsonl"
        self.decisions_path = self.artifacts / "entity_resolution_decisions.jsonl"
        self.summary_path = self.artifacts / "entity_resolution_audit.json"

    def write(self, result: EntityResolutionResult, provider_trace: list[dict] | None = None) -> str:
        result.audit_ref = str(self.decisions_path)
        with self.candidates_path.open("a", encoding="utf-8") as handle:
            for candidate in result.candidates:
                handle.write(candidate.model_dump_json() + "\n")
        payload = {**result.model_dump(), "provider_trace": provider_trace or []}
        with self.decisions_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
        decisions = self._read_lines(self.decisions_path)
        statuses, providers = {}, {}
        network_calls = api_calls = 0
        for item in decisions:
            status = item.get("normalization_status", "unknown")
            statuses[status] = statuses.get(status, 0) + 1
            for trace in item.get("provider_trace", []):
                if trace.get("status") in {"not_applicable", "not_needed"}:
                    continue
                name = trace.get("provider_name", "unknown")
                providers[name] = providers.get(name, 0) + 1
                network_calls += int(trace.get("network_calls_made", 0))
                api_calls += int(trace.get("api_calls_made", 0))
        self.summary_path.write_text(json.dumps({"total_mentions": len(decisions), "status_counts": statuses, "provider_usage_counts": providers, "network_calls_made": network_calls, "api_calls_made": api_calls}, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(self.decisions_path)

    @staticmethod
    def _read_lines(path: Path) -> list[dict]:
        records = []
        for line in path.read_text(encoding="utf-8").splitlines() if path.exists() else []:
            try: records.append(json.loads(line))
            except json.JSONDecodeError: pass
        return records
