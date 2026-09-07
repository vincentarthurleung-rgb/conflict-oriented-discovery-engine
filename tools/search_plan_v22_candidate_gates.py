"""Frozen, offline pre-acquisition gate candidate; deliberately no file or model IO.

Inputs contain only a target contract and preserved title/abstract/publication types.
Identifiers and adjudications are outside this module's interface. This is a bounded
lexical plausibility screen, never scientific proposition compatibility.
"""

from __future__ import annotations

import re
from typing import Any

VERSION = "SearchPlanV22GenericAcquisitionGatesCandidateV1"
INPUT_FIELDS = {"title", "abstract", "publication_types", "publication_types_reliable", "target"}
GATE_ORDER = ("evidence_mode", "context", "endpoint", "relation", "entity", "therapy")
PASS_STATES = {
    "evidence_mode": "PRIMARY_EVIDENCE_PLAUSIBLE",
    "entity": "ENTITY_PLAUSIBLE",
    "context": "CONTEXT_PLAUSIBLE",
    "endpoint": "ENDPOINT_PLAUSIBLE",
    "relation": "RELATION_DIRECTLY_PLAUSIBLE",
    "therapy": "THERAPY_PLAUSIBLE",
}
MISMATCH_STATES = {
    "evidence_mode": "NON_PRIMARY_EVIDENCE_DETECTED",
    "entity": "ENTITY_MISMATCH_ESTABLISHED",
    "context": "CONTEXT_MISMATCH_ESTABLISHED",
    "endpoint": "ENDPOINT_MISMATCH_ESTABLISHED",
    "relation": "RELATION_MISMATCH_ESTABLISHED",
    "therapy": "THERAPY_MISMATCH_ESTABLISHED",
}

NON_PRIMARY_TYPES = {
    "review", "systematic review", "meta-analysis", "narrative review", "overview",
    "editorial", "comment", "published erratum", "news",
}
PRIMARY_TYPES = {
    "clinical trial", "randomized controlled trial", "controlled clinical trial",
    "clinical trial, phase i", "clinical trial, phase ii", "clinical trial, phase iii",
    "clinical trial, phase iv", "observational study", "comparative study",
    "evaluation study", "validation study", "clinical study",
}
REVIEW_SELF_DESCRIPTION = (
    r"\b(?:this|the present|our|the current)\s+(?:\w+\s+){0,3}"
    r"(?:review|overview|meta-analysis)\b|"
    r"\b(?:in|for)\s+this\s+(?:article|paper)\s*,?\s*(?:we\s+)?(?:review|summari[sz]e)\b|"
    r"\bwe\s+(?:systematically\s+)?review(?:ed)?\s+(?:the\s+)?(?:literature|studies|evidence)\b|"
    r"\b(?:we\s+(?:conducted|performed)|this\s+study\s+is)\s+(?:a\s+)?"
    r"(?:systematic\s+review|meta-analysis)\b"
)
PRIMARY_SELF_DESCRIPTION = (
    r"\bwe\s+(?:(?:have|also|first|further|here|therefore)\s+){0,2}"
    r"(?:investigated|examined|tested|measured|demonstrat\w*|show\w*|found|identified|"
    r"observed|established|analy[sz]ed|evaluated|assessed|report\w*)\b|"
    r"\b(?:cells|mice|patients|samples|tumou?rs)\s+were\s+(?:\w+\s+){0,2}"
    r"(?:treated|transfected|collected|randomi[sz]ed|analy[sz]ed|exposed|cultured|isolated)\b|"
    r"\b(?:our|these|the)\s+(?:results|findings|data)\s+(?:\w+\s+){0,2}"
    r"(?:show\w*|demonstrat\w*|reveal\w*|indicat\w*)\b"
)
CANCER_CONTEXT = r"\b(?:cancer|tumou?r|carcinoma|malignan\w*|oncogen\w*|neoplas\w*|leukemi\w*|lymphoma|sarcoma|melanoma|glioma|glioblastoma)\b"
CELL_ENDPOINT = r"\b(?:viability|cell(?:ular)?\s+survival|cell\s+death|apoptos\w*|apoptotic|cytotoxic\w*)\b"
CHANGE_ENDPOINT = r"\b(?:resistan\w*|sensiti\w*|adapt\w*|toleran\w*|persistent\s+survival|precondition\w*)\b"
THERAPY = r"\b(?:chemo(?:therapy|resistan\w*|sensiti\w*)|radio(?:therapy|resistan\w*|sensiti\w*)|immunotherapy|targeted\s+therap\w*|anticancer\s+(?:drug|agent|treatment)\w*|anti-cancer\s+(?:drug|agent|treatment)\w*|drug\s+(?:resistan\w*|sensiti\w*)|treatment\s+(?:response|efficacy))\b"
THERAPY_ENDPOINT = r"\b(?:resistan\w*|sensiti\w*|response|efficacy|regression|IC50|IC\(50\)|viability|cytotoxic\w*|cell\s+death|apoptos\w*|tumou?r\s+growth)\b"
RELATION_VERB = r"\b(?:activat\w*|regulat\w*|modulat\w*|contribut\w*|induc\w*|promot\w*|mediat\w*|inhibit\w*|suppress\w*|enhanc\w*|increas\w*|decreas\w*|reduc\w*|drive[ns]?|drives|driven|affect\w*|control\w*|requir\w*|associat\w*|involv\w*|sensiti\w*|protect\w*)\b"


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(x for x in values if x))


def _surface_regex(surface: str) -> str:
    """Only orthographic normalization, not biological alias invention."""
    tokens = re.split(r"[\s\-\u2010-\u2015_/]+", surface.strip())
    rendered = []
    for token in tokens:
        # Greek names and their glyphs are orthographic renderings, not new entities.
        token = re.escape(token)
        token = re.sub("kappa|κ", "(?:kappa|κ)", token, flags=re.I)
        token = re.sub("alpha|α", "(?:alpha|α)", token, flags=re.I)
        token = re.sub("beta|β", "(?:beta|β)", token, flags=re.I)
        rendered.append(token)
    return r"(?<!\w)" + r"[\s\-\u2010-\u2015_/]*".join(rendered) + r"(?!\w)"


def _surface_hits(source: dict, surfaces: list[str]) -> list[dict]:
    hits = []
    for surface in surfaces:
        hits.extend(_hits(source, _surface_regex(surface), "target_surface:" + surface))
    return _dedup_evidence(hits)


def _modified_phrase_hits(source: dict, surfaces: list[str]) -> list[dict]:
    """A single inserted modifier preserves a multiword entity's noun head.

    This supports plausibility only; modified scope is explicitly deferred and
    cannot earn Tier A through this fallback.
    """
    evidence = []
    for surface in surfaces:
        tokens = surface.split()
        if len(tokens) >= 2:
            pattern = _surface_regex(tokens[0]) + r"\s+[A-Za-z]+\s+" + _surface_regex(" ".join(tokens[1:]))
            evidence.extend(_hits(source, pattern, "frozen_phrase_with_one_inserted_modifier"))
    return evidence


def _entity_expansion_mismatch(source: dict, surfaces: list[str]) -> list[dict]:
    """Detect an explicitly expanded homonym only with a frozen long-form alias.

    Requiring equal expansion token count avoids treating an arbitrary preceding
    noun phrase as an alternative definition of a familiar acronym.
    """
    acronyms = [s for s in surfaces if re.fullmatch(r"[A-Z]{2,8}", s)]
    words = lambda s: re.findall(r"[a-z]+", re.sub(r"\bto\b", "", s.lower()))
    long_forms = [words(s) for s in surfaces if len(words(s)) >= 2 and not any(a.lower() in s.lower() for a in acronyms)]
    mismatches = []
    for acronym in acronyms:
        for form in long_forms:
            count = len(form)
            pattern = r"(?<!\w)([A-Za-z]+(?:[\s\-\u2010-\u2015]+[A-Za-z]+){" + str(count - 1) + r"})\s*\(" + re.escape(acronym) + r"\)"
            for field in ("title", "abstract"):
                for match in re.finditer(pattern, source.get(field) or ""):
                    expansion = words(match.group(1))
                    if expansion and "".join(w[0] for w in expansion).upper() == acronym and expansion not in long_forms:
                        mismatches.append({"field": field, "start": match.start(), "end": match.end(), "quote": match.group(), "signal": "explicit_alternative_acronym_expansion", "authority": "preserved_source_text"})
    return mismatches


def _hits(source: dict, pattern: str, signal: str, fields=("title", "abstract")) -> list[dict]:
    return [
        {"field": field, "start": match.start(), "end": match.end(),
         "quote": match.group(), "signal": signal, "authority": "preserved_source_text"}
        for field in fields for match in re.finditer(pattern, source.get(field) or "", re.I)
    ]


def _dedup_evidence(evidence: list[dict]) -> list[dict]:
    seen = set()
    result = []
    for item in evidence:
        key = (item["field"], item.get("start"), item.get("end"), item.get("index"), item["signal"])
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


def _gate(state: str, reason: str, evidence: list[dict], **extra: Any) -> dict:
    return {"state": state, "reasons": [reason], "evidence": _dedup_evidence(evidence), **extra}


def build_target_contract(plan: dict, frozen_gates: list[dict], variants: list[dict]) -> dict:
    """Derive lexical scope from frozen targets and authorized annotation surfaces.

    The caller supplies case-selected lists. No identity-based branches are used.
    The conditional frozen review rejection does not itself assert a Boolean primary
    requirement: that parameter must be provided with a separate policy authority.
    """
    retrieval = plan["retrieval_target"]
    scientific = plan["scientific_proposition_target"]
    subjects = list(retrieval.get("subject_surfaces") or [retrieval.get("subject_entity", "")])
    endpoints = list(retrieval.get("endpoint_measurement_surfaces") or [retrieval.get("measurement_target", "")])
    for variant in variants:
        for annotation in variant.get("term_authority_annotations", []):
            if not annotation.get("authorizes_proposition_identity"):
                continue
            term = annotation.get("term", "")
            if annotation.get("target_field") == "subject":
                subjects.append(term)
            elif annotation.get("target_field") in {"object", "measurement_target"}:
                endpoints.append(term)
    return {
        "subject_surfaces": _unique(subjects), "endpoint_surfaces": _unique(endpoints),
        "context_surfaces": retrieval.get("context_recall_scope", retrieval.get("context_qualifiers", [])),
        "endpoint_requirement": scientific.get("object_endpoint", scientific.get("measurement_property_endpoint", "")),
        "measurement_requirement": scientific.get("measurement_requirement", ""),
        "relation_requirement": scientific.get("relation_family", retrieval.get("relation_recall_scope", "")),
        "therapy_identity_requirement": scientific.get("therapy_identity_requirement", "not required"),
        "primary_evidence_required": scientific.get("primary_evidence_required", False),
        "primary_requirement_authority": {
            "status": "explicit_policy_parameter_required_if_not_boolean_in_frozen_target",
            "conditional_frozen_gate_text": [reason for gate in frozen_gates for reason in gate.get("known_mismatch_reasons", []) if "primary evidence" in reason],
        },
        "frozen_retrieval_target": retrieval, "frozen_scientific_target": scientific,
        "surface_authority": "frozen targets plus proposition-authorized term annotations; no query mutation",
    }


def _endpoint_family(target: dict) -> str:
    endpoint = " ".join([target.get("endpoint_requirement", ""), target.get("measurement_requirement", "")] + target.get("endpoint_surfaces", [])).lower()
    if re.search(r"adaptation|changed.tolerance|under ferroptotic", endpoint):
        return "changed_cell_tolerance"
    if re.search(r"therapy response|treatment.response|drug resistance|therapy resistance|anticancer agent|treatment-linked sensitivity", endpoint):
        return "therapy_response"
    if re.search(r"cell.survival|cell survival|cell viability|cell.viability|cancer.cell survival|cancer.cell viability", endpoint):
        return "cell_survival"
    if "apopto" in endpoint:
        return "apoptosis"
    if "metasta" in endpoint:
        return "metastasis"
    if re.search(r"expression|abundance", endpoint):
        return "expression"
    if re.search(r"activation|activity", endpoint):
        return "activity"
    return "frozen_surface"


def _evidence_mode(source: dict, target: dict) -> dict:
    types = source.get("publication_types") or []
    metadata = [{"field": "publication_types", "index": i, "quote": value,
                 "signal": "indexed_publication_type", "authority": "preserved_pubmed_publication_type"}
                for i, value in enumerate(types)]
    nonprimary = [e for e in metadata if e["quote"].lower() in NON_PRIMARY_TYPES]
    primary = [e for e in metadata if e["quote"].lower() in PRIMARY_TYPES]
    reliable = source.get("publication_types_reliable", True) and not (nonprimary and primary)
    reviews = _hits(source, REVIEW_SELF_DESCRIPTION, "abstract_self_describes_nonprimary_work", ("abstract",))
    experiments = _hits(source, PRIMARY_SELF_DESCRIPTION, "abstract_self_reports_original_study", ("abstract",))
    if reliable and nonprimary:
        return _gate("NON_PRIMARY_EVIDENCE_DETECTED", "Reliable indexed publication type establishes non-primary evidence.", nonprimary, authority="publication_type_metadata", fatal=target.get("primary_evidence_required", False))
    if reviews:
        return _gate("NON_PRIMARY_EVIDENCE_DETECTED", "Abstract explicitly describes this work as a review or evidence synthesis.", reviews, authority="deterministic_abstract_self_description", fatal=target.get("primary_evidence_required", False))
    if (reliable and primary) or experiments:
        return _gate("PRIMARY_EVIDENCE_PLAUSIBLE", "Indexed primary study type or abstract self-report supports an original investigation.", primary if reliable and primary else experiments, authority="publication_type_metadata" if reliable and primary else "deterministic_abstract_self_description", fatal=False)
    return _gate("EVIDENCE_MODE_UNRESOLVED", "Journal Article alone, missing metadata, or absent self-description does not establish primary or non-primary evidence.", metadata, authority="metadata_incomplete_or_non_discriminating", fatal=False)


def _context(source: dict, target: dict, family: str) -> dict:
    contexts = target.get("context_surfaces", [])
    if not contexts:
        return _gate("CONTEXT_PLAUSIBLE", "Target specifies no mandatory context constraint.", [])
    cancer_target = any(re.search(CANCER_CONTEXT, x, re.I) for x in contexts)
    plausible = _hits(source, CANCER_CONTEXT, "cancer_context") if cancer_target else _surface_hits(source, contexts)
    if cancer_target and family in {"cell_survival", "changed_cell_tolerance"}:
        foreign_owner = _hits(source, r"\b(?:ferroptos\w*|survival|viability|cell\s+death)\s+(?:of|in)\s+(?:the\s+)?(?:neutrophils?|neurons?|neuronal\s+cells?|cardiomyocytes?|normal\s+cells?)\b", "endpoint_explicitly_owned_by_other_biological_unit")
        target_owner = _hits(source, r"\b(?:cancer|tumou?r|carcinoma|malignant)\s+cells?\b", "target_cell_unit")
        if foreign_owner and not target_owner:
            return _gate("CONTEXT_MISMATCH_ESTABLISHED", "Source explicitly assigns the cellular endpoint to a different biological unit; no competing target-unit experiment is stated.", foreign_owner)
    if plausible:
        return _gate("CONTEXT_PLAUSIBLE", "Source positively names the required context family.", plausible)
    foreign_context = _hits(source, r"\b(?:spinal\s+cord\s+injury|traumatic\s+brain\s+injury|myocardial\s+infarction|cerebral\s+ischemia|neuronal\s+(?:injury|death)|neurodegenerati\w*|bacterial\s+(?:infection|resistance))\b", "explicit_other_study_context")
    studied = _hits(source, PRIMARY_SELF_DESCRIPTION, "original_study_scope", ("abstract",))
    if cancer_target and foreign_context and studied:
        return _gate("CONTEXT_MISMATCH_ESTABLISHED", "Source establishes an original investigation in a materially different biological context; missing cancer text alone would not reject.", foreign_context + studied)
    return _gate("CONTEXT_UNRESOLVED", "Required context is not resolved in preserved text; absence does not establish mismatch.", [])


def _endpoint(source: dict, target: dict, family: str) -> dict:
    exact = _surface_hits(source, target.get("endpoint_surfaces", []))
    if family == "changed_cell_tolerance":
        positive = _hits(source, CHANGE_ENDPOINT, "changed_tolerance_endpoint")
        # Generic resistance/tolerance needs a cellular stress source, represented by
        # the separately required subject anchor; no contrast is inferred here.
        immune = _hits(source, r"\b(?:immune|immunological|immunologic|T.cell)\s+tolerance\b", "immune_tolerance_endpoint")
        if immune and not positive_except(positive, immune):
            return _gate("ENDPOINT_MISMATCH_ESTABLISHED", "Explicit immune-tolerance endpoint is a different endpoint family from changed cancer-cell tolerance.", immune)
        baseline = _hits(source, r"\b(?:baseline|basal|unstimulated|unchallenged)\s+(?:cell\s+)?(?:viability|survival)\b", "explicit_baseline_only_endpoint")
        if baseline and not positive:
            return _gate("ENDPOINT_MISMATCH_ESTABLISHED", "Source explicitly characterizes the measured endpoint as baseline survival/viability, distinct from changed tolerance.", baseline)
    elif family == "cell_survival":
        positive = _hits(source, CELL_ENDPOINT, "cell_survival_endpoint")
    elif family == "therapy_response":
        positive = _hits(source, THERAPY_ENDPOINT, "therapy_response_endpoint")
    elif family == "apoptosis":
        positive = _hits(source, r"\bapopto\w*\b", "apoptotic_endpoint")
    elif family == "metastasis":
        positive = _hits(source, r"\bmetasta\w*\b", "metastatic_endpoint")
    elif family == "expression":
        bases = [re.sub(r"\s+(?:expression|abundance)$", "", surface, flags=re.I) for surface in target.get("endpoint_surfaces", [])]
        measured = _hits(source, r"\b(?:express\w*|abundance|protein\s+levels?|mRNA\s+levels?)\b", "expression_measurement_language")
        base_hits = _surface_hits(source, bases)
        positive = exact or (base_hits if measured else [])
    elif family == "activity":
        positive = exact
    else:
        positive = exact
    if positive:
        return _gate("ENDPOINT_PLAUSIBLE", "Preserved source text names the target endpoint family; exact assay and contrast may still require fulltext.", positive, endpoint_family=family)
    patient = _hits(source, r"\b(?:patient\s+(?:overall\s+)?survival|overall\s+survival|progression.free\s+survival|disease.free\s+survival|prognostic\s+(?:marker|biomarker|model|signature)|patient\s+prognosis)\b", "explicit_patient_endpoint")
    if family in {"cell_survival", "changed_cell_tolerance"} and patient:
        return _gate("ENDPOINT_MISMATCH_ESTABLISHED", "Source explicitly supplies a patient prognosis/survival endpoint for a cellular survival/tolerance target.", patient, endpoint_family=family)
    return _gate("ENDPOINT_UNRESOLVED", "No positive target endpoint or material endpoint mismatch is established; missing detail does not reject.", exact, endpoint_family=family)


def positive_except(positive: list[dict], scoped: list[dict]) -> list[dict]:
    return [hit for hit in positive if not any(hit["field"] == other["field"] and other["start"] <= hit["start"] and hit["end"] <= other["end"] for other in scoped)]


def _relation(source: dict, entity: dict, endpoint: dict) -> dict:
    entities = entity["evidence"]
    endpoints = endpoint["evidence"] if endpoint["state"] == "ENDPOINT_PLAUSIBLE" else []
    explicit = []
    alternative_ownership = []
    for field in ("title", "abstract"):
        text = source.get(field) or ""
        for sentence in re.finditer(r"[^.!?\n]+(?:[.!?]|$)", text):
            es = [e for e in entities if e["field"] == field and sentence.start() <= e["start"] < sentence.end()]
            ps = [e for e in endpoints if e["field"] == field and sentence.start() <= e["start"] < sentence.end()]
            for e in es:
                for p in ps:
                    if e["start"] == p["start"] and e["end"] == p["end"]:
                        continue
                    left, right = sorted((e, p), key=lambda x: x["start"])
                    between = text[left["end"]:right["start"]]
                    if left is p and re.search(r"\b(?:controlled|mediated|regulated|driven)\s+(?:solely|exclusively)\s+by\s+[^.!?;]+[,;]?\s+(?:independently\s+of|rather\s+than|not\s+by)\s*$", between, re.I):
                        alternative_ownership.append({"field": field, "start": sentence.start(), "end": sentence.end(), "quote": sentence.group(), "signal": "explicit_exclusive_alternative_endpoint_ownership", "authority": "preserved_source_text"})
                    # A predicate between anchors or a grammatical endpoint-via-
                    # subject link is stronger than pathway/component co-occurrence.
                    linked = re.search(RELATION_VERB, between, re.I)
                    via = re.search(r"\b(?:via|through|dependent\s+on|mediated\s+by)\b", between, re.I)
                    if linked or (via and left is p):
                        explicit.append({"field": field, "start": sentence.start(), "end": sentence.end(), "quote": sentence.group(), "signal": "same_sentence_explicit_relation_link", "authority": "preserved_source_text"})
    if alternative_ownership:
        return _gate("RELATION_MISMATCH_ESTABLISHED", "Source explicitly assigns the endpoint exclusively to another mechanism and distinguishes the target subject. A null/negative effect alone does not establish this mismatch.", alternative_ownership)
    if explicit:
        return _gate("RELATION_DIRECTLY_PLAUSIBLE", "A source sentence grammatically links the target subject and endpoint; direction, causal truth and proposition compatibility remain unadjudicated.", explicit)
    return _gate("RELATION_REQUIRES_FULLTEXT", "The abstract does not directly link subject and endpoint; co-occurrence alone cannot pass Tier A. No alternative mechanism is inferred from absence.", entities + endpoints)


def evaluate(scientific_input: dict) -> dict:
    """Pure deterministic evaluation; any unexpected top-level field is rejected.

    Returns state=None on information-insufficient inputs outside the evaluable
    three-state acquisition domain. Such an abstention is NEVER a known mismatch.
    All retained Tier B rows require evidenced subject and endpoint plus resolvable
    named scientific fields. No fallback transforms arbitrary topic uncertainty.
    """
    if set(scientific_input) - INPUT_FIELDS:
        raise ValueError("Only allowlisted scientific input fields are accepted")
    target = scientific_input["target"]
    source = scientific_input
    family = _endpoint_family(target)
    entities = _surface_hits(source, target.get("subject_surfaces", []))
    functional_state_unresolved = False
    modified_subject_scope_unresolved = False
    if not entities:
        base_subjects = [re.sub(r"\s+(?:signaling|signalling|activity|perturbation|expression)$", "", surface, flags=re.I) for surface in target.get("subject_surfaces", [])]
        entities = _surface_hits(source, base_subjects)
        functional_state_unresolved = bool(entities)
    if not entities:
        entities = _modified_phrase_hits(source, target.get("subject_surfaces", []))
        modified_subject_scope_unresolved = bool(entities)
    entity_reason = "Missing subject anchor does not establish a wrong entity."
    if entities:
        entity_reason = "Frozen subject surface is present."
    if functional_state_unresolved:
        entity_reason = "Base entity from the frozen functional subject is present; its signaling/activity/perturbation state remains unresolved."
    if modified_subject_scope_unresolved:
        entity_reason = "Frozen subject noun phrase appears with an inserted modifier; exact target scope remains unresolved."
    entity = _gate("ENTITY_PLAUSIBLE" if entities else "ENTITY_UNRESOLVED", entity_reason, entities)
    alternative_expansion = _entity_expansion_mismatch(source, target.get("subject_surfaces", []))
    if alternative_expansion:
        long_forms = [s for s in target.get("subject_surfaces", []) if re.search(r"\s|[-\u2010-\u2015]", s)]
        if not _surface_hits(source, long_forms):
            entity = _gate("ENTITY_MISMATCH_ESTABLISHED", "Source explicitly expands the target acronym as a different long-form entity; lexical absence alone would not establish mismatch.", alternative_expansion)
    evidence = _evidence_mode(source, target)
    context = _context(source, target, family)
    endpoint = _endpoint(source, target, family)
    relation = _relation(source, entity, endpoint)
    therapy_requirement = target.get("therapy_identity_requirement", "not required")
    therapy_required = not re.search(r"not (?:required|proposition-critical)", therapy_requirement, re.I) and bool(therapy_requirement)
    therapy_hits = _hits(source, THERAPY, "meaningful_therapy_class") if therapy_required else []
    therapy = _gate("THERAPY_PLAUSIBLE" if not therapy_required or therapy_hits else "THERAPY_UNRESOLVED", "No target-critical therapy identity requirement." if not therapy_required else "A meaningful treatment class is stated." if therapy_hits else "Exact agent/class requires fulltext; no wrong therapy is inferred.", therapy_hits, applicable=therapy_required)
    gates = {"evidence_mode": evidence, "entity": entity, "context": context, "endpoint": endpoint, "relation": relation, "therapy": therapy}
    rejects = [name for name, gate in gates.items() if gate["state"] == MISMATCH_STATES[name] and (name != "evidence_mode" or gate["fatal"])]
    known = [name for name, gate in gates.items() if gate["state"] == PASS_STATES[name]]
    if not target.get("primary_evidence_required", False) and evidence["state"] == "NON_PRIMARY_EVIDENCE_DETECTED":
        known.append("evidence_mode_permitted_by_target")
    unresolved = [name for name in gates if name not in known and name not in rejects and not (name == "evidence_mode" and "evidence_mode_permitted_by_target" in known)]
    if functional_state_unresolved:
        unresolved.append("subject_functional_state")
    if modified_subject_scope_unresolved:
        unresolved.append("modified_subject_scope")
    resolutions = {
        "evidence_mode": "Methods and results can establish whether this paper reports original measurements.",
        "context": "Methods and model descriptions can resolve the biological unit and study context for the evidenced subject/endpoint.",
        "relation": "Experimental design and results can show whether the evidenced subject and endpoint are directly connected or only co-mentioned.",
        "therapy": "Methods and treatment-arm descriptions can name the agent or scientifically meaningful therapy class for the evidenced response.",
        "subject_functional_state": "Methods and perturbation/activity measurements can resolve whether the evidenced base entity represents the target signaling or functional state.",
        "modified_subject_scope": "Model and experimental context descriptions can resolve whether the source's modified noun phrase instantiates the frozen subject scope.",
    }
    reasons = {name: resolutions[name] for name in unresolved if name in resolutions}
    fulltext_resolvable = all(name in resolutions for name in unresolved)
    if rejects:
        state, eligible, rejection_kind = "REJECT", False, "REJECT_KNOWN_MISMATCH"
    elif not unresolved:
        state, eligible, rejection_kind = "TIER_A", True, None
    elif entities and endpoint["state"] == "ENDPOINT_PLAUSIBLE" and fulltext_resolvable:
        state, eligible, rejection_kind = "TIER_B", True, None
    else:
        state, eligible, rejection_kind = None, False, None
    return {
        "candidate_version": VERSION, "state": state, "acquisition_eligible": eligible,
        "rejection_kind": rejection_kind, "reject_gate_names": rejects, "gates": gates,
        "known_plausible_fields": known,
        "unresolved_fields_requiring_fulltext": unresolved if state == "TIER_B" else [],
        "why_fulltext_can_resolve": reasons if state == "TIER_B" else {},
        "contract_defect": "INSUFFICIENT_PLAUSIBILITY_FOR_THREE_STATE" if state is None else None,
        "proposition_compatibility_inferred": False,
    }


def contracts() -> dict[str, dict]:
    """Artifact-ready contracts documenting limitations without evaluation labels."""
    common = {"candidate_version": VERSION, "activation_state": "CANDIDATE_NOT_PRODUCTION_ACTIVATED", "heldout_validation_state": "NOT_HELD_OUT_VALIDATED", "source_scope": "preserved title, abstract, publication types and frozen target contract only", "network_calls": 0, "provider_calls": 0, "llm_calls": 0}
    def contract(**kwargs: Any) -> dict:
        return dict(common, **kwargs)
    return {
        "evidence_mode_gate_candidate.json": contract(name="PublicationEvidenceModeGateV1Candidate", states=["PRIMARY_EVIDENCE_PLAUSIBLE", "NON_PRIMARY_EVIDENCE_DETECTED", "EVIDENCE_MODE_UNRESOLVED"], metadata_priority="Reliable indexed discriminating type; Journal Article alone does not establish primary evidence. Conflicting primary/nonprimary tags trigger abstract fallback.", fallback="Deterministic abstract self-description only, never title inference or model classification.", non_primary_types=sorted(NON_PRIMARY_TYPES), primary_types=sorted(PRIMARY_TYPES), abstract_nonprimary_pattern=REVIEW_SELF_DESCRIPTION, primary_requirement="Explicit input target policy plus recorded authority; conditional frozen review rejection alone is not a Boolean assertion.", reject_only_when_primary_required=True),
        "context_plausibility_gate_candidate.json": contract(name="RetrievalContextPlausibilityGateV1", states=["CONTEXT_PLAUSIBLE", "CONTEXT_MISMATCH_ESTABLISHED", "CONTEXT_UNRESOLVED"], mismatch="Positive other study context or positively assigned other cellular endpoint owner. An absent context alone remains unresolved.", scope="Generic cancer context family and biological-unit contrasts selected by target type, without target identity branches.", missing_context_is_mismatch=False),
        "endpoint_plausibility_gate_candidate.json": contract(name="RetrievalEndpointPlausibilityGateV1", states=["ENDPOINT_PLAUSIBLE", "ENDPOINT_MISMATCH_ESTABLISHED", "ENDPOINT_UNRESOLVED"], families=["changed_cell_tolerance", "cell_survival", "therapy_response", "apoptosis", "metastasis", "expression", "activity", "frozen_surface"], mismatch="Positive patient prognosis versus cellular endpoint, immune tolerance versus changed cellular tolerance, or explicitly baseline viability versus changed tolerance.", missing_endpoint_is_mismatch=False),
        "relation_plausibility_gate_candidate.json": contract(name="RetrievalRelationPlausibilityGateV1", states=["RELATION_DIRECTLY_PLAUSIBLE", "RELATION_REQUIRES_FULLTEXT", "RELATION_MISMATCH_ESTABLISHED"], direct="Source sentence links subject and endpoint with an intervening relation predicate or endpoint-via-subject construction.", missing_link="Requires fulltext; co-occurrence cannot pass Tier A.", mismatch="Narrow explicit endpoint controlled/mediated/regulated/driven solely/exclusively by another mechanism, independently of/rather than/not by target subject. Null or negative effects alone never trigger it.", direction_or_causality_inferred=False, scientific_proposition_compatibility_performed=False),
        "tier_a_v22_candidate_contract.json": contract(name="TierAV22Candidate", required_gates="All applicable gates plausible with explicit source support; no fatal mismatch; evidence mode may be nonprimary only if target permits it.", proposition_compatibility=False),
        "tier_b_v22_candidate_contract.json": contract(name="TierBV22Candidate", required=["entity plausible", "endpoint family plausible", "no known fatal mismatch", "at least one named unresolved scientific field", "every unresolved field realistically resolvable from methods/results"], required_ledgers=["known_plausible_fields", "unresolved_fields_requiring_fulltext", "why_fulltext_can_resolve"], topic_only_allowed=False),
        "reject_v22_candidate_contract.json": contract(name="RejectV22Candidate", state="REJECT_KNOWN_MISMATCH", allowed_gates=list(GATE_ORDER), missing_information_is_rejection=False, insufficient_domain="Inputs lacking sufficient positive entity/endpoint evidence return an explicit noneligible abstention (state null); never silently relabel missing information as mismatch. A replay requiring exactly three states must flag any such row as invalid."),
        "search_plan_v22_candidate_contract.json": contract(name="SearchPlanV22GenericAcquisitionGateCandidate", input_fields=sorted(INPUT_FIELDS), no_identifier_based_decisions=True, generic_entity_gate="Frozen surfaces/authorized aliases; generic functional suffix and one-inserted-modifier fallbacks require explicit Tier B unresolved field. Explicit alternative acronym expansion may establish mismatch; missing anchor alone cannot.", generic_therapy_gate="Recognized treatment class or unresolved exact identity; no unspecified-drug blacklist and no missing-therapy mismatch.", queries_or_budgets_modified=False, calibration_only=True, policy="Freeze code and input contracts before overlay joins; never adapt after evaluation feedback.", relation_candidate_limit="Conservative syntactic plausibility and narrow exclusive-alternative-ownership pattern only; heldout validation required.", offsets="Every textual evidence item has exact original field, start, end, quote; indexed metadata has exact list index and quote.")
    }
