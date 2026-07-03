"""Small, official-endpoint reachability checks with no scientific interpretation."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

DEFAULT_VALIDATORS = ("reactome", "enrichr", "chembl", "opentargets", "pubmed_post_cutoff", "pmc_oa")


def load_dotenv(path: str | Path = ".env") -> None:
    file = Path(path)
    if not file.is_file(): return
    for line in file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line: continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


class ExternalAPISmokeTester:
    def __init__(self, registry: str | Path, *, network_enabled: bool = False, timeout_seconds: float = 20, max_retries: int = 1, transport: Callable | None = None):
        data = json.loads(Path(registry).read_text(encoding="utf-8"))
        self.registry = {item["validator_id"]: item for item in data.get("validators", [])}
        self.network_enabled, self.timeout, self.max_retries = network_enabled, timeout_seconds, max_retries
        self.transport = transport or self._urlopen

    def run(self, validators=None, case_profile: str | Path | None = None) -> dict[str, Any]:
        selected = list(dict.fromkeys(validators or DEFAULT_VALIDATORS))
        results = {}
        for validator in selected:
            results[validator] = self._run_one(validator)
        statuses = [item["status"] for item in results.values()]
        return {"schema_version": "external_api_smoke_summary_v1", "created_at": datetime.now(timezone.utc).isoformat(), "network_enabled": self.network_enabled, "case_profile": str(case_profile) if case_profile else None, "api_count": len(results), "reachable_count": statuses.count("reachable"), "failed_count": statuses.count("failed"), "skipped_count": statuses.count("skipped"), "results": results}

    def _run_one(self, validator):
        spec = self.registry.get(validator, {})
        endpoint_type = {"pubmed_post_cutoff": "ncbi_eutilities", "pmc_oa": "pmc_oa_service", "reactome": "reactome_content_service", "enrichr": "enrichr", "chembl": "chembl_web_services", "opentargets": "opentargets_graphql"}.get(validator, "unknown")
        production_ready = True if validator == "pmc_oa" else bool(spec.get("runnable_now"))
        base = {"pmc_oa": "https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/"}.get(validator, spec.get("base_url"))
        result = {"validator_id": validator, "api": endpoint_type, "status": "skipped", "endpoint_type": endpoint_type, "endpoint": base, "http_status": None, "production_validator_ready": production_ready, "reason": "Network disabled; no request sent.", "attempt_count": 0}
        if not self.network_enabled: return result
        if validator not in DEFAULT_VALIDATORS or not base:
            result.update(status="skipped", reason="No smoke-test definition or endpoint configured.")
            return result
        try:
            status, payload, attempts = self._request_validator(validator, base)
            self._validate(validator, payload)
            result.update(status="reachable", http_status=status, attempt_count=attempts, reason=self._reason(validator, production_ready))
        except Exception as error:
            result.update(status="failed", attempt_count=getattr(error, "attempt_count", self.max_retries + 1), reason=f"Smoke request failed: {type(error).__name__}: {error}")
        return result

    def _request_validator(self, validator, base):
        if validator == "pubmed_post_cutoff":
            params = {"db": "pubmed", "term": "biomedical mechanism", "retmax": "1", "retmode": "json", "tool": os.getenv("NCBI_TOOL", "conflict_oriented_discovery_engine"), "email": os.getenv("NCBI_EMAIL", "")}
            if os.getenv("NCBI_API_KEY"): params["api_key"] = os.environ["NCBI_API_KEY"]
            return self._request(urllib.request.Request(base.rstrip("/") + "/esearch.fcgi?" + urllib.parse.urlencode(params), headers={"Accept": "application/json"}))
        if validator == "pmc_oa":
            params = urllib.parse.urlencode({"ids": "PMC7096777", "format": "json", "tool": os.getenv("NCBI_TOOL", "conflict_oriented_discovery_engine"), "email": os.getenv("NCBI_EMAIL", "")})
            return self._request(urllib.request.Request(base + "?" + params, headers={"Accept": "application/json"}))
        if validator == "reactome":
            url = base.rstrip("/") + "/data/database/version"
            return self._request(urllib.request.Request(url, headers={"Accept": "text/plain", "User-Agent": "conflict-oriented-discovery-engine/1.0"}))
        if validator == "chembl":
            url = base.rstrip("/") + "/molecule/search.json?" + urllib.parse.urlencode({"q": "rapamycin", "limit": "1"})
            return self._request(urllib.request.Request(url, headers={"Accept": "application/json"}))
        if validator == "opentargets":
            query = '{ search(queryString: "TP53", entityNames: ["target"], page: {index: 0, size: 1}) { total hits { id name entity } } }'
            return self._request(urllib.request.Request(base, data=json.dumps({"query": query}).encode(), headers={"Content-Type": "application/json", "Accept": "application/json"}, method="POST"))
        if validator == "enrichr":
            boundary = "----SystemBSmokeBoundary"
            fields = {"list": "TP53\nEGFR", "description": "System B API smoke test"}
            chunks = []
            for name, value in fields.items():
                chunks.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n")
            body = ("".join(chunks) + f"--{boundary}--\r\n").encode()
            status, payload, attempts = self._request(urllib.request.Request(base.rstrip("/") + "/addList", data=body, headers={"Content-Type": f"multipart/form-data; boundary={boundary}", "Accept": "application/json", "User-Agent": "conflict-oriented-discovery-engine/1.0"}, method="POST"))
            user_list_id = json.loads(payload.decode())["userListId"]
            url = base.rstrip("/") + "/enrich?" + urllib.parse.urlencode({"userListId": user_list_id, "backgroundType": "Reactome_2022"})
            status2, payload2, attempts2 = self._request(urllib.request.Request(url, headers={"Accept": "application/json"}))
            return status2, payload2, attempts + attempts2
        raise ValueError(f"unsupported validator: {validator}")

    def _request(self, request):
        last = None
        for attempt in range(1, self.max_retries + 2):
            try:
                status, payload = self.transport(request, self.timeout)
                if not 200 <= status < 300: raise urllib.error.HTTPError(request.full_url, status, "unexpected status", {}, None)
                return status, payload, attempt
            except Exception as error:
                last = error
                if attempt <= self.max_retries: time.sleep(min(0.2 * attempt, 1.0))
        setattr(last, "attempt_count", self.max_retries + 1)
        raise last

    @staticmethod
    def _urlopen(request, timeout):
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read(1_000_000)

    @staticmethod
    def _validate(validator, payload):
        if validator == "reactome":
            if not payload.decode("utf-8").strip().isdigit(): raise ValueError("response did not contain a Reactome database version")
            return
        value = json.loads(payload.decode("utf-8"))
        valid = {"pubmed_post_cutoff": lambda x: "esearchresult" in x and ("count" in x["esearchresult"] or "idlist" in x["esearchresult"]), "pmc_oa": lambda x: isinstance(x.get("records"), list), "enrichr": lambda x: isinstance(x, dict), "chembl": lambda x: isinstance(x.get("molecules"), list), "opentargets": lambda x: isinstance(x.get("data"), dict) and not x.get("errors")}[validator](value)
        if not valid: raise ValueError("response did not match expected minimal schema")

    @staticmethod
    def _reason(validator, ready):
        if validator == "pmc_oa": return "PMC ID converter reachable; OA-only client is implemented; no full text was downloaded."
        descriptions = {"pubmed_post_cutoff": "post-cutoff validator execution logic", "reactome": "validator mapping/execution", "enrichr": "production mapping from L6/L7 genes", "chembl": "schema-bound case-entity mapping", "opentargets": "target/disease mapping and evidence scoring"}
        return "API reachable; production validator is runnable." if ready else f"API reachable; {descriptions[validator]} still requires implementation."


def write_smoke_reports(summary, output_root):
    root = Path(output_root); root.mkdir(parents=True, exist_ok=True)
    (root / "external_api_smoke_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (root / "external_api_smoke_results.jsonl").write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in summary["results"].values()), encoding="utf-8")
    overlay = {"schema_version": "external_api_smoke_registry_overlay_v1", "created_at": summary["created_at"], "validators": {key: {"smoke_test": {"enabled": True, "last_status": item["status"], "last_checked_at": summary["created_at"], "production_validator_ready": item["production_validator_ready"]}} for key, item in summary["results"].items()}}
    (root / "external_api_smoke_registry_overlay.json").write_text(json.dumps(overlay, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = ["# External API Smoke Test", "", f"- Network enabled: `{str(summary['network_enabled']).lower()}`", f"- Reachable: {summary['reachable_count']}", f"- Failed: {summary['failed_count']}", f"- Skipped: {summary['skipped_count']}", "", "| Validator | API | Status | Production ready | Reason |", "| --- | --- | --- | --- | --- |"]
    lines += [f"| {key} | {item['api']} | {item['status']} | {str(item['production_validator_ready']).lower()} | {item['reason']} |" for key, item in summary["results"].items()]
    (root / "external_api_smoke_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return root
