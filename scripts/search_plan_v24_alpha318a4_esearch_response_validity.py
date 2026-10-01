"""Frozen PubMedESearchResponseValidityV2 for source-frame JSON responses."""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from typing import Any


SCHEMA_VERSION = "PubMedESearchResponseValidityV2"
VALID_STATES = frozenset({"QUERY_SEMANTIC_SUCCESS", "VALID_ZERO_RESULT"})
STATES = frozenset({"TRANSPORT_FAILURE", "RESPONSE_SCHEMA_INVALID",
    "QUERY_SEMANTIC_ERROR", "QUERY_WARNING_UNRESOLVED", *VALID_STATES})
NON_SEMANTIC_ZERO_MESSAGE = "No items found."


def _has_entries(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, dict):
        return any(_has_entries(item) for item in value.values())
    if isinstance(value, list):
        return any(_has_entries(item) for item in value)
    if isinstance(value, str):
        return bool(value.strip())
    return bool(value)


def _result(state: str, *, count: int | None = None, ids: list[str] | None = None,
            querytranslation: str | None = None, errorlist: Any = None,
            warninglist: Any = None, reason: str | None = None) -> dict[str, Any]:
    return {"schema_version": SCHEMA_VERSION, "state": state,
        "transport_success": state != "TRANSPORT_FAILURE",
        "query_semantic_success": state in VALID_STATES,
        "count": count, "idlist": ids, "querytranslation": querytranslation,
        "errorlist": errorlist, "warninglist": warninglist, "reason": reason}


def validate_response(http_status: int | None, raw: bytes,
                      expected_retstart: int, requested_retmax: int) -> dict[str, Any]:
    """ErrorList is checked before count, and unknown warnings fail closed."""
    if http_status != 200:
        return _result("TRANSPORT_FAILURE", reason=f"HTTP_STATUS:{http_status}")
    try:
        decoded = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        # JSON is the frozen transport; XML ErrorList still signals a query error.
        try:
            root = ET.fromstring(raw)
            error_nodes = [node for node in root.iter() if node.tag.rsplit("}", 1)[-1] == "ErrorList"]
            if any("".join(node.itertext()).strip() for node in error_nodes):
                return _result("QUERY_SEMANTIC_ERROR", reason="XML_ERRORLIST_NONEMPTY")
        except ET.ParseError:
            pass
        return _result("RESPONSE_SCHEMA_INVALID", reason="NOT_VALID_ESEARCH_JSON")
    if not isinstance(decoded, dict) or not isinstance(decoded.get("esearchresult"), dict):
        return _result("RESPONSE_SCHEMA_INVALID", reason="ESEARCHRESULT_MISSING_OR_INVALID")
    result = decoded["esearchresult"]
    errorlist = result.get("errorlist")
    if errorlist is not None and not isinstance(errorlist, dict):
        return _result("RESPONSE_SCHEMA_INVALID", errorlist=errorlist,
                       reason="ERRORLIST_WRONG_TYPE")
    if _has_entries(errorlist):
        return _result("QUERY_SEMANTIC_ERROR", errorlist=errorlist,
                       warninglist=result.get("warninglist"),
                       querytranslation=result.get("querytranslation"),
                       reason="ESEARCH_ERRORLIST_NONEMPTY")
    count_raw, retstart_raw, retmax_raw = (result.get("count"), result.get("retstart"),
                                           result.get("retmax"))
    if not all(isinstance(value, str) and re.fullmatch(r"0|[1-9][0-9]*", value)
               for value in (count_raw, retstart_raw, retmax_raw)):
        return _result("RESPONSE_SCHEMA_INVALID", errorlist=errorlist,
                       reason="COUNT_OR_PAGINATION_FIELD_INVALID")
    count, retstart, retmax = int(count_raw), int(retstart_raw), int(retmax_raw)
    if retstart != expected_retstart or retmax > requested_retmax:
        return _result("RESPONSE_SCHEMA_INVALID", count=count, errorlist=errorlist,
                       reason="PAGINATION_MISMATCH")
    ids = result.get("idlist")
    if not isinstance(ids, list) or len(ids) > requested_retmax or any(
        not isinstance(value, str) or not re.fullmatch(r"[1-9][0-9]*", value)
        for value in ids
    ):
        return _result("RESPONSE_SCHEMA_INVALID", count=count, errorlist=errorlist,
                       reason="IDLIST_INVALID")
    if count == 0 and (ids or retmax != 0):
        return _result("RESPONSE_SCHEMA_INVALID", count=count, ids=ids,
                       reason="ZERO_COUNT_WITH_IDS_OR_NONZERO_RETURNED_RETMAX")
    if count > expected_retstart and not ids:
        return _result("RESPONSE_SCHEMA_INVALID", count=count, ids=ids,
                       reason="NONZERO_COUNT_WITH_EMPTY_PAGE")
    querytranslation = result.get("querytranslation")
    if querytranslation is not None and not isinstance(querytranslation, str):
        return _result("RESPONSE_SCHEMA_INVALID", count=count, ids=ids,
                       reason="QUERYTRANSLATION_WRONG_TYPE")
    warninglist = result.get("warninglist")
    if warninglist is not None and not isinstance(warninglist, dict):
        return _result("RESPONSE_SCHEMA_INVALID", count=count, ids=ids,
                       reason="WARNINGLIST_WRONG_TYPE")
    if _has_entries(warninglist):
        # The only permitted display message is the exact observed zero-hit note.
        permitted = (count == 0 and ids == [] and
            warninglist == {"phrasesignored": [], "quotedphrasesnotfound": [],
                            "outputmessages": [NON_SEMANTIC_ZERO_MESSAGE]})
        if not permitted:
            return _result("QUERY_WARNING_UNRESOLVED", count=count, ids=ids,
                querytranslation=querytranslation, errorlist=errorlist,
                warninglist=warninglist, reason="WARNINGLIST_NOT_ALLOWLISTED")
    state = "VALID_ZERO_RESULT" if count == 0 else "QUERY_SEMANTIC_SUCCESS"
    return _result(state, count=count, ids=ids,
                   querytranslation=querytranslation, errorlist=errorlist,
                   warninglist=warninglist)
