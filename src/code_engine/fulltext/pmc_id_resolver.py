from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from urllib.parse import urlencode
from urllib.request import urlopen


IDCONV_URL = "https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/"
_PMCID_RE = re.compile(r"^PMC[0-9]+$", re.IGNORECASE)


@dataclass(frozen=True)
class PmcidVerificationResult:
    pmcid: str
    expected_pmid: str
    observed_pmid: str | None
    status: str
    source: str
    reason: str

    def to_dict(self) -> dict:
        return asdict(self)


def _request(identifier: str, transport: Callable[[str], dict] | None) -> dict:
    url = IDCONV_URL + "?" + urlencode({"ids": identifier, "format": "json", "tool": "code_engine"})
    if transport:
        return transport(url)
    with urlopen(url, timeout=30) as response:
        return json.load(response)


def _record_for_identifier(payload: dict, identifier: str) -> dict:
    """Select by identifier, never by response position."""
    records = payload.get("records") or []
    wanted = identifier.upper()
    for record in records:
        values = (record.get("pmcid"), record.get("pmid"), record.get("doi"), record.get("requested-id"))
        if any(str(value or "").upper() == wanted for value in values):
            return record
    return records[0] if len(records) == 1 else {}


def verify_pmcid_maps_to_pmid(
    pmcid: str,
    expected_pmid: str,
    *,
    network_enabled: bool = False,
    cache_dir: str | Path | None = None,
    transport: Callable[[str], dict] | None = None,
) -> PmcidVerificationResult:
    normalized = str(pmcid or "").strip().upper()
    expected = str(expected_pmid or "").strip()
    if not _PMCID_RE.fullmatch(normalized):
        return PmcidVerificationResult(normalized, expected, None, "invalid_format", "cached" if cache_dir else "ncbi_idconv", "PMCID must match PMC followed by digits")
    if not expected:
        return PmcidVerificationResult(normalized, expected, None, "missing", "ncbi_idconv", "candidate has no PMID to verify against")

    cache_path = Path(cache_dir) / f"verify_{normalized}.json" if cache_dir else None
    if cache_path and cache_path.is_file():
        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            observed = str(cached.get("observed_pmid") or "").strip() or None
            status = "verified" if observed == expected else "mismatch" if observed else "missing"
            return PmcidVerificationResult(normalized, expected, observed, status, "cached", cached.get("reason") or "cached NCBI idconv mapping")
        except (OSError, json.JSONDecodeError):
            pass
    if not network_enabled:
        return PmcidVerificationResult(normalized, expected, None, "network_unavailable", "ncbi_idconv", "network verification disabled and no cached mapping exists")
    try:
        record = _record_for_identifier(_request(normalized, transport), normalized)
        observed = str(record.get("pmid") or "").strip() or None
        status = "verified" if observed == expected else "mismatch" if observed else "missing"
        reason = "PMCID maps to expected PMID" if status == "verified" else "PMCID maps to a different PMID" if status == "mismatch" else "NCBI idconv returned no PMID"
    except Exception as exc:
        return PmcidVerificationResult(normalized, expected, None, "network_unavailable", "ncbi_idconv", str(exc))
    if cache_path:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps({"pmcid": normalized, "observed_pmid": observed, "reason": reason}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return PmcidVerificationResult(normalized, expected, observed, status, "ncbi_idconv", reason)


def resolve_pmcid(paper: dict, *, network_enabled: bool = False, cache_dir: str | Path | None = None,
                  transport: Callable[[str], dict] | None = None) -> dict:
    """Resolve by a single PMID/DOI key. Returned PMCID is not implicitly verified."""
    base = {"paper_id": paper.get("paper_id"), "pmid": paper.get("pmid"), "doi": paper.get("doi"),
            "pmcid": paper.get("pmcid"), "idconv_error": None}
    identifier = str(paper.get("pmid") or paper.get("doi") or "").strip()
    cache = Path(cache_dir) if cache_dir else None
    cached = cache / f"resolve_{identifier.replace('/', '_')}.json" if cache and identifier else None
    if cached and cached.is_file():
        data = json.loads(cached.read_text(encoding="utf-8"))
        return {**base, **data, "idconv_source": "cache"}
    if not identifier:
        return {**base, "idconv_status": "no_pmcid", "idconv_source": "metadata"}
    if not network_enabled:
        return {**base, "idconv_status": "network_disabled", "idconv_source": None}
    try:
        record = _record_for_identifier(_request(identifier, transport), identifier)
        pmcid = record.get("pmcid")
        result = {**base, "pmcid": pmcid, "observed_pmid": record.get("pmid"),
                  "idconv_status": "resolved" if pmcid else "no_pmcid", "idconv_source": "pmc_id_converter_api"}
    except Exception as exc:
        result = {**base, "idconv_status": "error", "idconv_source": "pmc_id_converter_api", "idconv_error": str(exc)}
    if cached:
        cached.parent.mkdir(parents=True, exist_ok=True)
        cached.write_text(json.dumps({k: v for k, v in result.items() if k not in base or v != base[k]}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def resolve_authoritative_pmcid_for_pmid(
    pmid: str,
    *,
    network_enabled: bool = False,
    cache_dir: str | Path | None = None,
    transport: Callable[[str], dict] | None = None,
    reverse_transport: Callable[[str], dict] | None = None,
    verify_reverse: bool = True,
    refresh_cache: bool = False,
) -> dict:
    """Resolve one PMID by key and optionally prove the returned PMCID maps back."""
    expected = str(pmid or "").strip()
    cache_path = Path(cache_dir) / f"pmid_{expected}.json" if cache_dir and expected else None
    if cache_path and cache_path.is_file() and not refresh_cache:
        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            return {**cached, "resolution_source": "cache", "cache_hit": True}
        except (OSError, json.JSONDecodeError):
            pass
    base = {"pmid": expected, "resolved_pmcid": None, "forward_resolution_status": "error",
            "reverse_observed_pmid": None, "reverse_verification_status": "missing",
            "canonical_pmcid_status": "rejected", "resolution_source": "ncbi_idconv", "cache_hit": False}
    if not expected:
        return {**base, "reason": "candidate has no PMID"}
    if not network_enabled:
        return {**base, "forward_resolution_status": "network_unavailable",
                "reverse_verification_status": "network_unavailable", "canonical_pmcid_status": "unverified",
                "reason": "network resolution disabled and no cached PMID mapping exists"}
    try:
        payload = _request(expected, transport)
        record = _record_for_identifier(payload, expected)
        if (payload.get("records") or []) and not record:
            result = {**base, "forward_resolution_status": "error",
                      "reason": "forward response contained records but none matched requested PMID"}
            record = None
        if record is None:
            returned_pmid = ""; pmcid = None
        else:
            returned_pmid = str(record.get("pmid") or "").strip()
            pmcid = str(record.get("pmcid") or "").strip().upper() or None
        if record is None:
            pass
        elif returned_pmid and returned_pmid != expected:
            result = {**base, "forward_resolution_status": "error", "reason": "forward response PMID did not match requested PMID"}
        elif not pmcid:
            result = {**base, "forward_resolution_status": "no_mapping", "reverse_verification_status": "missing",
                      "canonical_pmcid_status": "no_pmc_mapping", "reason": "NCBI returned no PMCID for requested PMID"}
        elif not _PMCID_RE.fullmatch(pmcid):
            result = {**base, "resolved_pmcid": pmcid, "forward_resolution_status": "resolved",
                      "reverse_verification_status": "invalid", "reason": "forward PMCID has invalid format"}
        elif verify_reverse:
            reverse = verify_pmcid_maps_to_pmid(pmcid, expected, network_enabled=True, cache_dir=cache_dir,
                                                transport=reverse_transport or transport)
            canonical = "verified" if reverse.status == "verified" else "unverified" if reverse.status == "network_unavailable" else "rejected"
            result = {**base, "resolved_pmcid": pmcid, "forward_resolution_status": "resolved",
                      "reverse_observed_pmid": reverse.observed_pmid, "reverse_verification_status": reverse.status,
                      "canonical_pmcid_status": canonical, "reason": reverse.reason}
        else:
            result = {**base, "resolved_pmcid": pmcid, "forward_resolution_status": "resolved",
                      "reverse_verification_status": "not_requested", "canonical_pmcid_status": "unverified",
                      "reason": "reverse verification not requested"}
    except Exception as exc:
        result = {**base, "forward_resolution_status": "network_unavailable",
                  "reverse_verification_status": "network_unavailable", "canonical_pmcid_status": "unverified",
                  "reason": str(exc)}
    # Cache stable positive/absence/rejection outcomes, never transient network failures.
    if cache_path and result["forward_resolution_status"] != "network_unavailable":
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_value = {**result, "source": "ncbi_idconv", "timestamp": datetime.now(timezone.utc).isoformat()}
        cache_path.write_text(json.dumps(cache_value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


__all__ = ["PmcidVerificationResult", "resolve_authoritative_pmcid_for_pmid", "resolve_pmcid", "verify_pmcid_maps_to_pmid"]
