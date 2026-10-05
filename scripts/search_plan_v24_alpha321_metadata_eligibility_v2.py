"""Offline alpha3.21 metadata date and source-collision execution overlay V2."""

from __future__ import annotations

import calendar
import hashlib
import itertools
import json
import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import date

from code_engine.extraction_assets.source_identity import normalize_identifier
from scripts import run_search_plan_v24_alpha319c_pubmed_metadata_eligibility as legacy
from scripts import run_search_plan_v24_alpha319a_ncbi_source_acquisition as rules
from scripts import search_plan_v24_alpha318a3_correction_reference as correction


WINDOW_START, WINDOW_END = date(2026, 1, 1), date(2026, 9, 30)
DATE_IN = "DATE_CLEAR_IN_WINDOW"
DATE_OUT = "DATE_CLEAR_OUTSIDE_WINDOW"
DATE_PARTIAL = "DATE_UNRESOLVED_INSUFFICIENT_PRECISION"
DATE_CONFLICT = "DATE_UNRESOLVED_CONFLICTING_DIRECT_REPRESENTATIONS"
DATE_MISSING = "DATE_UNRESOLVED_MISSING_DIRECT_PUBLICATION_DATE"
DATE_BAD = "DATE_UNRESOLVED_UNPARSEABLE_DIRECT_PUBLICATION_DATE"
COLLISION = "SAME_ATTEMPT_EXACT_IDENTITY_COLLISION_FAIL_CLOSED"
DATE_FIELDS = ["Year", "Month", "Day", "MedlineDate"]
DATE_PATHS = ["PubmedArticle/MedlineCitation/Article/Journal/JournalIssue/PubDate",
              "PubmedArticle/MedlineCitation/Article/ArticleDate"]
ENGLISH_MONTHS = ("January", "February", "March", "April", "May", "June", "July",
                  "August", "September", "October", "November", "December")
MONTHS = {name.casefold(): i for i, full_name in enumerate(ENGLISH_MONTHS, 1)
          for name in (full_name, full_name[:3])}
MONTHS["sept"] = 9
PRECEDENCE = ["METADATA_TERMINAL_FAILURE", "HISTORICAL_EXACT_ALIAS_CONTAMINATION",
              COLLISION, "DATE_EXCLUDED_OR_UNRESOLVED", "PUBLICATION_TYPE_EXCLUDED",
              "CORRECTION_UPDATE_EXCLUDED", "PRE_OA_HANDOFF_CLEAR_OR_DEFERRED"]


def _month(value: str) -> int:
    if re.fullmatch(r"[0-9]{1,2}", value):
        number = int(value)
    else:
        number = MONTHS.get(value.casefold(), 0)
    if not 1 <= number <= 12:
        raise ValueError("MONTH_NOT_IN_FROZEN_VOCABULARY")
    return number


def _interval(year: int, month: int | None = None, day: int | None = None):
    if month is None:
        if day is not None:
            raise ValueError("DAY_WITHOUT_MONTH")
        return date(year, 1, 1), date(year, 12, 31), "year"
    if day is None:
        return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1]), "month"
    exact = date(year, month, day)
    return exact, exact, "day"


def _text_point(text: str):
    iso = re.fullmatch(r"([0-9]{4})(?:-([0-9]{2})(?:-([0-9]{2}))?)?", text)
    if iso:
        return _interval(int(iso[1]), int(iso[2]) if iso[2] else None,
                         int(iso[3]) if iso[3] else None)
    named = re.fullmatch(r"([0-9]{4}) ([A-Za-z]+)(?: ([0-9]{1,2}))?", text)
    if named:
        return _interval(int(named[1]), _month(named[2]), int(named[3]) if named[3] else None)
    raise ValueError("TEXT_NOT_IN_FROZEN_DATE_GRAMMAR")


def normalize_date_text(value: str):
    """Strict ISO/NLM date grammar; unsupported dates are never guessed."""
    text = " ".join(value.split())
    for separator in ("/", "..", " to "):
        if separator in text:
            parts = text.split(separator)
            if len(parts) != 2:
                raise ValueError("DATE_RANGE_ENDPOINT_COUNT_INVALID")
            left, right = (_text_point(part.strip()) for part in parts)
            if left[0] > right[1]:
                raise ValueError("DATE_RANGE_REVERSED")
            return left[0], right[1], "explicit_range"
    months = re.fullmatch(r"([0-9]{4}) ([A-Za-z]+)-([A-Za-z]+)", text)
    if months:
        start = _interval(int(months[1]), _month(months[2]))
        end = _interval(int(months[1]), _month(months[3]))
    else:
        cross_year = re.fullmatch(r"([0-9]{4}) ([A-Za-z]+)-([0-9]{4}) ([A-Za-z]+)", text)
        days = re.fullmatch(r"([0-9]{4}) ([A-Za-z]+) ([0-9]{1,2})-([0-9]{1,2})", text)
        if cross_year:
            start = _interval(int(cross_year[1]), _month(cross_year[2]))
            end = _interval(int(cross_year[3]), _month(cross_year[4]))
        elif days:
            start = _interval(int(days[1]), _month(days[2]), int(days[3]))
            end = _interval(int(days[1]), _month(days[2]), int(days[4]))
        else:
            return _text_point(text)
    if start[0] > end[1]:
        raise ValueError("DATE_RANGE_REVERSED")
    return start[0], end[1], "explicit_range"


def interval_state(start: date, end: date) -> str:
    if WINDOW_START <= start <= end <= WINDOW_END:
        return DATE_IN
    if end < WINDOW_START or start > WINDOW_END:
        return DATE_OUT
    return DATE_PARTIAL


def _date_representation(node: ET.Element, path: str, ordinal: int) -> dict:
    fields = defaultdict(list)
    for child in node:
        fields[legacy.source_policy.local(child.tag)].append(legacy.node_text(child))
    raw_fields = dict(fields)
    result = {"path": path, "representation_ordinal": ordinal, "direct_fields": raw_fields}
    try:
        if any(key not in DATE_FIELDS or len(values) != 1 for key, values in fields.items()):
            raise ValueError("UNSUPPORTED_OR_DUPLICATE_DIRECT_DATE_FIELD")
        if "MedlineDate" in fields:
            if len(fields) != 1:
                raise ValueError("MIXED_MEDLINEDATE_AND_STRUCTURED_FIELDS")
            start, end, precision = normalize_date_text(fields["MedlineDate"][0])
        else:
            year = fields.get("Year", [""])[0]
            if not re.fullmatch(r"[0-9]{4}", year):
                raise ValueError("YEAR_MISSING_OR_INVALID")
            month = _month(fields["Month"][0]) if "Month" in fields else None
            day_text = fields.get("Day", [None])[0]
            if day_text is not None and not re.fullmatch(r"[0-9]{1,2}", day_text):
                raise ValueError("DAY_INVALID")
            start, end, precision = _interval(int(year), month, int(day_text) if day_text is not None else None)
        result.update(earliest_possible_date=start.isoformat(), latest_possible_date=end.isoformat(),
                      precision=precision, state=interval_state(start, end), parse_error=None)
    except (ValueError, OverflowError) as exc:
        result.update(earliest_possible_date=None, latest_possible_date=None, precision=None,
                      state="UNPARSEABLE_DIRECT_PUBLICATION_DATE", parse_error=str(exc))
    return result


def resolve_publication_dates(raw: bytes, expected_pmid: str) -> dict:
    """Use only the requested citation's two established direct date paths."""
    root = ET.fromstring(raw)
    articles = [root] if legacy.source_policy.local(root.tag) == "PubmedArticle" else legacy.children(root, "PubmedArticle")
    if len(articles) != 1:
        raise ValueError("PUBMED_ARTICLE_COUNT_NOT_ONE")
    citations = legacy.children(articles[0], "MedlineCitation")
    if len(citations) != 1 or [legacy.node_text(p) for p in legacy.children(citations[0], "PMID")] != [expected_pmid]:
        raise ValueError("PRIMARY_CITATION_PMID_MISSING_OR_MISMATCH")
    article_nodes = legacy.children(citations[0], "Article")
    if len(article_nodes) != 1:
        raise ValueError("CITATION_ARTICLE_COUNT_NOT_ONE")
    article = article_nodes[0]
    dates = []
    for journal in legacy.children(article, "Journal"):
        for issue in legacy.children(journal, "JournalIssue"):
            dates.extend((node, DATE_PATHS[0]) for node in legacy.children(issue, "PubDate"))
    dates.extend((node, DATE_PATHS[1]) for node in legacy.children(article, "ArticleDate"))
    representations = [_date_representation(node, path, i) for i, (node, path) in enumerate(dates, 1)]
    conclusions = [r["state"] for r in representations]
    if not conclusions:
        state = DATE_MISSING
    elif "UNPARSEABLE_DIRECT_PUBLICATION_DATE" in conclusions:
        state = DATE_BAD
    elif len(conclusions) == 1:
        state = conclusions[0]
    elif len(set(conclusions)) == 1 and conclusions[0] in (DATE_IN, DATE_OUT):
        state = conclusions[0]
    else:
        state = DATE_CONFLICT
    return {"schema_version": "PublicationDateResolutionContractV2", "pmid": expected_pmid,
            "publication_window_start": WINDOW_START.isoformat(), "publication_window_end": WINDOW_END.isoformat(),
            "precedence": "none; all direct representations must agree",
            "representations": representations, "state": state,
            "date_dimension_satisfied": state == DATE_IN}


def collision_components(records: list[dict]) -> dict:
    """Exact canonical aliases, connected components, and all-members exclusion."""
    pmids = [r["pmid"] for r in records]
    if len(pmids) != len(set(pmids)) or any(not isinstance(p, str) or not re.fullmatch(r"[1-9][0-9]*", p) for p in pmids):
        raise ValueError("SAMPLED_PMID_RECORD_IDENTITIES_NOT_UNIQUE_CANONICAL")
    aliases = defaultdict(set)
    adjacency = {p: set() for p in pmids}
    for record in records:
        for kind in ("pmcid", "doi"):
            value = record.get(kind)
            if value is not None and not isinstance(value, str):
                raise ValueError("DIRECT_ALIAS_MUST_BE_SINGLY_BOUND_STRING")
            normalized = normalize_identifier(value, kind)
            if normalized:
                aliases[(kind, normalized)].add(record["pmid"])
    edges = []
    for (kind, alias), members in sorted(aliases.items()):
        for left, right in itertools.combinations(sorted(members, key=int), 2):
            adjacency[left].add(right)
            adjacency[right].add(left)
            edges.append({"left_pmid": left, "right_pmid": right,
                          "identifier_type": kind, "canonical_identifier": alias})
    visited, components, states = set(), [], {p: "CLEAR" for p in pmids}
    for start in sorted(pmids, key=int):
        if start in visited:
            continue
        pending, members = [start], set()
        while pending:
            current = pending.pop()
            if current in members:
                continue
            members.add(current)
            pending.extend(adjacency[current] - members)
        visited.update(members)
        if len(members) < 2:
            continue
        member_ids = sorted(members, key=int)
        component_edges = [e for e in edges if e["left_pmid"] in members and e["right_pmid"] in members]
        identity = json.dumps({"pmids": member_ids, "edges": component_edges}, sort_keys=True, separators=(",", ":")).encode()
        components.append({"component_id": "collision_" + hashlib.sha256(identity).hexdigest(),
            "state": "SAME_ATTEMPT_EXACT_IDENTITY_COLLISION_COMPONENT", "member_pmids": member_ids,
            "edges": component_edges, "terminal_state": COLLISION})
        for pmid in member_ids:
            states[pmid] = COLLISION
    return {"components": components, "edges": edges, "source_states": states,
            "winner_selection_used": False, "collapse_used": False, "replacement_allowed": False}


def parse_source(raw: bytes, expected_pmid: str, accepted: dict, excluded: dict) -> dict:
    """Leave legacy direct-identity/type/correction behavior unchanged."""
    parsed = legacy.parse_metadata(raw, expected_pmid)
    date_result = resolve_publication_dates(raw, expected_pmid)
    type_result = rules.publication_type_state(parsed["publication_types"], accepted, excluded)
    correction_result = correction.classify(parsed["publication_types"], parsed["correction_relationships"])
    deferred = (correction_result["state"] == "CORRECTION_REFERENCE_UNRESOLVED" and
                correction_result["unresolved_reasons"] == ["REF_TYPE:UpdateOf:INDEPENDENT_SOURCE_NOT_YET_ELIGIBLE"])
    return {**parsed, "metadata_response_state": "RESOLVED",
        "direct_pmcid": normalize_identifier(parsed["pmcid"], "pmcid"),
        "direct_doi": normalize_identifier(parsed["doi"], "doi"),
        "date_resolution": date_result, "date_resolution_state": date_result["state"],
        "date_state": "CLEAR" if date_result["state"] == DATE_IN else "INELIGIBLE" if date_result["state"] == DATE_OUT else "UNRESOLVED",
        "publication_type_state": {"PRELIMINARY_TYPE_ACCEPTED": "CLEAR",
            "SOURCE_TYPE_INELIGIBLE": "INELIGIBLE", "SOURCE_TYPE_UNRESOLVED": "UNRESOLVED"}[type_result["state"]],
        "publication_type_result": type_result, "correction_result": correction_result,
        "correction_update_state": correction_result["state"].removeprefix("CORRECTION_REFERENCE_"),
        "updateof_deferred_state": legacy.DEFERRED_UPDATEOF if deferred else None,
        "metadata_error": None}


def evaluate_batch(responses: list[dict], accepted: dict, excluded: dict,
                   historical_pmcids: set[str], historical_dois: set[str]) -> dict:
    """Pure local processing after the future caller freezes all raw responses."""
    records = []
    for response in responses:
        pmid = response["pmid"]
        try:
            raw = response.get("raw_xml")
            if raw is None:
                raise ValueError("TERMINAL_METADATA_TRANSPORT_FAILURE")
            record = parse_source(raw, pmid, accepted, excluded)
        except (ValueError, ET.ParseError) as exc:
            record = {"pmid": pmid, "metadata_response_state": "SOURCE_FAILED_CLOSED",
                "metadata_state": "SOURCE_FAILED_CLOSED", "metadata_error": type(exc).__name__ + ":" + str(exc),
                "direct_pmcid": None, "direct_doi": None, "date_resolution_state": None,
                "date_state": "UNRESOLVED", "publication_type_state": "UNRESOLVED",
                "correction_update_state": "UNRESOLVED", "updateof_deferred_state": None}
        record["historical_pmcid_contaminated"] = record["direct_pmcid"] in historical_pmcids if record["direct_pmcid"] else False
        record["historical_doi_contaminated"] = record["direct_doi"] in historical_dois if record["direct_doi"] else False
        record["historical_alias_contamination_state"] = "POST_SAMPLE_EXACT_SOURCE_CONTAMINATION" if (
            record["historical_pmcid_contaminated"] or record["historical_doi_contaminated"]) else "CLEAR"
        records.append(record)
    graph = collision_components([{"pmid": r["pmid"], "pmcid": r["direct_pmcid"], "doi": r["direct_doi"]} for r in records])
    for record in records:
        record["same_attempt_alias_collision_state"] = graph["source_states"][record["pmid"]]
        deferred = record["updateof_deferred_state"] == legacy.DEFERRED_UPDATEOF
        dimensions = [record["metadata_state"] != "RESOLVED",
            record["historical_alias_contamination_state"] != "CLEAR",
            record["same_attempt_alias_collision_state"] != "CLEAR",
            record["date_resolution_state"] != DATE_IN,
            record["publication_type_state"] != "CLEAR",
            record["correction_update_state"] != "CLEAR" and not deferred]
        record["exclusion_dimensions"] = [PRECEDENCE[i] for i, blocked in enumerate(dimensions) if blocked]
        record["pre_oa_handoff_state"] = "BLOCKED" if any(dimensions) else "PRE_OA_CONDITIONAL_UPDATEOF" if deferred else "PRE_OA_CLEAR"
        record["primary_terminal_reason"] = record["exclusion_dimensions"][0] if any(dimensions) else PRECEDENCE[-1]
    return {"schema_version": "Alpha321MetadataEligibilityParserContractV2", "records": records,
        "collision_graph": graph, "pre_oa_handoff": [r for r in records if r["pre_oa_handoff_state"] != "BLOCKED"],
        "replacement_used": False, "source_record_count_preserved": len(records) == len(responses)}
