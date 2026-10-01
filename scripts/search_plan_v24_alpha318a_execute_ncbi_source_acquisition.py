#!/usr/bin/env python3
"""Execute the frozen alpha3.18A.3 NCBI-only source-acquisition manifest.

No provider, scientific extraction, relevance adjudication, or held-out work.
"""

from __future__ import annotations

import hashlib
import json
import re
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from scripts import search_plan_v24_alpha318a1_source_contracts as policy
    from scripts import search_plan_v24_alpha318a2_rebuild_source_prereg_offline as prior
    from scripts import search_plan_v24_alpha318a3_correction_reference as correction
    from scripts import search_plan_v24_alpha318a3_finalize_source_prereg_offline as freeze
except ModuleNotFoundError:
    import search_plan_v24_alpha318a1_source_contracts as policy
    import search_plan_v24_alpha318a2_rebuild_source_prereg_offline as prior
    import search_plan_v24_alpha318a3_correction_reference as correction
    import search_plan_v24_alpha318a3_finalize_source_prereg_offline as freeze


ROOT = prior.ROOT
OUT = ROOT / "runs/20260928_search_plan_v24_dev_alpha3_18a_ncbi_only_source_acquisition"
ES = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EF = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
STRATA = prior.STRATA
ROOT_MARKER = "search_plan_v24_dev_alpha3_18a_sha256"
MANIFEST_SHA = "24632aa9d8b8aca217e6cbb80704e490b8eeeddafd8983bc0e20c2159d9ff924"
PREREG_SHA = "f94bddd105196cd4b3b86144bab9abbad5a24db80e32c3558ac33e8cb92144a3"


def canonical(value: Any) -> bytes:
    return prior.canonical(value)


def sha(raw: bytes) -> str:
    return prior.sha(raw)


def write_json(path: Path, value: Any) -> None:
    if path.exists():
        raise RuntimeError(f"refusing overwrite: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical(value) + b"\n")


def write_jsonl(path: Path, rows: list[Any]) -> None:
    if path.exists():
        raise RuntimeError(f"refusing overwrite: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"".join(canonical(row) + b"\n" for row in rows))


def write_bytes(path: Path, raw: bytes) -> None:
    if path.exists():
        raise RuntimeError(f"refusing overwrite: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)


def marker(name: str, digest: str) -> None:
    write_bytes(OUT / name, (digest + "\n").encode("ascii"))


def root_hash() -> str:
    files = sorted(p for p in OUT.rglob("*") if p.is_file() and p.name != ROOT_MARKER)
    if any(p.is_symlink() for p in OUT.rglob("*")):
        raise RuntimeError("symlink in execution output")
    return sha(canonical([[str(p.relative_to(OUT)), sha(p.read_bytes())] for p in files]))


def verify_before_network() -> dict[str, Any]:
    if prior.all_file_root(freeze.OUT, "search_plan_v24_dev_alpha3_18a3_prereg_sha256") != PREREG_SHA:
        raise RuntimeError("alpha3.18A.3 root mismatch")
    if (freeze.OUT / "search_plan_v24_dev_alpha3_18a3_prereg_sha256").read_text().strip() != PREREG_SHA:
        raise RuntimeError("alpha3.18A.3 marker mismatch")
    path = freeze.OUT / "alpha3_18a3_source_acquisition_execution_manifest.json"
    if sha(path.read_bytes()) != MANIFEST_SHA or (freeze.OUT / "alpha3_18a3_source_acquisition_execution_manifest_sha256").read_text().strip() != MANIFEST_SHA:
        raise RuntimeError("execution manifest mismatch")
    freeze.verify()
    manifest = json.loads(path.read_text(encoding="utf-8"))
    references: list[dict[str, str]] = []
    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if "path" in node and "sha256" in node:
                references.append(node)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)
    walk(manifest)
    for ref in references:
        path = ROOT / ref["path"]
        if not path.is_file() or sha(path.read_bytes()) != ref["sha256"]:
            raise RuntimeError("frozen manifest reference mismatch: " + ref["path"])
    if len(manifest["queries"]) != 6 or manifest["material_runtime_policy_unresolved_count"] != 0:
        raise RuntimeError("manifest completeness mismatch")
    if manifest["network_scope"]["allowed_host"] != "eutils.ncbi.nlm.nih.gov":
        raise RuntimeError("non-NCBI network scope")
    if manifest["authoritative_roots"]["correction_reference_eligibility_v1"] != (
        freeze.OUT / "correction_reference_eligibility_v1_sha256").read_text().strip():
        raise RuntimeError("correction gate mismatch")
    return manifest


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise RuntimeError("NCBI request redirected; fail closed")


class Transport:
    def __init__(self, run: Path, retry_policy: dict[str, Any]):
        self.run = run
        self.retry = retry_policy
        self.opener = urllib.request.build_opener(NoRedirect)
        self.last_started = 0.0
        self.calls = 0
        self.log: list[dict[str, Any]] = []

    def get(self, stage: str, key: str, endpoint: str, params: dict[str, str],
            raw_dir: str) -> tuple[bytes | None, list[dict[str, Any]]]:
        parsed = urllib.parse.urlsplit(endpoint)
        if parsed.scheme != "https" or parsed.hostname != "eutils.ncbi.nlm.nih.gov" or endpoint not in (ES, EF):
            raise RuntimeError("NETWORK_SCOPE_VIOLATION")
        url = endpoint + "?" + urllib.parse.urlencode(params)
        attempts: list[dict[str, Any]] = []
        for attempt in range(1, self.retry["maximum_attempts_per_request"] + 1):
            delay = max(0.0, 0.38 - (time.monotonic() - self.last_started))
            if delay:
                time.sleep(delay)
            self.last_started = time.monotonic()
            self.calls += 1
            request = urllib.request.Request(url, headers={"User-Agent": "conflict-oriented-discovery-engine-alpha318a/1.0"})
            stamp = datetime.now(timezone.utc).isoformat()
            status: int | None = None
            raw = b""
            error: str | None = None
            try:
                with self.opener.open(request, timeout=self.retry["timeout_seconds"]) as response:
                    status = response.status
                    raw = response.read()
            except urllib.error.HTTPError as exc:
                status = exc.code
                raw = exc.read()
                error = type(exc).__name__
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                error = type(exc).__name__ + ":" + str(exc)
            relative = f"{raw_dir}/{key}_attempt{attempt}.bin"
            write_bytes(self.run / relative, raw)
            record = {"stage": stage, "request_key": key, "attempt": attempt,
                      "method": "GET", "endpoint": endpoint, "parameters": params,
                      "url": url, "timestamp_utc": stamp, "status": status,
                      "raw_path": relative, "raw_sha256": sha(raw), "raw_bytes": len(raw),
                      "error": error}
            attempts.append(record)
            self.log.append(record)
            if status == 200 and error is None:
                return raw, attempts
            retryable = status in self.retry["http_status_retryable"] or status is None
            if not retryable or attempt == self.retry["maximum_attempts_per_request"]:
                break
            time.sleep(self.retry["backoff_seconds"][attempt - 1])
        return None, attempts


def parse_esearch(raw: bytes, expected_retstart: int, page_size: int) -> tuple[int, list[str]]:
    data = json.loads(raw)
    result = data["esearchresult"]
    count = int(result["count"])
    if count < 0 or int(result.get("retstart", expected_retstart)) != expected_retstart:
        raise ValueError("ESearch count or retstart mismatch")
    ids = result["idlist"]
    if not isinstance(ids, list) or len(ids) > page_size:
        raise ValueError("ESearch idlist invalid")
    canonical_ids = []
    for value in ids:
        if not isinstance(value, str) or not re.fullmatch(r"[1-9][0-9]*", value):
            raise ValueError("ESearch PMID invalid")
        canonical_ids.append(value)
    return count, canonical_ids


def parse_metadata(raw: bytes, sampled_pmid: str) -> dict[str, Any]:
    root = ET.fromstring(raw)
    articles = [node for node in root.iter() if policy.local(node.tag) == "PubmedArticle"]
    if len(articles) != 1:
        raise ValueError("metadata EFetch must contain one PubmedArticle")
    article = articles[0]
    citation = next((n for n in article if policy.local(n.tag) == "MedlineCitation"), None)
    if citation is None:
        raise ValueError("MedlineCitation missing")
    pmids = [policy.node_text(n) for n in citation if policy.local(n.tag) == "PMID"]
    if pmids != [sampled_pmid]:
        raise ValueError("sampled PMID identity mismatch")
    pubmed_data = next((n for n in article if policy.local(n.tag) == "PubmedData"), None)
    ids = [] if pubmed_data is None else [(n.attrib.get("IdType"), policy.node_text(n))
        for n in pubmed_data.iter() if policy.local(n.tag) == "ArticleId"]
    pmcids = sorted({value for kind, value in ids if kind == "pmc"})
    dois = sorted({value for kind, value in ids if kind == "doi"})
    if len(pmcids) != 1 or not re.fullmatch(r"PMC[1-9][0-9]*", pmcids[0]):
        raise ValueError("PMCID missing or ambiguous")
    if len(dois) > 1:
        raise ValueError("DOI ambiguous")
    years = set()
    source_article = next((n for n in citation if policy.local(n.tag) == "Article"), None)
    if source_article is None:
        raise ValueError("Article metadata missing")
    for node in source_article.iter():
        name = policy.local(node.tag)
        if name not in {"PubDate", "ArticleDate"}:
            continue
        for date_node in node.iter():
            part_name = policy.local(date_node.tag)
            if part_name == "Year" and date_node.text and re.fullmatch(r"[0-9]{4}", date_node.text.strip()):
                years.add(int(date_node.text.strip()))
            elif part_name == "MedlineDate" and date_node.text:
                years.update(int(value) for value in re.findall(r"\b(?:19|20)[0-9]{2}\b", date_node.text))
    if len(years) != 1 or not (2018 <= next(iter(years)) <= 2023):
        raise ValueError("publication date/year ambiguous or out of frozen window")
    extracted = correction.parse_pubmed_relationships(raw)
    return {"pmid": sampled_pmid, "pmcid": pmcids[0], "doi": dois[0] if dois else None,
            "publication_year": next(iter(years)), "publication_types": extracted["publication_types"],
            "correction_relationships": extracted["relationships"]}


def preliminary_type(types: list[str]) -> dict[str, Any]:
    found = set(types)
    if not found:
        return {"state": "SOURCE_TYPE_UNRESOLVED", "reason": "PUBLICATION_TYPES_MISSING"}
    excluded = sorted(found & policy.EXCLUDED_PUBLICATION_TYPES)
    if excluded:
        return {"state": "SOURCE_TYPE_INELIGIBLE", "reason": "EXCLUDED_PUBLICATION_TYPE", "matched": excluded}
    unknown = sorted(found - policy.LOCAL_PUBLICATION_TYPES)
    if unknown:
        return {"state": "SOURCE_TYPE_UNRESOLVED", "reason": "UNRECOGNIZED_PUBLICATION_TYPE", "matched": unknown}
    if not found & policy.ACCEPTED_PUBLICATION_TYPES:
        return {"state": "SOURCE_TYPE_UNRESOLVED", "reason": "POSITIVE_PUBLICATION_TYPE_ABSENT"}
    return {"state": "PRELIMINARY_TYPE_ACCEPTED", "reason": "POSITIVE_TYPE_NO_EXCLUSION"}


def parse_subset(raw: bytes, pmcid: str) -> bool | None:
    try:
        result = json.loads(raw)["esearchresult"]
        count = int(result["count"])
        ids = result["idlist"]
        numeric = pmcid[3:]
        if count == 0 and ids == []:
            return False
        if ids == [numeric]:
            return True
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        pass
    return None


def canonical_article(raw: bytes, pmcid: str) -> bytes:
    root = ET.fromstring(raw)
    articles = [n for n in root.iter() if policy.local(n.tag) == "article"]
    if len(articles) != 1:
        raise ValueError("exactly one PMC article required")
    article = articles[0]
    article_ids = [(n.attrib.get("pub-id-type", "").casefold(), policy.node_text(n))
                   for n in article.iter() if policy.local(n.tag) == "article-id"]
    supported = {value if value.startswith("PMC") else "PMC" + value
                 for kind, value in article_ids if kind in {"pmc", "pmcid"}}
    if pmcid not in supported:
        raise ValueError("PMC JATS identity mismatch")
    return ET.tostring(article, encoding="utf-8")


def visible_audit(document: dict[str, Any], jats_xml: bytes, metadata: dict[str, Any],
                  queries: list[dict[str, Any]]) -> dict[str, Any]:
    visible = document["abstract_text"] + "\n" + document["body_text"]
    root = ET.fromstring(jats_xml)
    title_node = next((n for n in root.iter() if policy.local(n.tag) == "article-title"), None)
    title = policy.node_text(title_node) if title_node is not None else ""
    issues: list[str] = []
    if title and len(title) >= 30 and title.casefold() in visible.casefold():
        issues.append("ARTICLE_TITLE_IN_VISIBLE_TEXT")
    for field in ("pmid", "pmcid", "doi"):
        value = metadata.get(field)
        if value and re.search(r"(?<![A-Za-z0-9])" + re.escape(value) + r"(?![A-Za-z0-9])", visible, re.I):
            issues.append(field.upper() + "_IN_VISIBLE_TEXT")
    if any(q["query_utf8"] in visible for q in queries):
        issues.append("FROZEN_QUERY_IN_VISIBLE_TEXT")
    if re.search(r"\bheldout_v[0-9]+_|SearchConstraintAllocationV1|BoundedLexicalRealizationV2|\bP[012]\s*(?:gate|policy)\b", visible, re.I):
        issues.append("DEVELOPMENT_OR_SEARCH_STATE_IN_VISIBLE_TEXT")
    if document.get("article_title_visible") is not False or document.get("bibliography_visible") is not False:
        issues.append("DOCUMENT_VISIBILITY_FLAGS_INVALID")
    return {"pass": not issues, "issues": issues}


def final_root_and_status(status: str, failure_code: str | None, counts: dict[str, Any],
                          transport: Transport | None) -> str:
    safety = {"builder_calls": 0, "quality_calls": 0, "deepseek_calls": 0,
              "openai_calls": 0, "llm_calls": 0, "non_ncbi_network_calls": 0,
              "ncbi_network_attempts": transport.calls if transport else 0,
              "scientific_propositions_generated": 0, "historical_assets_modified": False}
    write_json(OUT / "scientific_state_safety_audit.json", safety)
    write_json(OUT / "validation.json", {"status": status, "failure_code": failure_code,
        "authoritative_execution_manifest_verified": True, "source_query_changes": 0,
        "network_scope_ncbi_only": True, "six_source_frames_frozen": counts.get("source_frames_completed", 0) == 6,
        "dynamic_source_replacement_used": False, **safety})
    write_json(OUT / "summary.json", {"status": "completed" if status == "PASS" else "failed",
        "failure_code": failure_code, **counts,
        "next_stage_recommendation": "PREREGISTER_ALPHA3_18B_BUILDER_EXECUTION_AUTHORIZATION" if status == "PASS"
        else "AUDIT_ALPHA3_18A_RUNTIME_FAILURE_OFFLINE",
        "network_execution_finished": True, "builder_executed": False})
    root = root_hash()
    marker(ROOT_MARKER, root)
    return root


def main() -> None:
    if OUT.exists():
        raise RuntimeError("execution directory already exists; never rerun frozen source acquisition")
    manifest = verify_before_network()
    OUT.mkdir()
    write_json(OUT / "authoritative_manifest_verification.json", {
        "prereg_root_sha256": PREREG_SHA, "manifest_sha256": MANIFEST_SHA,
        "referenced_contracts_verified_before_network": True,
        "query_count": 6, "source_query_changes": 0})
    source_policy = prior.load(prior.SOURCE, "source_execution_policy.json")
    transport = Transport(OUT, source_policy)
    counts: dict[str, Any] = {"source_frames_completed": 0, "raw_source_records": 0,
        "deduplicated_source_records": 0, "sampled_source_count": 0}
    try:
        run(manifest, transport, counts)
    except Exception as exc:
        write_jsonl(OUT / "ncbi_transport_attempts.jsonl", transport.log)
        root = final_root_and_status("FAILED_CLOSED", type(exc).__name__ + ":" + str(exc), counts, transport)
        print(json.dumps({"status": "failed_closed", "failure": type(exc).__name__ + ":" + str(exc),
                          "run_root": root, **counts}, sort_keys=True))
        return
    write_jsonl(OUT / "ncbi_transport_attempts.jsonl", transport.log)
    root = final_root_and_status("PASS", None, counts, transport)
    print(json.dumps({"status": "completed", "run_root": root, **counts}, sort_keys=True))


def run(manifest: dict[str, Any], transport: Transport, counts: dict[str, Any]) -> None:
    queries = manifest["queries"]
    requests = [{"stratum_id": q["stratum_id"], "query_sha256": q["query_sha256"],
                 "page_retstart": offset, "endpoint": ES,
                 "parameters": {"db": "pubmed", "retmode": "json", "sort": "relevance",
                                "retmax": "50", "retstart": str(offset), "term": q["query_utf8"]}}
                for q in queries for offset in (0, 50, 100, 150)]
    write_jsonl(OUT / "source_query_request_manifest.jsonl", requests)
    frame_rows: list[dict[str, Any]] = []
    query_results: list[dict[str, Any]] = []
    for q in queries:
        seen: set[str] = set()
        raw_order: list[str] = []
        page_records = []
        for offset in (0, 50, 100, 150):
            params = {"db": "pubmed", "retmode": "json", "sort": "relevance", "retmax": "50",
                      "retstart": str(offset), "term": q["query_utf8"]}
            key = f"{q['stratum_order']:02d}_{offset:03d}"
            raw, attempts = transport.get("SOURCE_FRAME", key, ES, params, "source_query_raw_responses")
            if raw is None:
                query_results.append({"stratum_id": q["stratum_id"], "retstart": offset,
                                      "status": "TERMINAL_TECHNICAL_FAILURE", "attempts": attempts})
                write_jsonl(OUT / "source_query_execution_results.jsonl", query_results)
                raise RuntimeError("SOURCE_FRAME_ACQUISITION_FAILED_CLOSED")
            try:
                count, ids = parse_esearch(raw, offset, 50)
            except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
                query_results.append({"stratum_id": q["stratum_id"], "retstart": offset,
                                      "status": "INVALID_RESPONSE", "error": str(exc), "attempts": attempts})
                write_jsonl(OUT / "source_query_execution_results.jsonl", query_results)
                raise RuntimeError("SOURCE_FRAME_ACQUISITION_FAILED_CLOSED") from exc
            raw_order.extend(ids)
            page_records.append({"retstart": offset, "count": count, "pmids": ids,
                                 "response_sha256": sha(raw), "attempts": attempts})
            query_results.append({"stratum_id": q["stratum_id"], "retstart": offset,
                                  "status": "COMPLETE", "returned": len(ids), "count": count,
                                  "raw_response_sha256": sha(raw), "attempts": attempts})
            if len(ids) < 50 or offset + len(ids) >= count:
                break
        ordered = []
        for pmid in raw_order:
            if pmid not in seen:
                seen.add(pmid)
                ordered.append(pmid)
        frame = {"stratum_id": q["stratum_id"], "query_sha256": q["query_sha256"],
                 "raw_pmid_order": raw_order, "ordered_unique_pmids": ordered,
                 "page_records": page_records, "status": "COMPLETE"}
        write_json(OUT / "six_source_frame_manifests" / f"{q['stratum_order']:02d}_{q['stratum_id']}.json", frame)
        frame_rows.append(frame)
        counts["source_frames_completed"] += 1
        counts["raw_source_records"] += len(raw_order)
        print(json.dumps({"stage": "source_frame", "completed": counts["source_frames_completed"],
                          "stratum": q["stratum_id"], "raw": len(raw_order), "unique": len(ordered)}), flush=True)
    write_jsonl(OUT / "source_query_execution_results.jsonl", query_results)
    frame_paths = sorted((OUT / "six_source_frame_manifests").glob("*.json"))
    marker("six_source_frames_sha256", sha(canonical([[p.name, sha(p.read_bytes())] for p in frame_paths])))
    membership: dict[str, list[str]] = {}
    for frame in frame_rows:
        for pmid in frame["ordered_unique_pmids"]:
            membership.setdefault(pmid, []).append(frame["stratum_id"])
    sampling_frame = []
    for frame in frame_rows:
        stratum = frame["stratum_id"]
        for position, pmid in enumerate(frame["ordered_unique_pmids"]):
            if membership[pmid][0] == stratum:
                sampling_frame.append({"pmid": pmid, "owner_stratum": stratum,
                                       "owner_frame_position": position, "all_strata": membership[pmid]})
    write_json(OUT / "cross_stratum_duplicate_audit.json", {
        "raw_frame_records": counts["raw_source_records"], "canonical_unique_pmids": len(sampling_frame),
        "cross_stratum_duplicate_pmids": sum(len(v) > 1 for v in membership.values()),
        "earliest_stratum_owner": True, "all_memberships_preserved": True})
    write_jsonl(OUT / "new_pool_source_sampling_frame.jsonl", sampling_frame)
    marker("new_pool_source_sampling_frame_sha256", sha((OUT / "new_pool_source_sampling_frame.jsonl").read_bytes()))
    counts["deduplicated_source_records"] = len(sampling_frame)
    seed = prior.load(prior.SOURCE, "source_sampling_algorithm.json")["seed_sha256"]
    sampled = []
    for stratum in STRATA:
        owned = [row for row in sampling_frame if row["owner_stratum"] == stratum]
        for row in owned:
            preimage = f"{seed}:{stratum}:{row['pmid']}".encode("utf-8")
            row["sample_key_sha256"] = sha(preimage)
        selected = sorted(owned, key=lambda row: (bytes.fromhex(row["sample_key_sha256"]), int(row["pmid"])))[:12]
        sampled.extend({**row, "sample_rank_in_stratum": i + 1} for i, row in enumerate(selected))
    # The canonical frame was frozen before assigning keyed sample hashes.
    write_jsonl(OUT / "deterministic_source_sampling_results.jsonl", sampled)
    write_json(OUT / "source_sampling_summary.json", {"sample_count": len(sampled),
        "per_stratum": {s: sum(row["owner_stratum"] == s for row in sampled) for s in STRATA},
        "seed_sha256": seed, "no_replacement": True, "six_frame_barrier_passed": True})
    counts["sampled_source_count"] = len(sampled)
    print(json.dumps({"stage": "sampling", "unique_frame": len(sampling_frame),
                      "sampled": len(sampled)}), flush=True)
    finish_sampled_sources(manifest, transport, counts, sampled)


def finish_sampled_sources(manifest: dict[str, Any], transport: Transport,
                           counts: dict[str, Any], sampled: list[dict[str, Any]]) -> None:
    registry = prior.load(prior.SOURCE, "seen_source_local_registry.json")
    seen_hashes = set(registry["hashed_pmcids"])
    metadata_requests: list[dict[str, Any]] = []
    metadata_records: list[dict[str, Any]] = []
    seen_records: list[dict[str, Any]] = []
    correction_records: list[dict[str, Any]] = []
    oa_records: list[dict[str, Any]] = []
    type_records: list[dict[str, Any]] = []
    exclusion_records: list[dict[str, Any]] = []
    fulltext_requests: list[dict[str, Any]] = []
    fulltext_results: list[dict[str, Any]] = []
    fulltext_failures: list[dict[str, Any]] = []
    documents: list[dict[str, Any]] = []
    anchors: list[dict[str, Any]] = []
    construction: list[dict[str, Any]] = []
    vault: list[dict[str, Any]] = []
    builder_requests: list[dict[str, Any]] = []
    visibility_records: list[dict[str, Any]] = []
    output_schema = prior.load(prior.BUILDER, "proposition_builder_output_schema_v2.json")["schema"]
    builder_protocol = prior.load(prior.BUILDER, "proposition_builder_protocol_v2.json")
    user_template = (prior.AMEND / "proposition_builder_v2_1_user_prompt_template.txt").read_text(encoding="utf-8")
    system_prompt = builder_protocol["system_prompt_utf8"]
    write_jsonl(OUT / "sampled_source_metadata_manifest.jsonl", [
        {"pmid": row["pmid"], "endpoint": EF,
         "parameters": {"db": "pubmed", "retmode": "xml", "id": row["pmid"]}}
        for row in sampled])
    for index, selected in enumerate(sampled, 1):
        pmid = selected["pmid"]
        source_key = f"{index:03d}_{pmid}"
        reasons: list[str] = []
        params = {"db": "pubmed", "retmode": "xml", "id": pmid}
        metadata_requests.append({"pmid": pmid, "endpoint": EF, "parameters": params})
        raw, attempts = transport.get("SAMPLED_METADATA", source_key, EF, params,
                                      "sampled_metadata_raw_responses")
        meta: dict[str, Any] | None = None
        try:
            if raw is not None:
                meta = parse_metadata(raw, pmid)
        except (ET.ParseError, ValueError, TypeError) as exc:
            reasons.append("METADATA_UNRESOLVED:" + str(exc))
        if meta is None and not reasons:
            reasons.append("METADATA_TRANSPORT_UNRESOLVED")
        metadata_records.append({"pmid": pmid, "metadata": meta, "raw_sha256": sha(raw) if raw else None,
                                 "attempts": attempts, "state": "RESOLVED" if meta else "UNRESOLVED"})
        if meta is None:
            seen_records.append({"pmid": pmid, "state": "SOURCE_IDENTITY_UNRESOLVED"})
            correction_records.append({"pmid": pmid, "state": "CORRECTION_REFERENCE_UNRESOLVED",
                                       "reason": "METADATA_UNAVAILABLE"})
            oa_records.append({"pmid": pmid, "state": "CONSTRUCTION_OA_UNRESOLVED", "reason": "METADATA_UNAVAILABLE"})
            type_records.append({"pmid": pmid, "state": "SOURCE_TYPE_UNRESOLVED", "reason": "METADATA_UNAVAILABLE"})
            exclusion_records.append({"pmid": pmid, "terminal": "EXCLUDED", "reasons": reasons})
            continue
        seen_hash = sha((registry["hash_domain"] + meta["pmcid"]).encode("utf-8"))
        seen_state = "MATCHED_FROZEN_SEEN_SOURCE" if seen_hash in seen_hashes else "NO_FROZEN_LOCAL_MATCH"
        seen_records.append({"pmid": pmid, "pmcid": meta["pmcid"], "state": seen_state,
                             "registry_sha256": sha((prior.SOURCE / "seen_source_local_registry.json").read_bytes())})
        if seen_state == "MATCHED_FROZEN_SEEN_SOURCE":
            reasons.append(seen_state)
        preliminary = preliminary_type(meta["publication_types"])
        if preliminary["state"] != "PRELIMINARY_TYPE_ACCEPTED":
            reasons.append("PUBLICATION_TYPE:" + preliminary["reason"])
        correction_result = correction.classify(meta["publication_types"], meta["correction_relationships"])
        correction_records.append({"pmid": pmid, "snapshot_sha256": sha(raw),
                                   "result": correction_result, "phase": "PRELIMINARY"})
        conditional_update_only = correction_result["state"] == "CORRECTION_REFERENCE_UNRESOLVED" and (
            correction_result["unresolved_reasons"] == ["REF_TYPE:UpdateOf:INDEPENDENT_SOURCE_NOT_YET_ELIGIBLE"])
        if correction_result["state"] != "CORRECTION_REFERENCE_CLEAR" and not conditional_update_only:
            reasons.append(correction_result["state"])
        if reasons:
            oa_records.append({"pmid": pmid, "state": "NOT_CHECKED_AFTER_PRELIMINARY_EXCLUSION"})
            type_records.append({"pmid": pmid, "state": preliminary["state"], "phase": "PRELIMINARY"})
            exclusion_records.append({"pmid": pmid, "terminal": "EXCLUDED", "reasons": reasons})
            continue
        pmcid = meta["pmcid"]
        oa_term = policy.oa_subset_esearch_term(pmcid)
        oa_params = {"db": "pmc", "retmode": "json", "retmax": "1", "term": oa_term}
        oa_raw, oa_attempts = transport.get("PMC_OA_SUBSET", source_key, ES, oa_params,
                                             "pmc_oa_raw_responses")
        subset = parse_subset(oa_raw, pmcid) if oa_raw else None
        if subset is not True:
            oa_state = "CONSTRUCTION_OA_INELIGIBLE" if subset is False else "CONSTRUCTION_OA_UNRESOLVED"
            oa_records.append({"pmid": pmid, "pmcid": pmcid, "state": oa_state,
                               "subset_result": subset, "attempts": oa_attempts})
            type_records.append({"pmid": pmid, "state": "NOT_CHECKED_NO_JATS"})
            exclusion_records.append({"pmid": pmid, "terminal": "EXCLUDED", "reasons": [oa_state]})
            continue
        ft_params = {"db": "pmc", "retmode": "xml", "id": pmcid[3:]}
        fulltext_requests.append({"pmid": pmid, "pmcid": pmcid, "endpoint": EF, "parameters": ft_params})
        ft_raw, ft_attempts = transport.get("PMC_JATS", source_key, EF, ft_params,
                                            "construction_fulltext_raw_responses")
        jats: bytes | None = None
        if ft_raw is not None:
            try:
                jats = canonical_article(ft_raw, pmcid)
            except (ET.ParseError, ValueError) as exc:
                fulltext_failures.append({"pmid": pmid, "pmcid": pmcid, "reason": str(exc),
                                          "raw_sha256": sha(ft_raw)})
        else:
            fulltext_failures.append({"pmid": pmid, "pmcid": pmcid, "reason": "TERMINAL_TRANSPORT_FAILURE",
                                      "attempts": ft_attempts})
        if jats is not None:
            write_bytes(OUT / "construction_fulltext_canonical_jats" / f"{source_key}.xml", jats)
        fulltext_results.append({"pmid": pmid, "pmcid": pmcid, "success": jats is not None,
                                 "raw_sha256": sha(ft_raw) if ft_raw else None,
                                 "canonical_jats_sha256": sha(jats) if jats else None,
                                 "attempts": ft_attempts})
        oa_decision = policy.construction_oa_state(pmcid, True, jats)
        oa_records.append({"pmid": pmid, "pmcid": pmcid, "subset_result": True,
                           "state": oa_decision["state"], "decision": oa_decision,
                           "subset_attempts": oa_attempts})
        if oa_decision["state"] != "CONSTRUCTION_OA_ELIGIBLE":
            type_records.append({"pmid": pmid, "state": "NOT_CHECKED_OA_NOT_ELIGIBLE"})
            exclusion_records.append({"pmid": pmid, "terminal": "EXCLUDED", "reasons": [oa_decision["state"]]})
            continue
        assert jats is not None
        type_decision = policy.source_type_state(meta["publication_types"], jats)
        type_records.append({"pmid": pmid, "state": type_decision["state"], "decision": type_decision})
        final_correction = correction.classify(meta["publication_types"], meta["correction_relationships"],
                                               type_decision["state"])
        correction_records[-1]["final_result"] = final_correction
        if type_decision["state"] != "SOURCE_TYPE_ELIGIBLE":
            reasons.append(type_decision["state"])
        if final_correction["state"] != "CORRECTION_REFERENCE_CLEAR":
            reasons.append(final_correction["state"])
        if reasons:
            exclusion_records.append({"pmid": pmid, "terminal": "EXCLUDED", "reasons": reasons})
            continue
        token = "src_" + secrets.token_hex(32)
        write_json(OUT / "private_anchor_vault_source_tokens" / f"{source_key}.json", {
            "source_token": token, "pmid": pmid, "pmcid": pmcid, "doi": meta["doi"],
            "created_before_document_generation": True})
        try:
            document = policy.build_construction_document(jats, token)
            visibility = visible_audit(document, jats, meta, manifest["queries"])
            if not visibility["pass"]:
                raise ValueError("BUILDER_VISIBILITY_FIREWALL_INCOMPLETE:" + ",".join(visibility["issues"]))
            body = document["body_text"]
            for paragraph in document["paragraphs"]:
                if body[paragraph["start_offset"]:paragraph["end_offset"]] != paragraph["text"]:
                    raise ValueError("evidence span offset mismatch")
                expected_span = "spanv1_" + policy.digest([policy.SPAN_VERSION, token,
                    paragraph["section_path"], paragraph["ordinal"], policy.sha_text(paragraph["text"])])
                if paragraph["span_id"] != expected_span:
                    raise ValueError("evidence span hash mismatch")
        except (ValueError, ET.ParseError) as exc:
            visibility_records.append({"pmid": pmid, "pass": False, "reason": str(exc)})
            exclusion_records.append({"pmid": pmid, "terminal": "EXCLUDED", "reasons": [str(exc)]})
            continue
        doc_path = OUT / "construction_evidence_documents" / f"{token}.json"
        write_json(doc_path, document)
        doc_sha = sha(doc_path.read_bytes())
        visible_prompt = user_template.format(source_record_token=token,
            frozen_abstract=document["abstract_text"], frozen_body=document["body_text"],
            output_schema_json=json.dumps(output_schema, sort_keys=True, ensure_ascii=False, separators=(",", ":")))
        if meta["pmid"] in visible_prompt or meta["pmcid"] in visible_prompt or (
            meta["doi"] and meta["doi"] in visible_prompt):
            raise RuntimeError("BUILDER_VISIBILITY_FIREWALL_INCOMPLETE")
        request = {"model": "deepseek-v4-pro", "thinking": {"type": "enabled"},
                   "reasoning_effort": "high", "response_format": {"type": "json_object"},
                   "messages": [{"role": "system", "content": system_prompt},
                                {"role": "user", "content": visible_prompt}]}
        documents.append({"source_token": token, "document_path": str(doc_path.relative_to(OUT)),
                          "document_sha256": doc_sha, "paragraph_count": len(document["paragraphs"])})
        anchors.extend({"source_token": token, "span_id": p["span_id"],
                        "section_path": p["section_path"], "ordinal": p["ordinal"],
                        "text_sha256": policy.sha_text(p["text"]),
                        "start_offset": p["start_offset"], "end_offset": p["end_offset"]}
                       for p in document["paragraphs"])
        vault.append({"source_token": token, "pmid": pmid, "pmcid": pmcid, "doi": meta["doi"],
                      "stratum": selected["owner_stratum"], "all_strata": selected["all_strata"],
                      "metadata_sha256": sha(raw), "jats_sha256": sha(jats), "document_sha256": doc_sha})
        construction.append({"source_token": token, "stratum": selected["owner_stratum"],
                             "sample_rank_in_stratum": selected["sample_rank_in_stratum"],
                             "document_path": str(doc_path.relative_to(OUT)), "document_sha256": doc_sha})
        builder_requests.append({"source_token": token, "request": request,
                                 "request_sha256": sha(canonical(request)), "document_sha256": doc_sha})
        visibility_records.append({"source_token": token, "pass": True, "issues": []})
        exclusion_records.append({"pmid": pmid, "terminal": "CONSTRUCTION_SOURCE_ELIGIBLE", "reasons": []})
        if index % 10 == 0:
            print(json.dumps({"stage": "sampled_sources", "processed": index,
                              "total": len(sampled), "construction_sources": len(construction)}), flush=True)
    write_jsonl(OUT / "sampled_source_metadata_records.jsonl", metadata_records)
    write_json(OUT / "seen_source_overlap_audit.json", {"registry_sha256": sha((prior.SOURCE / "seen_source_local_registry.json").read_bytes()),
        "records": seen_records, "matched_count": sum(r["state"] == "MATCHED_FROZEN_SEEN_SOURCE" for r in seen_records),
        "NO_FROZEN_LOCAL_MATCH_is_not_global_unseen": True})
    write_jsonl(OUT / "correction_reference_eligibility_results.jsonl", correction_records)
    write_jsonl(OUT / "construction_pmc_eligibility_results.jsonl", oa_records)
    write_jsonl(OUT / "source_type_mechanical_eligibility_results.jsonl", type_records)
    write_jsonl(OUT / "mechanical_source_exclusion_results.jsonl", exclusion_records)
    write_jsonl(OUT / "construction_fulltext_request_manifest.jsonl", fulltext_requests)
    write_jsonl(OUT / "construction_fulltext_acquisition_results.jsonl", fulltext_results)
    write_jsonl(OUT / "construction_fulltext_failure_records.jsonl", fulltext_failures)
    write_jsonl(OUT / "construction_evidence_document_manifest.jsonl", documents)
    write_jsonl(OUT / "construction_span_anchor_manifest.jsonl", anchors)
    write_jsonl(OUT / "construction_source_manifest.jsonl", construction)
    marker("construction_source_manifest_sha256", sha((OUT / "construction_source_manifest.jsonl").read_bytes()))
    write_jsonl(OUT / "private_anchor_vault_source_manifest.jsonl", vault)
    write_json(OUT / "builder_visibility_preflight_audit.json", {"records": visibility_records,
        "failed_count": sum(not x["pass"] for x in visibility_records), "identity_leakage_allowed": False})
    write_jsonl(OUT / "proposition_builder_v2_request_manifest.jsonl", builder_requests)
    marker("proposition_builder_v2_request_manifest_sha256", sha((OUT / "proposition_builder_v2_request_manifest.jsonl").read_bytes()))
    if len(construction) != len(builder_requests) or len(construction) > 72:
        raise RuntimeError("builder request count mismatch")
    write_json(OUT / "actual_builder_call_budget.json", {"actual_builder_scientific_call_count": len(construction),
        "construction_source_count": len(construction), "builder_request_count": len(builder_requests),
        "maximum": 72, "builder_calls_executed": 0})
    counts.update({"seen_source_exclusions": sum(x["state"] == "MATCHED_FROZEN_SEEN_SOURCE" for x in seen_records),
        "publication_type_ineligible": sum(x["state"] == "SOURCE_TYPE_INELIGIBLE" for x in type_records),
        "publication_type_unresolved": sum(x["state"] == "SOURCE_TYPE_UNRESOLVED" for x in type_records),
        "correction_reference_clear": sum((x.get("final_result") or x.get("result") or x).get("state") == "CORRECTION_REFERENCE_CLEAR" for x in correction_records),
        "correction_reference_ineligible": sum((x.get("final_result") or x.get("result") or x).get("state") == "CORRECTION_REFERENCE_INELIGIBLE" for x in correction_records),
        "correction_reference_unresolved": sum((x.get("final_result") or x.get("result") or x).get("state") == "CORRECTION_REFERENCE_UNRESOLVED" for x in correction_records),
        "construction_oa_eligible": sum(x["state"] == "CONSTRUCTION_OA_ELIGIBLE" for x in oa_records),
        "construction_oa_ineligible": sum(x["state"] == "CONSTRUCTION_OA_INELIGIBLE" for x in oa_records),
        "construction_oa_unresolved": sum(x["state"] == "CONSTRUCTION_OA_UNRESOLVED" for x in oa_records),
        "pmc_jats_requested": len(fulltext_requests), "pmc_jats_success": sum(x["success"] for x in fulltext_results),
        "pmc_jats_failed": sum(not x["success"] for x in fulltext_results),
        "source_type_eligible": sum(x["state"] == "SOURCE_TYPE_ELIGIBLE" for x in type_records),
        "source_type_ineligible": sum(x["state"] == "SOURCE_TYPE_INELIGIBLE" for x in type_records),
        "source_type_unresolved": sum(x["state"] == "SOURCE_TYPE_UNRESOLVED" for x in type_records),
        "construction_document_valid": len(documents),
        "construction_document_invalid": sum(not x["pass"] for x in visibility_records),
        "construction_document_unresolved": 0, "construction_source_count": len(construction),
        "actual_builder_scientific_call_count": len(construction),
        "builder_request_manifest_frozen": True, "builder_request_count": len(builder_requests)})
    write_json(OUT / "source_phase_completion_barrier.json", {"six_source_frames_frozen": True,
        "sampling_after_all_frames": True, "construction_source_manifest_frozen": True,
        "builder_request_manifest_frozen": True, "builder_calls_executed": 0,
        "actual_builder_scientific_call_count": len(construction)})
    write_json(OUT / "provenance_completeness_audit.json", {"status": "PASS",
        "sampled_metadata_records": len(metadata_records), "sampled_sources": len(sampled),
        "raw_ncbi_attempts": transport.calls, "raw_NCBI_attempts_preserved": True,
        "construction_source_count": len(construction), "private_vault_count": len(vault)})
    write_json(OUT / "development_nonuse_audit.json", {"development_labels_used_for_source_selection": False,
        "known_pmid_recovery_checks": 0, "scientific_content_used_for_sampling": False})
    write_json(OUT / "search_plan_firewall_audit.json", {"search_plan_queries_executed": 0,
        "planner_calls": 0, "heldout_selected": 0, "P0_P1_P2_calls": 0,
        "private_anchor_vault_not_public_pool": True})
    write_json(OUT / "protocol_compliance_audit.json", {"status": "PASS", "query_changes": 0,
        "publication_type_rules_modified": False, "correction_reference_rules_modified": False,
        "oa_policy_modified": False, "license_policy_modified": False,
        "source_type_rules_modified": False, "construction_document_rules_modified": False,
        "anchor_rules_modified": False, "dynamic_source_replacement_used": False,
        "six_source_frames_frozen": True, "sampled_after_frame_freeze": True})


if __name__ == "__main__":
    main()
