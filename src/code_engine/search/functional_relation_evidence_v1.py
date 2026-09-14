"""Deterministic pre-acquisition functional-relation evidence in shadow mode."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any, Literal

from code_engine.normalization.formal_relations import normalize_formal_relation
from code_engine.normalization.lexical import normalize_lexical_surface


EvidenceState = Literal[
    "DIRECT_FUNCTIONAL", "FUNCTIONAL_CHAIN", "ASSOCIATION_ONLY", "BACKGROUND_ONLY",
    "MULTI_TARGET_AMBIGUOUS", "UNRESOLVED",
]
EvidenceRole = Literal[
    "CURRENT_STUDY_PRIMARY", "CURRENT_STUDY_SUPPORTING", "BACKGROUND_PRIOR_WORK",
    "DISCUSSION_SPECULATION", "MIXED", "UNRESOLVED",
]
SubjectSpecificity = Literal[
    "EXACT_SUBJECT", "AUTHORIZED_EQUIVALENT", "UPSTREAM_OR_DOWNSTREAM_PROXY", "MULTI_TARGET",
    "NO_SUBJECT_PERTURBATION", "UNRESOLVED",
]
ResponseLinkState = Literal[
    "DIRECT_RESPONSE", "RESCUE_OR_NECESSITY", "MECHANISTIC_CHAIN", "CONCURRENT_CHANGE",
    "CORRELATION", "NO_LINK", "UNRESOLVED",
]

EVIDENCE_STATES = (
    "DIRECT_FUNCTIONAL", "FUNCTIONAL_CHAIN", "ASSOCIATION_ONLY", "BACKGROUND_ONLY",
    "MULTI_TARGET_AMBIGUOUS", "UNRESOLVED",
)
REASON_CODES = {
    "DIRECT_SUBJECT_PERTURBATION", "TARGET_SPECIFIC_KNOCKDOWN", "TARGET_SPECIFIC_KNOCKOUT",
    "TARGET_SPECIFIC_INHIBITION", "TARGET_SPECIFIC_ACTIVATION", "GAIN_OF_FUNCTION",
    "LOSS_OF_FUNCTION", "RESCUE_EVIDENCE", "NECESSITY_EVIDENCE", "MECHANISTIC_CHAIN_PRESENT",
    "ENDPOINT_RESPONSE_PRESENT", "DIRECTION_COMPATIBLE", "DIRECTION_CONFLICT", "COCHANGE_ONLY",
    "CORRELATION_ONLY", "RESISTANT_SENSITIVE_ASSOCIATION_ONLY", "MULTI_TARGET_INTERVENTION",
    "TARGET_CONTRIBUTION_NOT_ISOLATED", "BACKGROUND_PROPOSITION_ONLY",
    "CURRENT_STUDY_RELATION_UNRESOLVED", "NO_TARGET_PERTURBATION_EVIDENCE",
    "NO_ENDPOINT_RESPONSE_EVIDENCE",
}


@dataclass(frozen=True)
class FunctionalRelationApplicabilityV1:
    applicable: bool
    target_relation_family: str
    requires_functional_evidence: bool
    reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class FunctionalRelationEvidenceDecisionV1:
    packet_id: str
    applicable: bool
    applicability: dict[str, Any]
    target_subject: dict[str, Any]
    target_relation_family: dict[str, Any]
    target_endpoint: dict[str, Any]
    evidence_state: EvidenceState
    evidence_role: EvidenceRole
    subject_perturbation_specificity: SubjectSpecificity
    response_link_state: ResponseLinkState
    observed_subject_surfaces: tuple[dict[str, Any], ...]
    observed_endpoint_surfaces: tuple[dict[str, Any], ...]
    perturbation_polarity: str
    endpoint_response_direction: str
    direction_compatibility: str
    reason_codes: tuple[str, ...]
    source_evidence_spans_or_sentences: tuple[dict[str, Any], ...]
    resolver_status: str
    policy_version: str
    registry_version_if_any: str
    decision_mode: str = "deterministic"
    preacquisition_only: bool = True
    modifies_tier: bool = False
    modifies_acquisition: bool = False
    modifies_sample_membership: bool = False
    modifies_reject_status: bool = False


def _unique(values):
    return list(dict.fromkeys(values))


def _normalized(value):
    return normalize_lexical_surface(value).normalized_surface


def _bounded(text: str, surface: str):
    return [match.span() for match in re.finditer(r"(?<!\w)" + re.escape(surface) + r"(?!\w)", text)]


def _surface_values(values):
    result = []
    for value in values:
        if not value:
            continue
        for part in re.split(r"\s+(?:or|and)\s+|\s*/\s*", str(value)):
            normalized = _normalized(part)
            if normalized and (len(normalized) >= 4 or len(normalized.split()) > 1):
                result.append(normalized)
        normalized_full = _normalized(value)
        if normalized_full:
            result.append(normalized_full)
    return _unique(sorted(result, key=lambda item: (-len(item), item)))


def target_subject_surfaces(target: dict[str, Any]):
    raw = str(target.get("subject") or "")
    normalized = _normalized(raw)
    stripped = re.sub(
        r"\s+(?:activation|inhibition|signaling|signalling|activity|expression)$", "", normalized
    ).strip()
    return _surface_values([normalized, stripped])


def target_endpoint_surfaces(target: dict[str, Any]):
    # A measurement property such as "activation" or "phosphorylation" is not
    # an endpoint identity by itself.  Matching it without the measurement
    # target lets an unrelated pathway-state word masquerade as the endpoint.
    therapy = _normalized(target.get("therapy") or "")
    object_value = target.get("object")
    values = [target.get("measurement_target")]
    if _normalized(object_value or "") != therapy:
        values.append(object_value)
    endpoint = _normalized(target.get("object") or "")
    for suffix in (" resistance", " sensitivity"):
        if endpoint.endswith(suffix):
            therapy = endpoint[:-len(suffix)].strip() or therapy
            break
    if therapy:
        values.extend([
            f"{therapy}-resistant", f"{therapy} resistant", f"resistant to {therapy}",
            f"{therapy}-sensitive", f"{therapy} sensitive", f"sensitive to {therapy}",
            f"{therapy} sensitivity", f"sensitivity to {therapy}",
        ])
    surfaces = _surface_values(values)
    # Acceptable-evidence entries are often descriptive constraints rather
    # than alias lists. Preserve each complete phrase but do not split it into
    # unsafe generic fragments such as "activation" or "resistant".
    for value in target.get("acceptable_endpoint_evidence") or []:
        normalized = _normalized(value)
        if normalized and (len(normalized) >= 4 or len(normalized.split()) > 1):
            surfaces.append(normalized)
    return _unique(sorted(surfaces, key=lambda item: (-len(item), item)))


def normalize_target_relation(target: dict[str, Any], policy: dict[str, Any]):
    raw = _normalized(target.get("relation_family") or "").replace(" ", "_")
    formal = normalize_formal_relation({"relation_family": raw})
    if formal:
        semantic_kind = "association" if formal.semantic_kind == "association" else "functional"
        return {"raw": target.get("relation_family"), "normalized": formal.relation,
                "family": formal.family, "sign": formal.sign, "semantic_kind": semantic_kind,
                "source": "existing_formal_relation_registry"}
    configured = policy["relation_semantics"].get(raw)
    if configured:
        return {"raw": target.get("relation_family"), "normalized": raw, **configured,
                "source": "functional_relation_evidence_policy_v1"}
    return {"raw": target.get("relation_family"), "normalized": raw, "family": "unresolved",
            "sign": 0, "semantic_kind": "unresolved", "source": "unresolved"}


def determine_applicability(target: dict[str, Any], policy: dict[str, Any]):
    relation = normalize_target_relation(target, policy)
    if relation["semantic_kind"] == "functional":
        applicability = FunctionalRelationApplicabilityV1(
            applicable=True, target_relation_family=relation["family"],
            requires_functional_evidence=True, reason_codes=("FUNCTIONAL_TARGET_RELATION",),
        )
    elif relation["semantic_kind"] == "association":
        applicability = FunctionalRelationApplicabilityV1(
            applicable=False, target_relation_family=relation["family"],
            requires_functional_evidence=False, reason_codes=("ASSOCIATIVE_TARGET_RELATION",),
        )
    else:
        applicability = FunctionalRelationApplicabilityV1(
            applicable=False, target_relation_family="unresolved",
            requires_functional_evidence=False, reason_codes=("TARGET_RELATION_UNRESOLVED",),
        )
    return applicability, relation


def _sentences(title: str, abstract: str):
    records = []
    for field, text in (("title", title), ("abstract", abstract)):
        normalized = _normalized(text)
        parts = [part.strip() for part in re.split(r"(?<=[.;])\s+", normalized) if part.strip()]
        cursor = 0
        for index, part in enumerate(parts):
            start = normalized.find(part, cursor)
            end = start + len(part)
            cursor = end
            records.append({"field": field, "sentence_index": index, "text": part,
                            "normalized_start": start, "normalized_end": end})
    return records


def _role(sentence: dict[str, Any], policy: dict[str, Any]):
    text = sentence["text"]
    if any(re.search(pattern, text) for pattern in policy["background_patterns"]):
        return "BACKGROUND_PRIOR_WORK"
    if any(re.search(pattern, text) for pattern in policy["current_study_patterns"]):
        return "CURRENT_STUDY_PRIMARY"
    if any(re.search(pattern, text) for pattern in policy["discussion_speculation_patterns"]):
        return "DISCUSSION_SPECULATION"
    if sentence["field"] == "title":
        return "CURRENT_STUDY_SUPPORTING"
    perturbation_language = any(
        _cue_hits(text, policy[key])
        for key in ("positive_perturbation_patterns", "negative_perturbation_patterns")
    )
    linked_result_language = text.startswith("this ") and (
        any(re.search(pattern, text) for pattern in policy["chain_link_patterns"])
        or any(_cue_hits(text, policy[key]) for key in ("positive_response_patterns", "negative_response_patterns"))
    )
    if perturbation_language or linked_result_language or re.search(
            r"\b(?:assay|measur|analysis|analy[sz])", text):
        return "CURRENT_STUDY_SUPPORTING"
    return "UNRESOLVED"


def _matches(sentence, surfaces, kind):
    records = []
    for surface in surfaces:
        for start, end in _bounded(sentence["text"], surface):
            records.append({"surface": surface, "kind": kind, "field": sentence["field"],
                            "sentence_index": sentence["sentence_index"], "normalized_start": start,
                            "normalized_end": end})
    records.sort(key=lambda item: (item["normalized_start"], -(item["normalized_end"] - item["normalized_start"])))
    accepted = []
    for item in records:
        if any(other["normalized_start"] <= item["normalized_start"]
               and item["normalized_end"] <= other["normalized_end"] for other in accepted):
            continue
        accepted.append(item)
    return accepted


def _cue_hits(text, patterns):
    hits = []
    for pattern in patterns:
        hits.extend({"pattern": pattern, "start": match.start(), "end": match.end(), "text": match.group(0)}
                    for match in re.finditer(r"\b(?:" + pattern + r")\b", text))
    return sorted(hits, key=lambda item: (item["start"], item["pattern"]))


def _near(left, right, gap):
    return left["start"] <= right["end"] + gap and right["start"] <= left["end"] + gap


def _specific_perturbation(sentence, subject_matches, endpoint_matches, policy, target_subject):
    positive = _cue_hits(sentence["text"], policy["positive_perturbation_patterns"])
    negative = _cue_hits(sentence["text"], policy["negative_perturbation_patterns"])
    candidates = []
    allowed_between = {"", "of", "the", "of the", "genetically",
                       "selectively", "specifically", "pharmacologically", "directly",
                       "activity", "expression", "level", "levels"}
    for polarity, cues in (("POSITIVE", positive), ("NEGATIVE", negative)):
        for cue in cues:
            for subject in subject_matches:
                local_subject = {"start": subject["normalized_start"], "end": subject["normalized_end"]}
                if cue["start"] < local_subject["end"] and local_subject["start"] < cue["end"]:
                    continue
                between = sentence["text"][min(cue["end"], local_subject["end"]):max(cue["start"], local_subject["start"])]
                normalized_between = " ".join(between.split())
                adjacent = normalized_between in allowed_between
                if adjacent:
                    candidates.append({"polarity": polarity, "cue": cue, "subject": subject})
    if not candidates:
        return None
    finite_activation = re.compile(r"(?:activat|stimulat)(?:e|es|ed)$")
    direct_actor = re.compile(r"\bwe(?:\s+(?:directly|selectively|specifically))?\s*$")
    actor_filtered = []
    for item in candidates:
        cue = item["cue"]
        subject = item["subject"]
        if cue["end"] <= subject["normalized_start"] and finite_activation.fullmatch(cue["text"]):
            prefix = sentence["text"][max(0, cue["start"] - 64):cue["start"]]
            prefix = re.split(r"[.;]", prefix)[-1].strip()
            if prefix and not direct_actor.search(prefix):
                continue
        actor_filtered.append(item)
    candidates = actor_filtered
    if not candidates:
        return None
    normalized_target = _normalized(target_subject)
    state_match = re.search(r"\s+(activation|inhibition)$", normalized_target)
    if state_match:
        state_polarity = "POSITIVE" if state_match.group(1) == "activation" else "NEGATIVE"
        # A hyphenated third-intervention state (for example,
        # "contraction-stimulated X activation") is co-change, not a direct
        # perturbation of X. Explicit X agonists/inhibitors remain admissible.
        candidates = [
            item for item in candidates
            if item["polarity"] != state_polarity
            or item["cue"]["start"] == 0
            or sentence["text"][item["cue"]["start"] - 1] != "-"
        ]
        if not candidates:
            return None
    polarities = {item["polarity"] for item in candidates}
    polarity = next(iter(polarities)) if len(polarities) == 1 else "MIXED"
    coordination = any(re.search(pattern, sentence["text"]) for pattern in policy["multi_target_patterns"])
    response_word = re.compile(r"(?:increas|decreas|reduc|enhanc|promot|suppress|attenuat|abolish|induc|activat|phosphorylat|restor|rescu|sensitiz|observ|found|show|measur)")
    for candidate in candidates:
        subject = candidate["subject"]
        tail = sentence["text"][subject["normalized_end"]:subject["normalized_end"] + 48]
        coordinated = re.match(r"\s+(?:and|or)\s+([a-z0-9-]+)", tail)
        coordinated_start = (subject["normalized_end"] + coordinated.start(1)
                             if coordinated else -1)
        coordinated_is_endpoint = any(
            endpoint["normalized_start"] <= coordinated_start < endpoint["normalized_end"]
            for endpoint in endpoint_matches
        )
        if (coordinated and not coordinated_is_endpoint
                and not response_word.match(coordinated.group(1))):
            coordination = True
    return {"polarity": polarity, "candidates": candidates, "multi_target": coordination}


def _causal_state_subject(sentence, subject_matches, endpoint_response, target_subject):
    normalized_target = _normalized(target_subject)
    if not re.search(r"\s+(?:activation|inhibition)$", normalized_target) or not endpoint_response:
        return None
    full_matches = [item for item in subject_matches if item["surface"] == normalized_target]
    candidates = []
    for subject in full_matches:
        for response in endpoint_response["linked"]:
            cue = response["cue"]
            if subject["normalized_end"] <= cue["start"] and cue["start"] - subject["normalized_end"] <= 48:
                candidates.append({"polarity": "POSITIVE", "cue": {
                    "pattern": "target_state_as_causal_antecedent", "start": subject["normalized_start"],
                    "end": subject["normalized_end"], "text": normalized_target,
                }, "subject": subject})
    return {"polarity": "POSITIVE", "candidates": candidates, "multi_target": False} if candidates else None


def _endpoint_response(sentence, endpoint_matches, target_endpoint, policy):
    positive = _cue_hits(sentence["text"], policy["positive_response_patterns"])
    negative = _cue_hits(sentence["text"], policy["negative_response_patterns"])
    gap = policy["maximum_endpoint_response_gap_chars"]
    linked = []
    for direction, cues in (("INCREASE", positive), ("DECREASE", negative)):
        for cue in cues:
            for endpoint in endpoint_matches:
                local_endpoint = {"start": endpoint["normalized_start"], "end": endpoint["normalized_end"]}
                overlaps = cue["start"] < local_endpoint["end"] and local_endpoint["start"] < cue["end"]
                cue_before = cue["end"] <= local_endpoint["start"]
                endpoint_before = local_endpoint["end"] <= cue["start"]
                between = sentence["text"][min(cue["end"], local_endpoint["end"]):
                                           max(cue["start"], local_endpoint["start"])]
                after_endpoint_form = bool(
                    re.search(r"\b(?:was|were|is|are|became|becomes)\b", between)
                    or re.search(r"(?:ed|ing|ion|ment|al)$", cue["text"])
                    or cue["text"] in {"increase", "decrease", "loss of"}
                )
                directionally_linked = overlaps or cue_before or (endpoint_before and after_endpoint_form)
                if _near(cue, local_endpoint, gap) and directionally_linked and not re.search(r"[.;]", between):
                    distance = max(0, max(cue["start"], local_endpoint["start"])
                                   - min(cue["end"], local_endpoint["end"]))
                    linked.append({"direction": direction, "cue": cue, "endpoint": endpoint,
                                   "distance": distance})
    if not linked:
        return None
    # In constructions such as "abolished Y induction" or "inhibited
    # treatment-induced Y", the nearer nominal positive word names the
    # response being negated; it is not the observed direction.  Resolve that
    # scope before applying the nearest-cue rule.
    nominal_positive = re.compile(r"(?:activation|induction|phosphorylation|upregulation)$")
    scoped_negative = []
    for negative_item in (item for item in linked if item["direction"] == "DECREASE"):
        for positive_item in (item for item in linked if item["direction"] == "INCREASE"):
            if negative_item["endpoint"] != positive_item["endpoint"]:
                continue
            nearest_positive_distance = min(
                item["distance"] for item in linked
                if item["direction"] == "INCREASE" and item["endpoint"] == positive_item["endpoint"]
            )
            negative_cue = negative_item["cue"]
            positive_cue = positive_item["cue"]
            between = sentence["text"][negative_cue["end"]:positive_cue["start"]]
            if (negative_cue["start"] < positive_cue["start"]
                    and positive_item["distance"] == nearest_positive_distance
                    and nominal_positive.fullmatch(positive_cue["text"])
                    and not re.search(r"[.;]", between)
                    and positive_cue["start"] - negative_cue["end"] <= gap):
                scoped_negative.append(negative_item)
    if scoped_negative:
        linked = scoped_negative
    nearest = min(item["distance"] for item in linked)
    linked = [item for item in linked if item["distance"] == nearest]
    directions = {item["direction"] for item in linked}
    direction = next(iter(directions)) if len(directions) == 1 else "MIXED"
    normalized_target = _normalized(target_endpoint)
    for contrast in policy["endpoint_contrast_pairs"]:
        if contrast["target_contains"] in normalized_target and contrast["observed_contains"] in sentence["text"]:
            if direction == "INCREASE" and contrast["direction_multiplier"] == -1:
                direction = "DECREASE"
            elif direction == "DECREASE" and contrast["direction_multiplier"] == -1:
                direction = "INCREASE"
    return {"direction": direction, "linked": linked}


def _independent_direct_pair(perturbation, response):
    """Require distinct textual evidence for perturbation and response."""
    pairs = []
    for candidate in perturbation["candidates"]:
        perturbation_cue = candidate["cue"]
        for linked in response["linked"]:
            response_cue = linked["cue"]
            same_cue = (perturbation_cue["start"], perturbation_cue["end"]) == (
                response_cue["start"], response_cue["end"]
            )
            if not same_cue:
                pairs.append((candidate, linked))
    return pairs


def _direction_compatibility(relation_sign, perturbation, response):
    if perturbation not in {"POSITIVE", "NEGATIVE"} or response not in {"INCREASE", "DECREASE"}:
        return "UNRESOLVED"
    perturb_sign = 1 if perturbation == "POSITIVE" else -1
    response_sign = 1 if response == "INCREASE" else -1
    return "COMPATIBLE" if perturb_sign * response_sign == relation_sign else "CONFLICT"


def _reason_for_perturbation(perturbation):
    texts = " ".join(item["cue"]["text"] for item in perturbation["candidates"])
    reasons = ["DIRECT_SUBJECT_PERTURBATION"]
    if "knockdown" in texts:
        reasons.append("TARGET_SPECIFIC_KNOCKDOWN")
    if "knock-out" in texts or "knockout" in texts or "knock out" in texts:
        reasons.extend(["TARGET_SPECIFIC_KNOCKOUT", "LOSS_OF_FUNCTION"])
    if re.search(r"silenc|deplet|inhibit|block", texts):
        reasons.append("TARGET_SPECIFIC_INHIBITION")
    if re.search(r"activat|stimulat|agonist|treatment|exposure to|addition of", texts):
        reasons.append("TARGET_SPECIFIC_ACTIVATION")
    if re.search(r"overexpress|gain", texts):
        reasons.append("GAIN_OF_FUNCTION")
    if re.search(r"loss|deficien|delet", texts):
        reasons.append("LOSS_OF_FUNCTION")
    return _unique(reasons)


def _overall_role(selected_roles, all_relation_roles):
    current = {"CURRENT_STUDY_PRIMARY", "CURRENT_STUDY_SUPPORTING"}
    if selected_roles & current:
        if "BACKGROUND_PRIOR_WORK" in all_relation_roles or "DISCUSSION_SPECULATION" in all_relation_roles:
            return "MIXED"
        return "CURRENT_STUDY_PRIMARY" if "CURRENT_STUDY_PRIMARY" in selected_roles else "CURRENT_STUDY_SUPPORTING"
    if selected_roles == {"BACKGROUND_PRIOR_WORK"}:
        return "BACKGROUND_PRIOR_WORK"
    if selected_roles == {"DISCUSSION_SPECULATION"}:
        return "DISCUSSION_SPECULATION"
    return "UNRESOLVED"


def decide_functional_relation_evidence_v1(
    packet_id: str,
    target: dict[str, Any],
    *,
    title: str,
    abstract: str,
    publication_metadata: dict[str, Any] | None,
    policy: dict[str, Any],
) -> FunctionalRelationEvidenceDecisionV1:
    """Classify only target-linked current-study title/abstract evidence."""
    del publication_metadata
    applicability, relation = determine_applicability(target, policy)
    subject_surfaces = target_subject_surfaces(target)
    endpoint_surfaces = target_endpoint_surfaces(target)
    sentences = _sentences(title, abstract)
    analyzed = []
    all_subject, all_endpoint = [], []
    for sentence in sentences:
        subjects = _matches(sentence, subject_surfaces, "subject")
        endpoints = _matches(sentence, endpoint_surfaces, "endpoint")
        role = _role(sentence, policy)
        response = _endpoint_response(sentence, endpoints, target.get("object") or "", policy) if endpoints else None
        perturbation = _specific_perturbation(
            sentence, subjects, endpoints, policy, target.get("subject") or ""
        ) if subjects else None
        association = any(re.search(pattern, sentence["text"]) for pattern in policy["association_patterns"])
        resistant_association = any(re.search(pattern, sentence["text"])
                                    for pattern in policy["resistant_sensitive_association_patterns"])
        multi_target = any(re.search(pattern, sentence["text"]) for pattern in policy["multi_target_patterns"])
        rescue = any(re.search(pattern, sentence["text"]) for pattern in policy["rescue_patterns"])
        chain = any(re.search(pattern, sentence["text"]) for pattern in policy["chain_link_patterns"])
        if not perturbation and not association and not resistant_association:
            perturbation = _causal_state_subject(
                sentence, subjects, response, target.get("subject") or ""
            )
        record = {**sentence, "evidence_role": role, "subject_matches": subjects,
                  "endpoint_matches": endpoints, "subject_perturbation": perturbation,
                  "endpoint_response": response, "association_pattern": association,
                  "resistant_sensitive_association": resistant_association,
                  "multi_target_pattern": multi_target, "rescue_pattern": rescue,
                  "chain_link_pattern": chain}
        analyzed.append(record)
        all_subject.extend({**item, "evidence_role": role} for item in subjects)
        all_endpoint.extend({**item, "evidence_role": role} for item in endpoints)

    current_roles = {"CURRENT_STUDY_PRIMARY", "CURRENT_STUDY_SUPPORTING"}
    direct, multi, associations, cochanges, chains, backgrounds, speculations = [], [], [], [], [], [], []
    for row in analyzed:
        has_both = bool(row["subject_matches"] and row["endpoint_matches"])
        if has_both and row["evidence_role"] in current_roles:
            if row["multi_target_pattern"] and not row["subject_perturbation"]:
                multi.append(row)
            elif (row["subject_perturbation"] and row["endpoint_response"]
                  and _independent_direct_pair(row["subject_perturbation"], row["endpoint_response"])):
                if row["subject_perturbation"]["multi_target"]:
                    multi.append(row)
                else:
                    direct.append(row)
            elif row["association_pattern"] or row["resistant_sensitive_association"]:
                associations.append(row)
            elif row["endpoint_response"]:
                cochanges.append(row)
        if has_both and row["evidence_role"] == "BACKGROUND_PRIOR_WORK":
            backgrounds.append(row)
        if has_both and row["evidence_role"] == "DISCUSSION_SPECULATION":
            speculations.append(row)

    window = policy["adjacent_sentence_chain_window"]
    for subject_row in analyzed:
        if not subject_row["subject_perturbation"] or subject_row["evidence_role"] not in current_roles:
            continue
        for endpoint_row in analyzed:
            if endpoint_row["evidence_role"] not in current_roles or not endpoint_row["endpoint_response"]:
                continue
            if subject_row["field"] == endpoint_row["field"] and 0 < endpoint_row["sentence_index"] - subject_row["sentence_index"] <= window:
                if subject_row["chain_link_pattern"] or endpoint_row["chain_link_pattern"]:
                    chains.extend([subject_row, endpoint_row])

    reasons = []
    selected = []
    perturbation_polarity = "UNRESOLVED"
    endpoint_direction = "UNRESOLVED"
    direction = "UNRESOLVED"
    specificity: SubjectSpecificity = "UNRESOLVED"
    response_link: ResponseLinkState = "UNRESOLVED"
    if not applicability.applicable:
        state: EvidenceState = "UNRESOLVED"
        reasons = ["CURRENT_STUDY_RELATION_UNRESOLVED"]
    elif direct:
        direct_with_direction = [
            (row, _direction_compatibility(
                relation["sign"], row["subject_perturbation"]["polarity"],
                row["endpoint_response"]["direction"],
            ))
            for row in direct
        ]
        compatible = [row for row, compatibility in direct_with_direction
                      if compatibility == "COMPATIBLE"]
        chosen = compatible[0] if compatible else direct[0]
        selected = compatible or direct
        perturbation_polarity = chosen["subject_perturbation"]["polarity"]
        endpoint_direction = chosen["endpoint_response"]["direction"]
        direction = _direction_compatibility(relation["sign"], perturbation_polarity, endpoint_direction)
        specificity = "EXACT_SUBJECT"
        response_link = "RESCUE_OR_NECESSITY" if chosen["rescue_pattern"] else "DIRECT_RESPONSE"
        reasons = [*_reason_for_perturbation(chosen["subject_perturbation"]), "ENDPOINT_RESPONSE_PRESENT"]
        if chosen["rescue_pattern"]:
            reasons.extend(["RESCUE_EVIDENCE", "NECESSITY_EVIDENCE"])
        if direction == "COMPATIBLE":
            state = "DIRECT_FUNCTIONAL"
            reasons.append("DIRECTION_COMPATIBLE")
        else:
            state = "UNRESOLVED"
            reasons.append("DIRECTION_CONFLICT" if direction == "CONFLICT"
                           else "CURRENT_STUDY_RELATION_UNRESOLVED")
    elif chains:
        selected = _unique_dicts(chains)
        specificity = "EXACT_SUBJECT" if any(row["subject_perturbation"] for row in selected) else "UPSTREAM_OR_DOWNSTREAM_PROXY"
        response_link = "MECHANISTIC_CHAIN"
        perturbations = [row["subject_perturbation"] for row in selected if row["subject_perturbation"]]
        responses = [row["endpoint_response"] for row in selected if row["endpoint_response"]]
        perturbation_polarity = perturbations[0]["polarity"] if perturbations else "UNRESOLVED"
        endpoint_direction = responses[0]["direction"] if responses else "UNRESOLVED"
        direction = _direction_compatibility(relation["sign"], perturbation_polarity, endpoint_direction)
        reasons = ["MECHANISTIC_CHAIN_PRESENT", "ENDPOINT_RESPONSE_PRESENT"]
        if direction == "COMPATIBLE":
            state = "FUNCTIONAL_CHAIN"
            reasons.append("DIRECTION_COMPATIBLE")
        else:
            state = "UNRESOLVED"
        if direction == "CONFLICT":
            reasons.append("DIRECTION_CONFLICT")
        elif direction == "UNRESOLVED":
            reasons.append("CURRENT_STUDY_RELATION_UNRESOLVED")
    elif multi:
        selected = multi
        state = "MULTI_TARGET_AMBIGUOUS"
        specificity = "MULTI_TARGET"
        response_link = "UNRESOLVED"
        reasons = ["MULTI_TARGET_INTERVENTION", "TARGET_CONTRIBUTION_NOT_ISOLATED"]
        if any(row["endpoint_response"] for row in multi):
            reasons.append("ENDPOINT_RESPONSE_PRESENT")
    elif associations or cochanges:
        selected = associations or cochanges
        state = "ASSOCIATION_ONLY"
        specificity = "NO_SUBJECT_PERTURBATION"
        response_link = "CORRELATION" if associations else "CONCURRENT_CHANGE"
        reasons = ["NO_TARGET_PERTURBATION_EVIDENCE"]
        if associations:
            reasons.append("CORRELATION_ONLY")
        if any(row["resistant_sensitive_association"] for row in selected):
            reasons.append("RESISTANT_SENSITIVE_ASSOCIATION_ONLY")
        if cochanges:
            reasons.extend(["COCHANGE_ONLY", "ENDPOINT_RESPONSE_PRESENT"])
    elif backgrounds:
        selected = backgrounds
        state = "BACKGROUND_ONLY"
        specificity = "NO_SUBJECT_PERTURBATION"
        response_link = "NO_LINK"
        reasons = ["BACKGROUND_PROPOSITION_ONLY", "NO_TARGET_PERTURBATION_EVIDENCE"]
    else:
        selected = speculations or [row for row in analyzed if row["subject_matches"] or row["endpoint_matches"]]
        state = "UNRESOLVED"
        specificity = "NO_SUBJECT_PERTURBATION" if any(row["subject_matches"] for row in selected) else "UNRESOLVED"
        response_link = "NO_LINK" if selected else "UNRESOLVED"
        reasons = ["CURRENT_STUDY_RELATION_UNRESOLVED"]
        if not any(row["subject_perturbation"] for row in analyzed):
            reasons.append("NO_TARGET_PERTURBATION_EVIDENCE")
        if not any(row["endpoint_response"] for row in analyzed):
            reasons.append("NO_ENDPOINT_RESPONSE_EVIDENCE")

    selected_roles = {row["evidence_role"] for row in selected}
    relation_roles = {row["evidence_role"] for row in analyzed if row["subject_matches"] and row["endpoint_matches"]}
    evidence_role = _overall_role(selected_roles, relation_roles)
    reasons = tuple(_unique(reasons))
    if not set(reasons) <= REASON_CODES:
        raise ValueError("unknown functional-relation reason code")
    evidence_records = tuple({
        "field": row["field"], "sentence_index": row["sentence_index"], "sentence": row["text"],
        "evidence_role": row["evidence_role"],
        "subject_surfaces": [item["surface"] for item in row["subject_matches"]],
        "endpoint_surfaces": [item["surface"] for item in row["endpoint_matches"]],
    } for row in _unique_dicts(selected))
    return FunctionalRelationEvidenceDecisionV1(
        packet_id=packet_id,
        applicable=applicability.applicable,
        applicability=asdict(applicability),
        target_subject={"raw": target.get("subject"), "normalized_surfaces": subject_surfaces},
        target_relation_family=relation,
        target_endpoint={
            "object": target.get("object"), "measurement_target": target.get("measurement_target"),
            "measurement_property_endpoint": target.get("measurement_property_endpoint"),
            "normalized_surfaces": endpoint_surfaces,
        },
        evidence_state=state,
        evidence_role=evidence_role,
        subject_perturbation_specificity=specificity,
        response_link_state=response_link,
        observed_subject_surfaces=tuple(all_subject),
        observed_endpoint_surfaces=tuple(all_endpoint),
        perturbation_polarity=perturbation_polarity,
        endpoint_response_direction=endpoint_direction,
        direction_compatibility=direction,
        reason_codes=reasons,
        source_evidence_spans_or_sentences=evidence_records,
        resolver_status="resolved" if state != "UNRESOLVED" else "unresolved",
        policy_version=policy["policy_version"],
        registry_version_if_any="existing_formal_relation_registry_v1",
    )


def _unique_dicts(values):
    result = []
    seen = set()
    for value in values:
        key = (value["field"], value["sentence_index"], value["text"])
        if key not in seen:
            seen.add(key)
            result.append(value)
    return result
