"""Derived direction safety for legacy records; raw extraction is never authority.

Zero is a compatibility sentinel, not a biological zero-effect estimate. This
policy neither selects a statistical threshold nor infers a causal relation.
"""
from __future__ import annotations
import re

VERSION = "effective_legacy_direction_v2"
NON_SIGNIFICANT = (
    "no significant", "not significant", "not statistically significant",
    "no statistically significant", "nonsignificant", "non-significant",
    "did not find a significant", "(ns)", "无显著", "无明显",
)


def nonsignificant_wording(text):
    text = str(text or "").casefold()
    return any(term in text for term in NON_SIGNIFICANT)


def extracted_sign(value):
    if type(value) not in (int, str):
        return None
    if value in (1, "positive", "increase", "increased"):
        return 1
    if value in (-1, "negative", "decrease", "decreased"):
        return -1
    return None


def scoped_statistical_evidence(formal, spans):
    """Exact anchored statement/endpoint/arms scope; no P-value threshold or NLP.

    This only reads existing native field bindings. A caption glossary, absent
    method or a missing comparator cannot establish the selected result's status.
    The existing comparator-scope audit remains structural, not authorization.
    """
    from code_engine.discovery.ai_review_shadow import content_hash
    from code_engine.extraction_assets.experimental_core.source_authority import audit_source_scope
    norm = lambda value: " ".join(str(value or "").split()).casefold()
    experiment = formal['experiment']; measurement = formal['measurement']
    tested = experiment.get('comparison_arm_raw'); reference = experiment.get('control_arm_raw')
    # An entity mention alone cannot distinguish its mRNA/protein/activity endpoints.
    endpoint = norm(measurement.get('endpoint_raw'))
    contains = lambda clause, value: bool(value and re.search(
        r'(?<!\w)' + re.escape(norm(value)) + r'(?!\w)', norm(clause)))
    refs = formal['observation']['evidence_span_ids']
    revision = content_hash(formal)
    selected = re.findall(r'\b(?:fig(?:ure)?\.?\s*)\d+\s*\(?([A-Za-z])\)?',
                          str(experiment.get('experiment_label_raw') or ''), flags=re.I)
    selected_panel = selected[0].upper() if len(set(selected)) == 1 else None
    accepted = []; ignored = []
    for ref in refs:
        span = spans[ref]; text = span['text']
        markers = list(re.finditer(r'\(([A-Z])\)|\b([A-Z]),\s', text))
        boundaries = [0] + [m.end() for m in re.finditer(r'(?<=[.!?;])\s+|[\r\n]+', text)] + [len(text)]
        for start, end in zip(boundaries, boundaries[1:]):
            part = text[start:end]; clause = part.strip()
            if not clause: continue
            ns = nonsignificant_wording(clause)
            sig = bool(re.search(r'\bsignificant(?:ly)?\b', clause, re.I)) and not ns
            if not (ns or sig): continue
            offset = start + len(part) - len(part.lstrip())
            item = {'evidence_span_id': ref, 'anchor_id': span.get('anchor_id'),
                    'block_id': span['block_id'], 'source_document_id': span['source_document_id'],
                    'native_revision_sha256': revision, 'text': clause,
                    'char_start': span['char_start'] + offset,
                    'char_end': span['char_start'] + offset + len(clause)}
            local_markers = [m for m in markers if start <= m.start() < end]
            preceding = [m for m in markers if m.start() <= offset]
            marker = local_markers[0] if len(local_markers) == 1 else preceding[-1] if preceding else None
            panel = (marker.group(1) or marker.group(2)) if marker else None
            is_caption = 'fig' in str(span.get('section') or '').casefold()
            reason = None
            if (re.search(r'\bns\s*[,;:=]\s*(?:not significant|non[- ]significant)', clause, re.I) or
                    re.match(r'^\s*(?:ns\s*[,;:=]|not significant\s*$)', clause, re.I)):
                reason = 'GENERIC_STATISTICAL_LEGEND_NOT_OBSERVATION_EVIDENCE'
            elif len(local_markers) > 1 or (panel and (selected_panel is None or panel != selected_panel)):
                reason = 'PANEL_SCOPE_UNRESOLVED_OR_DIFFERENT'
            elif is_caption and (selected_panel is None or panel != selected_panel):
                reason = 'CAPTION_PANEL_NOT_BOUND_TO_SELECTED_RESULT'
            elif not endpoint or endpoint == 'unknown' or not contains(clause, endpoint):
                reason = 'STATISTICAL_STATEMENT_ENDPOINT_NOT_BOUND'
            elif not (tested and reference and norm(tested) != norm(reference) and
                      contains(clause, tested) and contains(clause, reference)):
                reason = 'STATISTICAL_STATEMENT_TESTED_REFERENCE_NOT_BOUND'
            elif not re.search(r'\b(?:versus|vs\.?|compared|comparison|between)\b', clause, re.I):
                reason = 'EXPLICIT_STATISTICAL_CONTRAST_NOT_BOUND'
            elif (re.search(r'\b(?:whereas|while|but|respectively)\b', clause, re.I) or
                  len(re.findall(r'\b(?:versus|vs\.?|compared|between)\b', clause, re.I)) > 1):
                reason = 'MULTIPLE_OUTCOME_OR_COMPARISON_SCOPE_UNRESOLVED'
            if reason:
                ignored.append({**item, 'reason': reason})
            else:
                accepted.append({**item, 'panel': panel,
                                 'status': 'NONSIGNIFICANT' if ns else 'SIGNIFICANT'})
    statuses = {a['status'] for a in accepted}
    status = next(iter(statuses)) if len(statuses) == 1 else 'UNKNOWN'
    arms_present = bool(tested and reference and any(
        norm(tested) in norm(spans[r]['text']) and norm(reference) in norm(spans[r]['text']) for r in refs))
    scope = audit_source_scope(task_type='comparator', result_context_present=bool(refs),
        factors_present=bool(formal.get('interventions')), measurements_present=bool(measurement.get('evidence_span_ids')),
        comparison_context_present=bool(tested and reference), group_definition_present=arms_present,
        caption_scope_checked=not any(i['reason'].startswith(('CAPTION_', 'PANEL_')) for i in ignored),
        source_anchor_verified=bool(refs))
    return {'schema_version': 'source_scoped_statistical_evidence_v1', 'status': status,
        'observation_id': formal['observation_id'], 'native_revision_sha256': revision,
        'experiment_scope_identity': experiment.get('experiment_id'),
        'endpoint': measurement.get('endpoint_raw'), 'tested_arm': tested, 'reference_arm': reference,
        'selected_panel': selected_panel, 'result_evidence_refs': refs,
        'accepted_statements': accepted, 'ignored_statements': ignored,
        'comparator_scope_audit': scope, 'comparator_audit_is_statistical_authority': False,
        'uncertainty_reasons': ['CONFLICTING_SCOPED_STATISTICAL_STATEMENTS'] if len(statuses) > 1 else
            ['NO_UNAMBIGUOUS_ENDPOINT_CONTRAST_SCOPED_STATISTICAL_STATEMENT'] if not statuses else [],
        'significance_assumed_from_absence': False, 'P_value_inferred': None,
        'zero_effect_asserted': False, 'scientific_authorization': False}


def effective_legacy_direction(row):
    raw = row.get("raw_relation_sign", row.get("relation_sign", row.get("direct_relation_sign")))
    text = " ".join(str(row.get(k) or "") for k in (
        "relation_raw", "evidence_sentence", "statistical_support_raw", "observed_result", "direction"))
    null = nonsignificant_wording(text)
    unresolved = row.get("direction") in (
        "mixed", "no_effect", "not_significant", "neutral_or_association")
    association = (row.get("polarity_type") == "association" or
                   row.get("relation_family") == "association" or
                   any(t in str(row.get("relation_raw") or "").casefold() for t in ("associated", "association", "correlat")) or
                   any(t in str(row.get("evidence_type") or "").casefold() for t in ("observational", "association")))
    sign = extracted_sign(raw)
    return {"schema_version": VERSION, "raw_extracted_sign": raw,
            "effective_sign": sign, "direction_eligible": sign in (-1, 1),
            "conflict_screen_eligible": sign in (-1, 1) and not unresolved and not null and not bool(row.get('null_or_no_effect')),
            "direction_derivation": "explicit_binary_direction_preserved_independently_of_statistics",
            "relationship_kind": "association" if association else "unresolved_relation",
            # Legacy tuples have no endpoint/panel/contrast span bindings. Keep
            # their conservative screening guard without asserting scoped NS.
            "nonsignificance_reported": None, "nonsignificance_wording_present": null,
            "statistical_significance_status": "UNKNOWN", "statistical_scope": "LEGACY_UNVERIFIED",
            "zero_effect_asserted": False,
            "causal_sign": None, "comparator_orientation": row.get("comparator_orientation", "unknown"),
            "tested_arm": row.get("tested_arm"), "reference_arm": row.get("reference_arm"),
            "reason": "legacy_unscoped_nonsignificance_wording; direction preserved, screening withheld" if null else
                      "direction_unresolved_or_neutral" if sign is None else "extracted_binary_direction_only"}
