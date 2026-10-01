"""Prospective, offline-frozen PubMed ESearch response classifier V2.1.

This module is not used to reinterpret or resume the failed alpha3.19A run.
"""
from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from typing import Any


SCHEMA_VERSION = "PubMedESearchResponseValidityV2_1"
BACKEND_PREFIX = "Search Backend failed:"
VALID_STATES = frozenset({"VALID_ZERO", "VALID_NONZERO"})
TECHNICAL_RETRYABLE_STATES = frozenset({"TRANSPORT_FAILURE", "NCBI_ESearch_BACKEND_ERROR"})
RETRYABLE_HTTP_STATUS = frozenset({408, 429, 500, 502, 503, 504})


def _entries(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, dict):
        return any(_entries(item) for item in value.values())
    if isinstance(value, list):
        return any(_entries(item) for item in value)
    if isinstance(value, str):
        return bool(value.strip())
    return bool(value)


def _out(state: str, reason: str, **details: Any) -> dict[str, Any]:
    return {"schema_version": SCHEMA_VERSION, "state": state,
            "reason": reason,
            "technical_retryable": details.get("technical_retryable", state in TECHNICAL_RETRYABLE_STATES),
            "valid_page": state in VALID_STATES,
            "count": details.get("count"), "idlist": details.get("idlist"),
            "querytranslation": details.get("querytranslation"),
            "raw_error_text": details.get("raw_error_text"),
            "errorlist": details.get("errorlist"),
            "warninglist": details.get("warninglist")}


def validate_response(http_status: int | None, raw: bytes,
                      expected_retstart: int, requested_retmax: int) -> dict[str, Any]:
    if http_status != 200:
        return _out("TRANSPORT_FAILURE", f"HTTP_STATUS:{http_status}",
                    technical_retryable=http_status is None or http_status in RETRYABLE_HTTP_STATUS)
    try:
        decoded = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        # Keep the V2 XML ErrorList guard for query-semantic errors.
        try:
            root = ET.fromstring(raw)
            if any("".join(node.itertext()).strip() for node in root.iter()
                   if node.tag.rsplit("}", 1)[-1] == "ErrorList"):
                return _out("QUERY_SEMANTIC_ERROR", "XML_ERRORLIST_NONEMPTY")
        except ET.ParseError:
            pass
        return _out("JSON_PARSE_FAILURE", "NOT_VALID_ESEARCH_JSON")
    if not isinstance(decoded, dict) or not isinstance(decoded.get("esearchresult"), dict):
        return _out("SUCCESS_SCHEMA_INVALID", "ESEARCHRESULT_MISSING_OR_INVALID")
    result = decoded["esearchresult"]

    # ERROR is not ErrorList. An ERROR-only backend envelope cannot become
    # success or valid zero merely because HTTP returned 200.
    if "ERROR" in result:
        message = result["ERROR"]
        if len(result) != 1:
            return _out("CONFLICTING_ERROR_ENVELOPE", "ERROR_WITH_ADDITIONAL_FIELDS",
                        raw_error_text=message if isinstance(message, str) else None)
        if not isinstance(message, str) or not message.strip():
            return _out("ERROR_ENVELOPE_AUTHORITY_UNRESOLVED", "ERROR_VALUE_MISSING_OR_INVALID")
        if message.startswith(BACKEND_PREFIX):
            return _out("NCBI_ESearch_BACKEND_ERROR", "STRUCTURAL_ERROR_ONLY_BACKEND_ENVELOPE",
                        raw_error_text=message)
        return _out("ERROR_ENVELOPE_AUTHORITY_UNRESOLVED", "ERROR_TEXT_NOT_BACKEND_PREFIX",
                    raw_error_text=message)

    errorlist = result.get("errorlist")
    if errorlist is not None and not isinstance(errorlist, dict):
        return _out("SUCCESS_SCHEMA_INVALID", "ERRORLIST_WRONG_TYPE", errorlist=errorlist)
    if _entries(errorlist):
        return _out("QUERY_SEMANTIC_ERROR", "ESEARCH_ERRORLIST_NONEMPTY",
                    errorlist=errorlist, warninglist=result.get("warninglist"),
                    querytranslation=result.get("querytranslation"))

    count_raw, retstart_raw, retmax_raw = (result.get("count"), result.get("retstart"),
                                           result.get("retmax"))
    if not all(isinstance(value, str) and re.fullmatch(r"0|[1-9][0-9]*", value)
               for value in (count_raw, retstart_raw, retmax_raw)):
        return _out("SUCCESS_SCHEMA_INVALID", "COUNT_OR_PAGINATION_FIELD_INVALID")
    count, retstart, retmax = int(count_raw), int(retstart_raw), int(retmax_raw)
    if retstart != expected_retstart or retmax > requested_retmax:
        return _out("SUCCESS_SCHEMA_INVALID", "PAGINATION_MISMATCH", count=count)
    ids = result.get("idlist")
    if not isinstance(ids, list) or len(ids) > requested_retmax or any(
        not isinstance(value, str) or not re.fullmatch(r"[1-9][0-9]*", value)
        for value in ids
    ):
        return _out("SUCCESS_SCHEMA_INVALID", "IDLIST_INVALID", count=count)
    if count == 0 and (ids or retmax != 0):
        return _out("SUCCESS_SCHEMA_INVALID", "ZERO_COUNT_WITH_IDS_OR_NONZERO_RETMAX",
                    count=count, idlist=ids)
    if count > expected_retstart and not ids:
        return _out("SUCCESS_SCHEMA_INVALID", "NONZERO_COUNT_WITH_EMPTY_PAGE",
                    count=count, idlist=ids)
    querytranslation = result.get("querytranslation")
    if querytranslation is not None and not isinstance(querytranslation, str):
        return _out("SUCCESS_SCHEMA_INVALID", "QUERYTRANSLATION_WRONG_TYPE",
                    count=count, idlist=ids)
    warninglist = result.get("warninglist")
    if warninglist is not None and not isinstance(warninglist, dict):
        return _out("SUCCESS_SCHEMA_INVALID", "WARNINGLIST_WRONG_TYPE",
                    count=count, idlist=ids)
    if _entries(warninglist):
        permitted = (count == 0 and ids == [] and
            warninglist == {"phrasesignored": [], "quotedphrasesnotfound": [],
                            "outputmessages": ["No items found."]})
        if not permitted:
            return _out("WARNING_POLICY_FAILURE", "WARNINGLIST_NOT_ALLOWLISTED",
                        count=count, idlist=ids, querytranslation=querytranslation,
                        warninglist=warninglist)
    return _out("VALID_ZERO" if count == 0 else "VALID_NONZERO", "SUCCESS",
                count=count, idlist=ids, querytranslation=querytranslation,
                errorlist=errorlist, warninglist=warninglist)
