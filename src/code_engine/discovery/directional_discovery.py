"""Deterministic exploratory signals from source-bound native extractions.

Exact local labels are preliminary grouping keys, never canonical identities or
proposition equivalence. Work assessments and formal eligibility are not inputs.
"""
from collections import defaultdict
from itertools import combinations
from pathlib import Path
import hashlib
import json

from code_engine.discovery.ai_review_shadow import content_hash, file_hash
from code_engine.extraction.direction_semantics import extracted_sign, scoped_statistical_evidence
from code_engine.graph.probabilistic_conflict import binary_direction_summary

VERSION = "deterministic_initial_direction_discovery_v2"
LEVELS = ("RAW_POLARITY_COLLISION", "PROVISIONAL_DIRECTIONAL_DISCORDANCE",
          "QUALIFIED_CONTRADICTION_CANDIDATE", "FORMALLY_AUTHORIZED_CONFLICT")
AUTH = {"scientific_authorization": False, "human_gold": False,
        "strict_core_eligible": False, "formal_core_graph_eligible": False,
        "formal_conflict": False, "qualified_for_l4": False,
        "authority_scope": "exploratory_direction_only"}


def _label(value):
    return " ".join(str(value or "").split()).casefold()


def _verify_spans(spans):
    """Check source-local span integrity; hydration retains original coordinates.

    The Pilot has already verified full source/window identity on hydration or
    native replay. Do not reinterpret XML offsets as ArticleJSON offsets here.
    """
    refs = {}
    for s in spans:
        text = s.get("text", "")
        if (not s.get("evidence_span_id") or not s.get("source_document_id") or
                not s.get("block_id") or not text or
                hashlib.sha256(text.encode()).hexdigest() != s.get("text_hash") or
                type(s.get("char_start")) is not int or type(s.get("char_end")) is not int or
                not 0 <= s["char_start"] < s["char_end"] or
                s["char_end"] - s["char_start"] != len(text)):
            raise ValueError("initial_direction_span_integrity_invalid")
        key = s["evidence_span_id"]
        if key in refs and refs[key] != s:
            raise ValueError("initial_direction_span_identity_ambiguous")
        refs[key] = s
    return refs


def native_direction_record(formal, *, publication, core_sha256=None, source_binding=None):
    """Derive a sidecar; preserve every raw native field and source reference."""
    spans = _verify_spans(formal["provenance"]["evidence_spans"])
    observation = formal["observation"]; measurement = formal["measurement"]
    result_refs = observation["evidence_span_ids"]
    measurement_refs = measurement["evidence_span_ids"]
    if not result_refs or not measurement_refs or not set(result_refs + measurement_refs) <= spans.keys():
        raise ValueError("initial_direction_result_or_measurement_evidence_missing")
    experiment = formal["experiment"]; relation = formal["candidate_relation"]
    result_evidence = [spans[r] for r in result_refs]
    document_id = formal['provenance'].get('source_document_id')
    if document_id and any(s['source_document_id'] != document_id for s in spans.values()):
        raise ValueError('initial_direction_evidence_source_identity_mismatch')
    statistics = scoped_statistical_evidence(formal, spans)
    null = statistics['status'] == 'NONSIGNIFICANT'
    raw = relation.get("lexical_direction")
    source_sign = extracted_sign(raw)
    # Explicit direction is an estimate/observation, independent of significance.
    sign = None if observation.get('negation') else source_sign
    screen_reasons = (['SOURCE_DIRECTION_UNRESOLVED'] if sign is None else []) + (
        ['SCOPED_NONSIGNIFICANCE_NOT_CONFLICT_SCREEN_AUTHORITY'] if null else [])
    interventions = formal.get("interventions", [])
    design_text = " ".join(str(experiment.get(k) or "") for k in
        ("design_type", "design_type_raw", "experimental_design_raw")).casefold()
    intervention_text = " ".join(str(i.get("intervention_type_raw") or "") for i in interventions).casefold()
    observational = any(t in design_text + " " + intervention_text for t in
        ("observational", "retrospective", "biomarker stratification", "cohort study"))
    kind = "association" if observational else "observed_contrast" if experiment.get("design_type") in (
        "in_vivo", "in_vitro", "clinical_interventional") else "unknown"
    primary = [i for i in interventions if i.get("role") == "primary"]
    factor = [{k: i.get(k) for k in ("target_mention", "agent_mention", "intervention_type_raw", "dose_raw", "condition_raw")}
              for i in primary]
    tested = experiment.get("comparison_arm_raw"); reference = experiment.get("control_arm_raw")
    evidence_text = " ".join(s["text"] for s in spans.values())
    arms_attested = bool(tested and reference and _label(tested) != _label(reference) and
                         _label(tested) in _label(evidence_text) and _label(reference) in _label(evidence_text))
    row = {**AUTH, "schema_version": VERSION + ":observation", "observation_id": formal["observation_id"],
        "native_revision_sha256": content_hash(formal), "core_sha256": core_sha256,
        "publication": publication, "source_binding": source_binding,
        "extraction_warnings": formal.get("extraction_warnings", []),
        "raw_extracted_sign": raw, "raw_direction_wording": relation.get("lexical_direction_raw"),
        "source_reported_direction": 'positive' if source_sign == 1 else 'negative' if source_sign == -1 else 'unknown',
        "source_reported_sign": source_sign, "effective_direction": sign,
        "effective_direction_derivation": {'policy': VERSION, 'input_native_revision_sha256': content_hash(formal),
            'rule': 'preserve_explicit_binary_direction; negation/unknown do not create a direction',
            'statistical_significance_consumed_to_set_direction': False},
        "statistical_significance_status": statistics['status'], "applicable_result_evidence_scope": statistics,
        "reported_nonsignificance": None if statistics['status'] == 'UNKNOWN' else null,
        "conflict_screen_eligibility": {'eligible':not screen_reasons,'reasons':screen_reasons,
            'unknown_significance_is_not_assumed_significant':True},
        "uncertainty_reasons":statistics['uncertainty_reasons'],
        "reported_absence_wording": [s['text'] for s in result_evidence if
            any(t in s['text'].casefold() for t in ('no association','no significant','did not find a significant','did not increase'))],
        "zero_effect_asserted": False, "causal_sign": None, "relationship_kind": kind,
        "relation_raw": relation.get("relation_raw"), "factor": factor,
        "source_relation_subject": relation.get("subject_mention"),
        "all_interventions": interventions, "measurement": measurement, "observed_result": observation,
        "experiment_context": experiment, "tested_arm": tested, "reference_arm": reference,
        "orientation": "source_tested_vs_reference" if arms_attested else "unverified",
        "source_evidence": list(spans.values()), "result_evidence_refs": result_refs,
        "measurement_evidence_refs": measurement_refs,
        "identity_scope": "exact_extracted_labels_only; canonical equivalence unresolved",
        "measurement_scope": "existing extracted endpoint/type only; no ontology expansion",
        "missing": [k for k,v in (("tested_arm",tested),("reference_arm",reference),
            ("measurement_dimension",measurement.get("measurement_dimension") not in (None,"unknown")),
            ("endpoint",measurement.get("endpoint_raw")),("factor",factor)) if not v]}
    row["record_identity"] = content_hash(row)
    return row


def _endpoint_key(row):
    m = row['measurement']
    return (row['relationship_kind'], _label(m.get('measured_entity_mention')),
            _label(m.get('endpoint_raw')), _label(m.get('measurement_dimension_raw') or m.get('measurement_dimension')))


def _relation_key(row):
    # Exact extracted intervention subject/operator; no alias or ontology inference.
    factor = tuple(tuple(_label(f.get(k)) for k in ('target_mention','agent_mention',
                    'intervention_type_raw','dose_raw','condition_raw')) for f in row['factor'])
    return (*_endpoint_key(row), factor)


def _screen_sign(row):
    return row['effective_direction'] if row['conflict_screen_eligibility']['eligible'] else None


def _publication(row):
    p = row["publication"]
    # Both identifiers are retained; unknown publication independence never
    # becomes a positive decision from source-file or endpoint counts.
    return p.get("pmcid"), str(p.get("pmid") or "")


def discover_directions(rows):
    groups = defaultdict(list); endpoint_groups = defaultdict(list)
    excluded = []; retained = []; seen = set(); duplicates = []
    for row in rows:
        # Exact scientific evidence/endpoint dedup, independent of observation IDs.
        evidence=row.get('source_verification',{}).get('verified_packet_evidence',row['source_evidence'])
        provenance = sorted({(s.get("source_document_id") or _publication(row)[0],
                              str(s.get('source_json_pointer') or s.get('section_index',s.get('block_id'))),
                              s["char_start"],s["char_end"],s["text_hash"])
                             for s in evidence if s["evidence_span_id"] in row["result_evidence_refs"]})
        measurement={k:v for k,v in row['measurement'].items() if k!='evidence_span_ids'}
        identity = content_hash([_publication(row),provenance,row["factor"],measurement,
                                 row["effective_direction"],row["tested_arm"],row["reference_arm"]])
        if identity in seen:
            duplicates.append({"record_identity":row["record_identity"],"reason":"duplicate_source_endpoint_direction"})
            continue
        seen.add(identity); retained.append(row)
        key = _relation_key(row)
        if not all(key) or key[0] == "unknown" or not any((f[0] or f[1]) and f[2] for f in key[-1]):
            excluded.append({"record_identity":row["record_identity"],"reason":"typed_relation_or_endpoint_unresolved"})
        else:
            groups[key].append(row)
            endpoint_groups[_endpoint_key(row)].append(row)
    pairs = []; inventories = []
    for key, members in sorted(groups.items()):
        binary = binary_direction_summary(_screen_sign(r) for r in members)
        from code_engine.graph.context_attribution import context_entropy_reduction
        context_diagnostics=context_entropy_reduction([
            {'relation_sign':_screen_sign(r),'context':{k:v for k,v in r['experiment_context'].items() if v}}
            for r in members],binary['entropy'] or 0.0)
        inventories.append({"preliminary_scope":key,"binary_signal":binary,
            "context_entropy_diagnostics":context_diagnostics,"context_diagnostics_are_explanations":False,
            "record_identities":[r["record_identity"] for r in members],
            "publication_count":len({_publication(r) for r in members if all(_publication(r))}),
            "contexts":[{"record_identity":r["record_identity"],"context":r["experiment_context"],
                         "tested_arm":r["tested_arm"],"reference_arm":r["reference_arm"]} for r in members]})
        for a,b in combinations(members,2):
            pa,pb = _publication(a),_publication(b)
            independent = bool(all(pa) and all(pb) and pa[0] != pb[0] and pa[1] != pb[1])
            sa,sb = _screen_sign(a),_screen_sign(b)
            raw_opposed = sa in (-1,1) and sb in (-1,1) and sa != sb
            arms_a = (_label(a["tested_arm"]),_label(a["reference_arm"]))
            arms_b = (_label(b["tested_arm"]),_label(b["reference_arm"]))
            orientation = "unverified"
            if a["orientation"] == b["orientation"] == "source_tested_vs_reference":
                if arms_a == arms_b: orientation = "same_tested_reference"
                elif arms_a == arms_b[::-1]: orientation = "reversed_tested_reference"
            oriented_b = -sb if orientation == "reversed_tested_reference" and sb in (-1,1) else sb
            factor_match = bool(a["factor"] and b["factor"] and a["factor"] == b["factor"])
            # No assay aliases, ontology creation, fuzzy identity or Work verdicts.
            assay_match = bool(a["measurement"].get("assay_or_readout_raw") and
                               _label(a["measurement"].get("assay_or_readout_raw")) == _label(b["measurement"].get("assay_or_readout_raw")))
            provisional = bool(independent and orientation != "unverified" and factor_match and assay_match
                               and sa in (-1,1) and oriented_b in (-1,1) and sa != oriented_b)
            levels = ([LEVELS[0]] if raw_opposed else []) + ([LEVELS[1]] if provisional else [])
            pairs.append({**AUTH,"pair_id":content_hash([a["record_identity"],b["record_identity"]]),
                "record_identities":[a["record_identity"],b["record_identity"]],"preliminary_scope":key,
                "levels":levels,"raw_extracted_signs":[a['raw_extracted_sign'],b['raw_extracted_sign']],
                "source_reported_directions":[a['source_reported_direction'],b['source_reported_direction']],
                "source_reported_signs":[a['source_reported_sign'],b['source_reported_sign']],
                "effective_signs":[a['effective_direction'],b['effective_direction']],
                "screening_signs":[sa,sb],"oriented_signs":[sa,oriented_b],
                "sign_field_semantics":{'oriented_signs':'orientation-adjusted eligible screening signs',
                    'raw_signs':'REMOVED in v2; v1 incorrectly stored effective signs'},
                "orientation":orientation,"factor_scope_exact_match":factor_match,"assay_scope_exact_match":assay_match,
                "independent_publications":independent,"same_publication":pa[0] == pb[0] or pa[1] == pb[1],
                "proposition_equivalence":"NOT_ESTABLISHED", "comparability":"UNQUALIFIED",
                "context_differences":{k:[a["experiment_context"].get(k),b["experiment_context"].get(k)]
                    for k in sorted(a["experiment_context"].keys() | b["experiment_context"].keys())
                    if a["experiment_context"].get(k) != b["experiment_context"].get(k)},
                "intervention_contexts":[a['all_interventions'],b['all_interventions']],
                "measurement_contexts":[a['measurement'],b['measurement']],
                "reason":"provisional_direction_signal_only" if provisional else
                         "raw_opposition_alignment_unverified_or_orientation_resolved" if raw_opposed else
                         "insufficient_direction" if sa is None or sb is None else "no_polarity_collision"})
    partitions=[]
    for members in endpoint_groups.values():
        for a,b in combinations(members,2):
            if _relation_key(a)==_relation_key(b):continue
            if {a['source_reported_sign'],b['source_reported_sign']}!={-1,1}:continue
            partitions.append({**AUTH,'record_identities':[a['record_identity'],b['record_identity']],
                'source_reported_directions':[a['source_reported_direction'],b['source_reported_direction']],
                'raw_extracted_signs':[a['raw_extracted_sign'],b['raw_extracted_sign']],
                'effective_signs':[a['effective_direction'],b['effective_direction']],
                'relation_keys_align':False,'raw_collision_qualifies':False,'provisional_discordance_qualifies':False,
                'relation_keys':[_relation_key(a),_relation_key(b)],
                'reason':'DISTINCT_INTERVENTION_TO_ENDPOINT_RELATIONS; shared endpoint is not proposition equivalence'})
    counts = {level:sum(level in p["levels"] for p in pairs) if level in LEVELS[:2] else 0 for level in LEVELS}
    retained_by_id = {r["record_identity"]:r for r in retained}
    publication_pairs = {tuple(sorted((_publication(retained_by_id[a]),_publication(retained_by_id[b]))))
                         for p in pairs if p["independent_publications"] for a,b in [p["record_identities"]]}
    from code_engine.discovery.dose_stratified_diagnostic import diagnose_dose_stratified_reversal
    return {**AUTH,"schema_version":VERSION,"counts":counts,"observations":retained,
        "dose_stratified_direction_reversal":diagnose_dose_stratified_reversal(retained),
        "groups":inventories,"pairs":pairs,"duplicates":duplicates,"excluded":excluded,
        "relation_partition_diagnostics":partitions,
        "source_opposing_direction_pairs":len(partitions)+sum(set(p['source_reported_signs'])=={-1,1} for p in pairs),
        "deprecated_removed_fields":{'pair.raw_signs':'Use raw_extracted_signs, source_reported_signs and effective_signs separately; v1 is audit-only'},
        "input_observations":len(rows),"retained_observations":len(retained),
        "independent_publication_pairs":len(publication_pairs),
        "Work_assessments_consumed":False,"formal_L4_invoked":False,
        "authority_count_scope":"C/D zero means not invoked by this exploratory lane, not a repository-wide count"}


def run_initial_discovery(records, *, dependencies):
    """Actual Pilot adapter: all retained native records, before admission gates."""
    rows = []; rejected = []; bindings = []
    for r in records:
        try:
            core = Path(r["core"]); envelope = json.loads(core.read_text())
            formal = envelope["ExperimentalObservationV3"]
            # Reuse existing coordinate/representation verification, without
            # reading any AI review or source-comparison judgment.
            if r.get('native_representation_binding'):
                from code_engine.orchestration.pilot_native_representation import load_native_bound_packet_v1
                bound=load_native_bound_packet_v1(Path(r['packet']),Path(r['prompt']),core,r['native_representation_binding'])
            else:
                from code_engine.discovery.ai_review_shadow import load_bound_packet
                bound=load_bound_packet(Path(r['packet']),Path(r['prompt']),core)
            if (bound.packet['source']['pmcid'] != r['source']['identity']['pmcid'] or
                    bound.input_hashes['source'] != r['source']['binding']['source_sha256']):
                raise ValueError('initial_direction_unrelated_source')
            verified={s['evidence_span_id']:s for s in bound.packet['evidence_spans']}
            blocks=(r.get('v3_lineage') or {}).get('source_blocks')
            for s in formal['provenance']['evidence_spans']:
                if (s['evidence_span_id'] not in verified or
                        any(verified[s['evidence_span_id']][k] != s[k] for k in ('text','text_hash'))):
                    raise ValueError('initial_direction_native_packet_span_mismatch')
                if blocks is not None and blocks.get(s['block_id'],'')[s['char_start']:s['char_end']] != s['text']:
                    raise ValueError('initial_direction_native_block_coordinate_mismatch')
            row=native_direction_record(formal,publication=r["source"]["identity"],
                core_sha256=file_hash(core),source_binding=r["source"].get("binding"))
            row['source_verification']={'packet_sha256':file_hash(Path(r['packet'])),
                'source_sha256':bound.input_hashes['source'],'original_block_coordinates_checked':blocks is not None,
                'verified_packet_evidence':bound.packet['evidence_spans']}
            row['record_identity']=content_hash({k:v for k,v in row.items() if k!='record_identity'})
            rows.append(row)
            bindings.append({"core":str(core),"sha256":file_hash(core),"source":r["source"].get("binding")})
        except (ValueError,KeyError,TypeError,OSError) as error:
            rejected.append({"core":str(r.get("core")),"reason":type(error).__name__+":"+str(error)})
    return {**discover_directions(rows),"rejected":rejected,"input_bindings":bindings,
            "effective_dependencies_sha256":dependencies,"implementation_sha256":file_hash(Path(__file__)),
            "optional_Work_consumption_role":"review_suggestions_only; not read by initial discovery"}
