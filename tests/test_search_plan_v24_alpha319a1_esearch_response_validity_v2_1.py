"""Synthetic fail-closed ESearch V2.1 classifier tests (no network)."""
import json

from scripts.search_plan_v24_alpha319a1_esearch_response_validity_v2_1 import validate_response


def payload(result):
    return json.dumps({"esearchresult": result}, separators=(",", ":")).encode()


def test_a_valid_nonzero():
    result = validate_response(200, payload({"count": "2", "retstart": "0",
        "retmax": "2", "idlist": ["123", "456"]}), 0, 50)
    assert result["state"] == "VALID_NONZERO" and result["valid_page"]


def test_b_valid_zero():
    result = validate_response(200, payload({"count": "0", "retstart": "0",
        "retmax": "0", "idlist": []}), 0, 50)
    assert result["state"] == "VALID_ZERO" and result["valid_page"]


def test_c_errorlist_semantic_not_retryable():
    result = validate_response(200, payload({"errorlist": {"phrasesnotfound": ["bad"]},
        "count": "0", "retstart": "0", "retmax": "0", "idlist": []}), 0, 50)
    assert result["state"] == "QUERY_SEMANTIC_ERROR"
    assert not result["technical_retryable"]


def test_d_prohibited_warning():
    result = validate_response(200, payload({"count": "1", "retstart": "0",
        "retmax": "1", "idlist": ["123"],
        "warninglist": {"phrasesignored": ["field"]}}), 0, 50)
    assert result["state"] == "WARNING_POLICY_FAILURE"


def test_e_backend_envelope():
    result = validate_response(200, payload({"ERROR": "Search Backend failed: upstream 502 status."}), 0, 50)
    assert result["state"] == "NCBI_ESearch_BACKEND_ERROR"
    assert result["technical_retryable"] and not result["valid_page"]


def test_f_unrelated_malformed_success_json():
    assert validate_response(200, b'{"x":1}', 0, 50)["state"] == "SUCCESS_SCHEMA_INVALID"


def test_g_conflicting_error_and_success_fields():
    result = validate_response(200, payload({"ERROR": "Search Backend failed: upstream 502 status.",
        "count": "0", "retstart": "0", "retmax": "0", "idlist": []}), 0, 50)
    assert result["state"] == "CONFLICTING_ERROR_ENVELOPE"
    assert not result["technical_retryable"] and not result["valid_page"]


def test_h_connection_reset_transport_failure():
    result = validate_response(None, b"", 0, 50)
    assert result["state"] == "TRANSPORT_FAILURE" and result["technical_retryable"]


def test_nonretryable_http_status_does_not_inherit_transport_retry():
    assert not validate_response(403, b"", 0, 50)["technical_retryable"]
    assert validate_response(502, b"", 0, 50)["technical_retryable"]


def test_i_backend_never_valid_zero():
    result = validate_response(200, payload({"ERROR": "Search Backend failed:"}), 0, 50)
    assert result["state"] != "VALID_ZERO" and result["count"] is None


def test_j_errorlist_with_http_number_remains_semantic():
    result = validate_response(200, payload({"errorlist": {"messages": ["502 invalid field"]},
        "count": "0", "retstart": "0", "retmax": "0", "idlist": []}), 0, 50)
    assert result["state"] == "QUERY_SEMANTIC_ERROR" and not result["technical_retryable"]


def test_non_backend_error_only_is_not_retried():
    result = validate_response(200, payload({"ERROR": "Invalid search expression"}), 0, 50)
    assert result["state"] == "ERROR_ENVELOPE_AUTHORITY_UNRESOLVED"
    assert not result["technical_retryable"]


def test_json_parse_failure_and_xml_errorlist():
    assert validate_response(200, b"not json", 0, 50)["state"] == "JSON_PARSE_FAILURE"
    assert validate_response(200, b"<eSearchResult><ErrorList>bad field</ErrorList></eSearchResult>",
                             0, 50)["state"] == "QUERY_SEMANTIC_ERROR"
