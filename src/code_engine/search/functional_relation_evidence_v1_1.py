"""Generic V1_1 refinement for deterministic pre-acquisition relation evidence."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import re
from typing import Any

from code_engine.search import functional_relation_evidence_v1 as v1


@dataclass(frozen=True)
class FunctionalRelationEvidenceDecisionV1_1(v1.FunctionalRelationEvidenceDecisionV1):
    base_v1_evidence_state: str = "UNRESOLVED"
    composition_provenance: tuple[dict[str, Any], ...] = ()
    refinement_version: str = "FunctionalRelationEvidenceV1_1"


EXTRA_REASON_CODES = {
    "SUBJECT_CAUSAL_PREDICATE", "CONSTITUTIVE_ACTIVATION", "DOMINANT_NEGATIVE_EVIDENCE",
    "DEFICIENT_CELL_EVIDENCE", "LOCAL_ABBREVIATION_RESOLVED", "BOUNDED_ADJACENT_COMPOSITION",
    "SHARED_INTERVENTION_CONTEXT", "EXPLICIT_ANAPHOR_CONTEXT", "POSITIVE_ASSOCIATION_REQUIRED",
    "PARSER_UNCERTAINTY_FAIL_CLOSED", "ALTERNATIVE_SINGLE_TARGET_PERTURBATION",
}


def _unique(values):
    return list(dict.fromkeys(values))


def _merge_policy(base_policy, policy):
    merged = dict(base_policy)
    for key in ("positive_perturbation_patterns", "negative_perturbation_patterns",
                "positive_response_patterns", "negative_response_patterns", "multi_target_patterns"):
        merged[key] = _unique([*base_policy.get(key, []), *policy.get(key, [])])
    return merged


def _local_abbreviations(text, surfaces):
    aliases = []
    for match in re.finditer(r"([a-z][a-z0-9 /-]{4,90}?)\s*\(([a-z][a-z0-9-]{1,15})\)", text):
        long_form = " ".join(match.group(1).split())
        abbreviation = match.group(2)
        if any(surface in long_form or long_form.endswith(surface) for surface in surfaces):
            aliases.append(abbreviation)
    return aliases


def _subject_surfaces(target, text):
    surfaces = list(v1.target_subject_surfaces(target))
    core = re.sub(r"\s+(?:activation|inhibition)$", "", v1._normalized(target.get("subject") or ""))
    if core.endswith(" receptor"):
        abbreviated = core[:-len(" receptor")].rstrip() + "r"
        surfaces.extend([abbreviated, abbreviated.replace("-", "")])
        if core in text:
            surfaces.extend(["h" + abbreviated, "h" + abbreviated.replace("-", "")])
    surfaces.extend(_local_abbreviations(text, surfaces))
    return _unique(sorted((item for item in surfaces if item), key=lambda item: (-len(item), item)))


def _endpoint_surfaces(target, text):
    surfaces = list(v1.target_endpoint_surfaces(target))
    for surface in list(surfaces):
        roman = re.fullmatch(r"(.+?)\s+([ivx]+)(?:\s+expression)?", surface)
        if roman:
            surfaces.append(f"type {roman.group(2)} {roman.group(1)}")
    surfaces.extend(_local_abbreviations(text, surfaces))
    return _unique(sorted((item for item in surfaces if item), key=lambda item: (-len(item), item)))


def _role(sentence, merged_policy, policy):
    base = v1._role(sentence, merged_policy)
    if base in {"BACKGROUND_PRIOR_WORK", "DISCUSSION_SPECULATION",
                "CURRENT_STUDY_PRIMARY"}:
        return base
    if sentence["field"] == "title":
        return "CURRENT_STUDY_SUPPORTING"
    if any(re.match(r"^" + pattern, sentence["text"])
           for pattern in policy["explicit_anaphor_patterns"]):
        return "CURRENT_STUDY_SUPPORTING"
    if any(re.search(pattern, sentence["text"]) for pattern in policy["current_result_patterns"]):
        return "CURRENT_STUDY_SUPPORTING"
    return "UNRESOLVED"


def _relative_polarity(target_subject, underlying):
    normalized = v1._normalized(target_subject)
    if normalized.endswith(" inhibition"):
        if underlying == "POSITIVE":
            return "NEGATIVE"
        if underlying == "NEGATIVE":
            return "POSITIVE"
    return underlying


def _specific_perturbation(sentence, subjects, endpoints, target, merged_policy, policy):
    base = v1._specific_perturbation(
        sentence, subjects, endpoints, merged_policy, target.get("subject") or ""
    ) if subjects else None
    candidates = [] if not base else list(base["candidates"])
    text = sentence["text"]
    for subject in subjects:
        surface = subject["surface"]
        start, end = subject["normalized_start"], subject["normalized_end"]
        after = text[end:end + 40]
        if re.match(r"^[- ](?:deficient|knock[- ]?down|knock[- ]?out)\b", after):
            cue_match = re.match(r"^[- ]([^ ]+)", after)
            candidates.append({"polarity": "NEGATIVE", "cue": {
                "pattern": "subject_suffix_loss", "start": end + cue_match.start(1),
                "end": end + cue_match.end(1), "text": cue_match.group(1),
            }, "subject": subject})
        alternative = re.search(
            r"\b(?:silenc(?:e|es|ed|ing)|knock[- ]?down|knock[- ]?out|inhibit(?:s|ed|ion)?|block(?:s|ed|ing)?)"
            r"\s+of\s+[a-z0-9-]+\s+or\s+" + re.escape(surface) + r"\b", text
        )
        if alternative:
            candidates.append({"polarity": "NEGATIVE", "cue": {
                "pattern": "alternative_single_target", "start": alternative.start(),
                "end": alternative.end(), "text": alternative.group(0),
            }, "subject": subject})
        receptor_inhibitor = re.search(
            r"\b(?:an?\s+)?inhibitor of\s+" + re.escape(surface) + r"(?:\s+receptor)?(?:\s+type\s+[a-z0-9-]+)?\b",
            text,
        )
        if receptor_inhibitor:
            candidates.append({"polarity": "NEGATIVE", "cue": {
                "pattern": "target_receptor_inhibitor", "start": receptor_inhibitor.start(),
                "end": receptor_inhibitor.end(), "text": receptor_inhibitor.group(0),
            }, "subject": subject})
        engagement = re.search(
            r"\b(?:bound to|engag(?:e|es|ed|ing))\s+(?:the\s+)?(?:h)?" + re.escape(surface) + r"\b",
            text,
        )
        if engagement:
            candidates.append({"polarity": "POSITIVE", "cue": {
                "pattern": "explicit_target_engagement", "start": engagement.start(),
                "end": engagement.end(), "text": engagement.group(0),
            }, "subject": subject})
        targeted_inhibition = re.search(
            r"\binhibit(?:s|ed|ing)?\s+(?:the\s+)?(?:activation|activity|expression)"
            r"(?:\s+step)?\s+of\s+(?:the\s+)?" + re.escape(surface) + r"\b",
            text,
        )
        if targeted_inhibition:
            candidates.append({"polarity": "NEGATIVE", "cue": {
                "pattern": "targeted_subject_inhibition", "start": targeted_inhibition.start(),
                "end": targeted_inhibition.end(), "text": targeted_inhibition.group(0),
            }, "subject": subject})
    if not candidates:
        return None
    adjusted = [{**item, "polarity": _relative_polarity(target.get("subject") or "", item["polarity"])}
                for item in candidates]
    polarities = {item["polarity"] for item in adjusted}
    multi = bool(base and base["multi_target"]) or any(
        re.search(pattern, text) for pattern in policy["multi_target_patterns"]
    )
    return {"polarity": next(iter(polarities)) if len(polarities) == 1 else "MIXED",
            "candidates": adjusted, "multi_target": multi}


def _response(sentence, endpoints, target, merged_policy):
    response = v1._endpoint_response(
        sentence, endpoints, target.get("object") or "", merged_policy
    ) if endpoints else None
    if not endpoints:
        return response
    negative = v1._cue_hits(sentence["text"], merged_policy["negative_response_patterns"])
    positive = v1._cue_hits(sentence["text"], merged_policy["positive_response_patterns"])
    for negative_cue in negative:
        for positive_cue in positive:
            for endpoint in endpoints:
                if (negative_cue["end"] <= positive_cue["start"]
                        and positive_cue["end"] <= endpoint["normalized_start"]
                        and positive_cue["start"] - negative_cue["end"] <= 4
                        and endpoint["normalized_start"] - positive_cue["end"] <= 32):
                    return {"direction": "DECREASE", "linked": [{
                        "direction": "DECREASE", "cue": negative_cue, "endpoint": endpoint,
                        "distance": endpoint["normalized_start"] - negative_cue["end"],
                    }]}
    return response


def _subject_causal_predicate(row, relation_sign):
    if not row["subjects"] or not row["response"]:
        return None
    compatible = []
    for subject in row["subjects"]:
        prefix = row["text"][max(0, subject["normalized_start"] - 48):subject["normalized_start"]]
        if re.search(r"\b(?:activat(?:e|es|ed)|stimulat(?:e|es|ed)|induc(?:e|es|ed))\s+$", prefix):
            continue
        for linked in row["response"]["linked"]:
            cue, endpoint = linked["cue"], linked["endpoint"]
            if subject["normalized_end"] <= cue["start"] <= endpoint["normalized_start"]:
                if endpoint["normalized_start"] - cue["end"] > 24:
                    continue
                between = row["text"][subject["normalized_end"]:cue["start"]]
                if re.fullmatch(r"\s*(?:directly\s+|significantly\s+|specifically\s+|also\s+)?", between):
                    direction = v1._direction_compatibility(relation_sign, "POSITIVE", linked["direction"])
                    if direction == "COMPATIBLE":
                        compatible.append((subject, linked))
    return compatible[0] if compatible else None


def _necessity(row, target):
    if not row["subjects"] or not row["endpoints"]:
        return False
    text = row["text"]
    for subject in row["subjects"]:
        surface = re.escape(subject["surface"])
        if re.search(r"(?:dependent on|requires|required for|essential for)\s+(?:the\s+)?" + surface, text):
            return True
        if re.search(surface + r"(?:\s+activation)?[- ]dependent\b", text):
            return True
        if re.search(surface + r"-\s+and\s+.{0,160}-dependent", text):
            return True
    return False


def _shared_context(left, right, policy, subject_surfaces, endpoint_surfaces):
    if any(re.match(r"^" + pattern, right["text"]) for pattern in policy["explicit_anaphor_patterns"]):
        return "EXPLICIT_ANAPHOR_CONTEXT", []
    stop = {"results", "result", "study", "cells", "mice", "treatment", "activation", "inhibition",
            "expression", "increased", "decreased", "signaling", "pathway", "response", "effect",
            "these", "this", "which", "with", "from", "that", "were", "both", "pathways",
            "proteins", "targets", "fibrosis", "collagen", "analysis", "effects", "significantly",
            "inhibited", "agonists", "receptor", "dependent", "current"}
    target_text = " ".join([*subject_surfaces, *endpoint_surfaces])
    target_tokens = set(target_text.split()) | set(target_text.replace("-", " ").split())
    left_tokens = set(re.findall(r"\b[a-z][a-z0-9-]{4,}\b", left["text"]))
    right_tokens = set(re.findall(r"\b[a-z][a-z0-9-]{4,}\b", right["text"]))
    shared = sorted(token for token in (left_tokens & right_tokens) - stop - target_tokens
                    if len(token) >= 8 or any(character.isdigit() for character in token) or "-" in token)
    return ("SHARED_INTERVENTION_CONTEXT", shared) if shared else (None, [])


def _evidence_record(row):
    return {"field": row["field"], "sentence_index": row["sentence_index"], "sentence": row["text"],
            "evidence_role": row["role"],
            "subject_surfaces": [item["surface"] for item in row["subjects"]],
            "endpoint_surfaces": [item["surface"] for item in row["endpoints"]]}


def decide_functional_relation_evidence_v1_1(
    packet_id: str,
    target: dict[str, Any],
    *,
    title: str,
    abstract: str,
    publication_metadata: dict[str, Any] | None,
    base_policy: dict[str, Any],
    policy: dict[str, Any],
) -> FunctionalRelationEvidenceDecisionV1_1:
    """Refine V1 with generic grammar and bounded local composition only."""
    base = v1.decide_functional_relation_evidence_v1(
        packet_id, target, title=title, abstract=abstract,
        publication_metadata=publication_metadata, policy=base_policy,
    )
    applicability, relation = v1.determine_applicability(target, base_policy)
    text = v1._normalized(f"{title} {abstract}")
    subject_surfaces = _subject_surfaces(target, text)
    endpoint_surfaces = _endpoint_surfaces(target, text)
    merged = _merge_policy(base_policy, policy)
    rows = []
    for sentence in v1._sentences(title, abstract):
        subjects = v1._matches(sentence, subject_surfaces, "subject")
        endpoints = v1._matches(sentence, endpoint_surfaces, "endpoint")
        role = _role(sentence, merged, policy)
        row = {**sentence, "subjects": subjects, "endpoints": endpoints, "role": role, "policy": policy}
        row["perturbation"] = _specific_perturbation(sentence, subjects, endpoints, target, merged, policy)
        row["response"] = _response(sentence, endpoints, target, merged)
        if (row["role"] == "UNRESOLVED" and subjects and endpoints
                and row["perturbation"] and row["response"]):
            row["role"] = "CURRENT_STUDY_SUPPORTING"
        row["necessity"] = _necessity(row, target)
        row["multi"] = any(re.search(pattern, row["text"]) for pattern in policy["multi_target_patterns"])
        row["association"] = any(re.search(pattern, row["text"]) for pattern in base_policy["association_patterns"])
        row["resistant_association"] = any(re.search(pattern, row["text"])
                                             for pattern in base_policy["resistant_sensitive_association_patterns"])
        rows.append(row)

    current = {"CURRENT_STUDY_PRIMARY", "CURRENT_STUDY_SUPPORTING"}
    direct = []
    chains = []
    multi = []
    associations = []
    backgrounds = []
    provenance = []
    for row in rows:
        both = bool(row["subjects"] and row["endpoints"])
        if both and row["role"] in current:
            causal = _subject_causal_predicate(row, relation["sign"])
            if row["perturbation"] and row["response"] and v1._independent_direct_pair(row["perturbation"], row["response"]):
                compatibility = v1._direction_compatibility(
                    relation["sign"], row["perturbation"]["polarity"], row["response"]["direction"]
                )
                if compatibility == "COMPATIBLE":
                    (multi if row["perturbation"]["multi_target"] else direct).append(row)
            elif causal:
                row["causal_predicate"] = causal
                direct.append(row)
            elif row["necessity"]:
                chains.append(row)
            elif row["multi"] and row["response"]:
                multi.append(row)
            elif row["association"] or row["resistant_association"]:
                associations.append(row)
        if both and row["role"] == "BACKGROUND_PRIOR_WORK":
            backgrounds.append(row)

    max_distance = policy["maximum_local_composition_sentence_distance"]
    for perturbation_row in rows:
        if (not perturbation_row["perturbation"] or perturbation_row["role"] not in current
                or perturbation_row["perturbation"]["multi_target"]):
            continue
        for response_row in rows:
            if not response_row["response"] or response_row["role"] not in current:
                continue
            distance = abs(response_row["sentence_index"] - perturbation_row["sentence_index"])
            if perturbation_row["field"] != response_row["field"] or not 0 < distance <= max_distance:
                continue
            left, right = sorted((perturbation_row, response_row), key=lambda row: row["sentence_index"])
            context_kind, tokens = _shared_context(left, right, policy, subject_surfaces, endpoint_surfaces)
            if context_kind:
                compatibility = v1._direction_compatibility(
                    relation["sign"], perturbation_row["perturbation"]["polarity"],
                    response_row["response"]["direction"]
                )
                if compatibility == "COMPATIBLE":
                    chains.extend([perturbation_row, response_row])
                    provenance.append({"composition_type": "adjacent_current_result_sentences",
                                       "left_sentence_index": left["sentence_index"],
                                       "right_sentence_index": right["sentence_index"],
                                       "context_rule": context_kind, "shared_context_tokens": tokens})

    selected = []
    reasons = []
    perturbation_polarity = endpoint_direction = direction = "UNRESOLVED"
    specificity = "UNRESOLVED"
    response_link = "UNRESOLVED"
    if not applicability.applicable:
        state = "UNRESOLVED"
        reasons = ["CURRENT_STUDY_RELATION_UNRESOLVED"]
    elif direct:
        selected = list({(row["field"], row["sentence_index"]): row for row in direct}.values())
        chosen = selected[0]
        if chosen.get("causal_predicate"):
            perturbation_polarity = "POSITIVE"
            endpoint_direction = chosen["causal_predicate"][1]["direction"]
            reasons = ["DIRECT_SUBJECT_PERTURBATION", "SUBJECT_CAUSAL_PREDICATE",
                       "ENDPOINT_RESPONSE_PRESENT", "DIRECTION_COMPATIBLE"]
        else:
            perturbation_polarity = chosen["perturbation"]["polarity"]
            endpoint_direction = chosen["response"]["direction"]
            reasons = [*v1._reason_for_perturbation(chosen["perturbation"]),
                       "ENDPOINT_RESPONSE_PRESENT", "DIRECTION_COMPATIBLE"]
            cue_text = " ".join(item["cue"]["text"] for item in chosen["perturbation"]["candidates"])
            if "constitutively active" in cue_text:
                reasons.append("CONSTITUTIVE_ACTIVATION")
            if "dominant" in cue_text:
                reasons.append("DOMINANT_NEGATIVE_EVIDENCE")
            if "deficient" in cue_text:
                reasons.append("DEFICIENT_CELL_EVIDENCE")
            if "alternative_single_target" in " ".join(item["cue"]["pattern"] for item in chosen["perturbation"]["candidates"]):
                reasons.append("ALTERNATIVE_SINGLE_TARGET_PERTURBATION")
        direction = "COMPATIBLE"
        state = "DIRECT_FUNCTIONAL"
        specificity = "EXACT_SUBJECT"
        response_link = "RESCUE_OR_NECESSITY" if any(
            re.search(pattern, chosen["text"]) for pattern in policy["rescue_patterns"]
        ) else "DIRECT_RESPONSE"
    elif chains:
        selected = list({(row["field"], row["sentence_index"]): row for row in chains}.values())
        perturbations = [row["perturbation"] for row in selected if row["perturbation"]]
        responses = [row["response"] for row in selected if row["response"]]
        if any(row["necessity"] for row in selected) and not perturbations:
            perturbation_polarity, endpoint_direction, direction = "NEGATIVE", "DECREASE", "COMPATIBLE"
            reasons = ["NECESSITY_EVIDENCE", "MECHANISTIC_CHAIN_PRESENT", "DIRECTION_COMPATIBLE"]
        else:
            perturbation_polarity = perturbations[0]["polarity"] if perturbations else "UNRESOLVED"
            endpoint_direction = responses[0]["direction"] if responses else "UNRESOLVED"
            direction = v1._direction_compatibility(relation["sign"], perturbation_polarity, endpoint_direction)
            reasons = ["MECHANISTIC_CHAIN_PRESENT", "ENDPOINT_RESPONSE_PRESENT"]
            reasons.append("DIRECTION_COMPATIBLE" if direction == "COMPATIBLE" else "CURRENT_STUDY_RELATION_UNRESOLVED")
        if direction == "COMPATIBLE":
            state = "FUNCTIONAL_CHAIN"
        else:
            state = "UNRESOLVED"
        specificity = "EXACT_SUBJECT"
        response_link = "MECHANISTIC_CHAIN"
        if provenance:
            reasons.extend(["BOUNDED_ADJACENT_COMPOSITION", provenance[0]["context_rule"]])
    elif base.evidence_state in {"DIRECT_FUNCTIONAL", "FUNCTIONAL_CHAIN"} and base.direction_compatibility == "COMPATIBLE":
        payload = asdict(base)
        payload["policy_version"] = policy["policy_version"]
        return FunctionalRelationEvidenceDecisionV1_1(
            **payload, base_v1_evidence_state=base.evidence_state,
            composition_provenance=(), refinement_version="FunctionalRelationEvidenceV1_1",
        )
    elif multi or base.evidence_state == "MULTI_TARGET_AMBIGUOUS":
        selected = multi
        state, specificity, response_link = "MULTI_TARGET_AMBIGUOUS", "MULTI_TARGET", "UNRESOLVED"
        reasons = ["MULTI_TARGET_INTERVENTION", "TARGET_CONTRIBUTION_NOT_ISOLATED"]
    elif associations or (base.evidence_state == "ASSOCIATION_ONLY" and (
            "CORRELATION_ONLY" in base.reason_codes or "RESISTANT_SENSITIVE_ASSOCIATION_ONLY" in base.reason_codes)):
        selected = associations
        state, specificity, response_link = "ASSOCIATION_ONLY", "NO_SUBJECT_PERTURBATION", "CORRELATION"
        reasons = ["NO_TARGET_PERTURBATION_EVIDENCE", "CORRELATION_ONLY", "POSITIVE_ASSOCIATION_REQUIRED"]
    elif backgrounds or base.evidence_state == "BACKGROUND_ONLY":
        selected = backgrounds
        state, specificity, response_link = "BACKGROUND_ONLY", "NO_SUBJECT_PERTURBATION", "NO_LINK"
        reasons = ["BACKGROUND_PROPOSITION_ONLY", "NO_TARGET_PERTURBATION_EVIDENCE"]
    else:
        selected = [row for row in rows if row["subjects"] or row["endpoints"]]
        state, specificity, response_link = "UNRESOLVED", "UNRESOLVED", "UNRESOLVED"
        reasons = ["CURRENT_STUDY_RELATION_UNRESOLVED", "PARSER_UNCERTAINTY_FAIL_CLOSED"]
        if base.evidence_state == "ASSOCIATION_ONLY" and "COCHANGE_ONLY" in base.reason_codes:
            reasons.append("POSITIVE_ASSOCIATION_REQUIRED")

    selected_roles = {row["role"] for row in selected}
    all_roles = {row["role"] for row in rows if row["subjects"] and row["endpoints"]}
    evidence_role = v1._overall_role(selected_roles, all_roles)
    observed_subjects = tuple({**item, "evidence_role": row["role"]}
                              for row in rows for item in row["subjects"])
    observed_endpoints = tuple({**item, "evidence_role": row["role"]}
                               for row in rows for item in row["endpoints"])
    reason_codes = tuple(_unique(reasons))
    allowed = v1.REASON_CODES | EXTRA_REASON_CODES
    if not set(reason_codes) <= allowed:
        raise ValueError(f"unknown V1_1 reason code: {set(reason_codes) - allowed}")
    return FunctionalRelationEvidenceDecisionV1_1(
        packet_id=packet_id, applicable=applicability.applicable, applicability=asdict(applicability),
        target_subject={"raw": target.get("subject"), "normalized_surfaces": subject_surfaces},
        target_relation_family=relation,
        target_endpoint={"object": target.get("object"), "measurement_target": target.get("measurement_target"),
                         "measurement_property_endpoint": target.get("measurement_property_endpoint"),
                         "normalized_surfaces": endpoint_surfaces},
        evidence_state=state, evidence_role=evidence_role,
        subject_perturbation_specificity=specificity, response_link_state=response_link,
        observed_subject_surfaces=observed_subjects, observed_endpoint_surfaces=observed_endpoints,
        perturbation_polarity=perturbation_polarity, endpoint_response_direction=endpoint_direction,
        direction_compatibility=direction, reason_codes=reason_codes,
        source_evidence_spans_or_sentences=tuple(_evidence_record(row) for row in selected),
        resolver_status="resolved" if state != "UNRESOLVED" else "unresolved",
        policy_version=policy["policy_version"], registry_version_if_any="existing_formal_relation_registry_v1",
        base_v1_evidence_state=base.evidence_state,
        composition_provenance=tuple(provenance) if state == "FUNCTIONAL_CHAIN" else (),
        refinement_version="FunctionalRelationEvidenceV1_1",
    )
