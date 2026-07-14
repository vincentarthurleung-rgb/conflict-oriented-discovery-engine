"""Cached read-only API over display KG v2 and manual-review artifacts."""
from __future__ import annotations
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import unquote
from .annotation_store import AnnotationStore
from .dossier_projection import DossierProjection
from .graph_projection import GraphProjection
from code_engine.system_b.annotation_schemas import schema_for_item_type
from code_engine.system_b.annotation_schemas.render_projection import form_projection

BOUNDARY = "C.O.D.E. Atlas supports evidence navigation and triage. Outputs require human review and are not biological validation."
CASE_CATALOG = {
    "emt_metastasis_drug_resistance_discovery_v1": ("EMT、转移与耐药", "上皮—间质转化如何影响肿瘤转移与药物耐受？", "emt"),
    "ferroptosis_cancer_therapy_response_discovery_v1": ("铁死亡与治疗反应", "铁死亡机制如何改变肿瘤治疗反应？", "ferroptosis"),
    "hif1a_hypoxia_cancer_response_discovery_v1": ("HIF-1α、缺氧与肿瘤反应", "缺氧与 HIF-1α 信号如何影响肿瘤反应？", "hif1a"),
    "il6_stat3_cancer_response_discovery_v1": ("IL-6 / STAT3 与肿瘤反应", "IL-6–STAT3 信号如何影响肿瘤反应？", "il6-stat3"),
    "nfkb_inflammation_cancer_response_discovery_v1": ("NF-κB、炎症与肿瘤", "NF-κB 介导的炎症如何影响肿瘤反应？", "nfkb"),
    "pdl1_immune_checkpoint_cancer_response_discovery_v1": ("PD-L1 与免疫检查点", "PD-L1 相关机制如何影响肿瘤免疫反应？", "pdl1"),
    "pi3k_akt_" + "m" + "tor_cancer_resistance_discovery_v1": ("PI3K-AKT-" + "m" + "TOR 与耐药", "PI3K-AKT-" + "m" + "TOR 通路如何参与肿瘤耐药？", "pi3k-akt-" + "m" + "tor"),
    "ros_oxidative_stress_cancer_response_discovery_v1": ("ROS、氧化应激与肿瘤反应", "活性氧与氧化应激如何改变肿瘤反应？", "ros"),
    "senescence_sasp_cancer_therapy_response_discovery_v1": ("细胞衰老、SASP 与治疗反应", "细胞衰老与 SASP 如何影响肿瘤治疗反应？", "senescence-sasp"),
    "tp53_apoptosis_cancer_therapy_response_discovery_v1": ("TP53、凋亡与治疗反应", "TP53 与凋亡机制如何影响肿瘤治疗反应？", "tp53"),
    "wnt_beta_catenin_cancer_stemness_immunity_discovery_v1": ("Wnt / β-catenin、干性与免疫", "Wnt / β-catenin 信号如何连接肿瘤干性与免疫反应？", "wnt-beta-catenin"),
}
LAYER_MAP = {
    "fulltext_l1_claim": "Fulltext Claims",
    "fulltext_reviewable_observation": "Fulltext Reviewable Observations",
    "abstract_reviewable_observation": "Abstract Reviewable Observations",
    "low_priority_context_observation": "Low-priority Context",
    "non_comparable_direction_pair": "Non-comparable / Mechanism Split",
    "weak_candidate": "Weak Candidates",
    "formal_hypothesis": "Formal Hypotheses",
}
OBSERVATION_FIELDS = (
    "subject", "relation", "object", "direction",
    "evidence_sentence", "claim_text", "preview",
    "pmid", "pmcid", "paper_title",
)
REQUIRED = ("display_entities_v2.jsonl", "display_triples_v2.jsonl", "display_chains_v2.jsonl", "case_focused_triples.jsonl", "case_focused_chains.jsonl", "triple_evidence_links.jsonl")

def _json(path):
    try: return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError): return {}

def _jsonl(path):
    if not path.is_file(): return []
    rows=[]
    for line in path.read_text(encoding="utf-8").splitlines():
        try: value=json.loads(line)
        except json.JSONDecodeError: continue
        if isinstance(value,dict): rows.append(value)
    return rows

def _bool(params,key): return str((params.get(key) or [""])[0]).lower() in {"1","true","yes"}
def _one(params,key,default=""): return (params.get(key) or [default])[0]
def _page(rows,params):
    try: limit=max(1,min(500,int(_one(params,"limit","100")))); offset=max(0,int(_one(params,"offset","0")))
    except ValueError: raise ValueError("limit and offset must be integers")
    return {"items":rows[offset:offset+limit],"total":len(rows),"limit":limit,"offset":offset}

class ExplorerAPI:
    def __init__(self, display_kg_root, review_root=None):
        configured=Path(display_kg_root);self.registry_path=configured/"current_projection.json" if configured.is_dir() and (configured/"current_projection.json").is_file() else None
        self.registry_mtime_ns=self.registry_path.stat().st_mtime_ns if self.registry_path else None
        self.configured_root=configured
        self.root=self._root_from_registry(configured) if self.registry_path else configured; self.review_root=Path(review_root) if review_root else None
        missing=[x for x in REQUIRED if not (self.root/x).is_file()]
        if missing: raise FileNotFoundError("Missing display KG v2 files: "+", ".join(missing)+". Run system_b_build_clean_kg first.")
        self.entities=_jsonl(self.root/"display_entities_v2.jsonl"); self.triples=_jsonl(self.root/"display_triples_v2.jsonl"); self.chains=_jsonl(self.root/"display_chains_v2.jsonl")
        self.case_triples=_jsonl(self.root/"case_focused_triples.jsonl"); self.case_chains=_jsonl(self.root/"case_focused_chains.jsonl"); self.evidence=_jsonl(self.root/"triple_evidence_links.jsonl")
        self.contexts=_jsonl(self.root/"triple_contexts.jsonl"); self.validators=_jsonl(self.root/"validator_annotations.jsonl"); self.conflicts=_jsonl(self.root/"conflict_lens_records.jsonl")
        self.entity_by_id={x["entity_id"]:x for x in self.entities}; self.triple_by_id={x["triple_id"]:x for x in self.triples}; self.chain_by_id={x["chain_id"]:x for x in self.chains}
        self.evidence_by_triple=defaultdict(list); self.context_by_triple=defaultdict(list); self.conflict_by_triple=defaultdict(list)
        for x in self.evidence:self.evidence_by_triple[x["triple_id"]].append(x)
        for x in self.contexts:self.context_by_triple[x["triple_id"]].append(x)
        for x in self.conflicts:
            for tid in x.get("linked_triple_ids",[]):self.conflict_by_triple[tid].append(x)
        self.review=_jsonl(self.review_root/"manual_review_queue.jsonl") if self.review_root else []
        dossier_index=_json(self.root/"dossier_index.json")
        self.dossier_triples=dossier_index.get("items",[]) if isinstance(dossier_index,dict) else []
        for x in _jsonl(self.root/"dossier_evidence.jsonl"):
            self.evidence_by_triple[x.get("triple_id")].append(x)
        self.review_by_id={x["review_item_id"]:x for x in self.review};self.annotations=AnnotationStore(self.review_root,self.review)
        self.paper_metrics=_json(self.review_root/"paper_metrics_starter.json") if self.review_root else {}
        self.annotation_status=self._annotation_status()
        self.cases=sorted({case for x in self.case_triples for case in [x["case_id"]]}|{case for x in self.triples for case in x.get("case_ids",[])})
        self.graph=GraphProjection(self);self.dossiers=DossierProjection(self)
        self.projection_manifest=_json(self.root/"projection_manifest.json")

    def _root_from_registry(self,configured):
        registry=_json(configured/"current_projection.json");relative=registry.get("projection_relative_path")
        if not relative or Path(relative).is_absolute() or ".." in Path(relative).parts:raise ValueError("unsafe current projection registry")
        root=(configured/relative).resolve();configured_resolved=configured.resolve()
        if configured_resolved not in root.parents:raise ValueError("current projection escapes configured root")
        manifest=root/"projection_manifest.json"
        if not manifest.is_file():raise FileNotFoundError("current projection manifest missing")
        expected=registry.get("projection_manifest_sha256")
        if expected and hashlib.sha256(manifest.read_bytes()).hexdigest()!=expected:raise ValueError("current projection manifest hash mismatch")
        return root

    def _refresh_if_needed(self):
        if not self.registry_path:return
        try:mtime=self.registry_path.stat().st_mtime_ns
        except OSError:return
        if mtime==self.registry_mtime_ns:return
        refreshed=ExplorerAPI(self.configured_root,self.review_root)
        self.__dict__.clear();self.__dict__.update(refreshed.__dict__)

    def _annotation_status(self):
        path=self.review_root/"manual_review_annotations_template.csv" if self.review_root else None
        if not path or not path.is_file(): return {"available":False,"reviewed":0,"total":len(self.review),"manual_metrics_available":False}
        with path.open(encoding="utf-8",newline="") as handle: rows=list(csv.DictReader(handle))
        reviewed=sum(bool((x.get("final_label") or "").strip()) for x in rows)
        return {"available":True,"reviewed":reviewed,"total":len(rows),"manual_metrics_available":reviewed>0}

    def summary(self):
        fulltext=sum(x.get("fulltext_evidence_count",0) for x in self.triples)
        warnings=[]
        if not self.review_root or not self.review_root.exists(): warnings.append("Review root unavailable; review panels are optional and empty.")
        return {"cases":len(self.cases),"display_entities":len(self.entities),"display_triples":len(self.triples),"display_chains":len(self.chains),"fulltext_evidence_count":fulltext,"conflict_lens_records":len(self.conflicts),"review_queue_count":len(self.review),"warnings":warnings,"scientific_boundary":BOUNDARY}

    def dispatch(self,path,params=None,method="GET",body=None):
        self._refresh_if_needed()
        params=params or {}
        if path=="/api/summary":return 200,self.summary()
        if path=="/api/cases":return 200,{"items":[self._case_summary(x) for x in self.cases],"total":len(self.cases)}
        if path.startswith("/api/case/"):
            case=unquote(path.removeprefix("/api/case/")); return (200,self._case(case)) if case in self.cases else (404,{"error":"case_not_found"})
        if path=="/api/entities":return 200,_page(self._entities(params),params)
        if path.startswith("/api/entity/"):
            value=self._entity(unquote(path.removeprefix("/api/entity/"))); return (200,value) if value else (404,{"error":"entity_not_found"})
        if path=="/api/triples":return 200,_page(self._triples(params),params)
        if path.startswith("/api/triple/"):
            value=self._triple(unquote(path.removeprefix("/api/triple/")),params); return (200,value) if value else (404,{"error":"triple_not_found"})
        if path=="/api/chains":return 200,_page(self._chains(params),params)
        if path.startswith("/api/chain/"):
            chain_id = unquote(path.removeprefix("/api/chain/"))
            value = self._chain_detail(chain_id)
            return (200, value) if value else (404, {"error": "chain_not_found"})
        if path=="/api/conflicts":return 200,self._conflicts(params)
        if path=="/api/review-summary":return 200,{"queue_count":len(self.review),"items_by_type":dict(Counter(x.get("item_type","unknown") for x in self.review)),"items_by_case":dict(Counter(x.get("case_id","unknown") for x in self.review)),"annotation_status":self.annotation_status,"paper_metrics":self.paper_metrics,"manual_metrics_notice":"Manual precision metrics require completed non-empty annotations."}
        if path=="/api/review-workspace":return 200,self._review_workspace()
        if path=="/api/review-cases":
            ws=self._review_workspace();return 200,{"cases":[{"case_id":c["case_id"],"total":c["total"],"reviewed":c["reviewed"],"unreviewed":c["unreviewed"]} for c in ws["cases"]],"total":ws["total_items"]}
        if path=="/api/review-layers":
            case=_one(params,"case_id");ws=self._review_workspace()
            for c in ws["cases"]:
                if c["case_id"]==case:return 200,c
            return 200,{"case_id":case,"total":0,"reviewed":0,"unreviewed":0,"layers":[]}
        if path=="/api/review-items":return 200,_page(self._review_items(params),params)
        if path.startswith("/api/review-item/"):
            item_id=unquote(path.removeprefix("/api/review-item/"));item=self.review_by_id.get(item_id)
            return (200,self._review_item_payload(item)) if item else (404,{"error":"review_item_not_found"})
        if path=="/api/annotations":return 200,{"items":list(self.annotations.records.values()),"total":len(self.annotations.records)}
        if path.startswith("/api/annotation/"):
            item_id=unquote(path.removeprefix("/api/annotation/"))
            if method=="POST":
                try:return 200,self.annotations.save(item_id,body or {})
                except KeyError:return 404,{"error":"review_item_not_found"}
                except RuntimeError as error:return 503,{"error":str(error)}
            value=self.annotations.get(item_id);return (200,value) if value else (404,{"error":"annotation_not_found"})
        if path=="/api/review-metrics":return 200,self.annotations.metrics()
        if path=="/api/review-metrics/recompute" and method=="POST":
            if not self.annotations.available:return 503,{"error":"Review root is unavailable; metrics cannot be persisted."}
            self.annotations.write_all();return 200,self.annotations.metrics()
        if path=="/api/review-export.csv":return 200,{"_raw":self.annotations.csv_text(),"_content_type":"text/csv; charset=utf-8","_filename":"manual_review_annotations_live.csv"}
        if path=="/api/review-export.jsonl":return 200,{"_raw":self.annotations.jsonl_text(),"_content_type":"application/x-ndjson; charset=utf-8","_filename":"manual_review_annotations_live.jsonl"}
        if path=="/api/search":return 200,self._search(_one(params,"q").casefold(),params)
        if path=="/api/dossiers":return 200,self.dossiers.list(params)
        if path=="/api/dossiers/audit" or path=="/api/dossier-audit":return 200,self.dossiers.audit()
        if path=="/api/dossiers/evidence-chain-compare":return 200,self.dossiers.compare_evidence_chains(params)
        if path.startswith("/api/dossier/"):
            tail=unquote(path.removeprefix("/api/dossier/"))
            if tail.endswith("/evidence"):
                value=self.dossiers.evidence(tail.removesuffix("/evidence"))
            elif tail.endswith("/context-matrix"):
                value=self.dossiers.context_matrix(tail.removesuffix("/context-matrix"))
            elif tail.endswith("/reasoning"):
                value=self.dossiers.reasoning(tail.removesuffix("/reasoning"))
            elif tail.endswith("/evidence-chains"):
                value=self.dossiers.evidence_chains(tail.removesuffix("/evidence-chains"))
            elif tail.endswith("/paths"):
                value=self.dossiers.paths(tail.removesuffix("/paths"),params)
            elif tail.endswith("/review-target"):
                value=self.dossiers.review_target(tail.removesuffix("/review-target"))
            else:
                value=self.dossiers.detail(tail)
            return (200,value) if value else (404,{"error":"dossier_not_found"})
        if path=="/api/graph/filters":return 200,self.graph.filters()
        if path=="/api/graph/case-overview":return 200,self.graph.case_overview()
        if path=="/api/graph/overview":return 200,self.graph.overview(params)
        if path.startswith("/api/graph/neighborhood/"):
            return 200,self.graph.neighborhood(unquote(path.removeprefix("/api/graph/neighborhood/")),params)
        if path=="/api/graph/path":return 200,self.graph.path(params)
        return 404,{"error":"not_found"}

    def _entities(self,p):
        rows=self.entities; q=_one(p,"q").casefold(); et=_one(p,"entity_type"); case=_one(p,"case_id")
        if q:rows=[x for x in rows if q in (x.get("display_label") or x.get("label","")).casefold() or any(q in a.casefold() for a in x.get("aliases",[]))]
        if et:rows=[x for x in rows if x.get("entity_type")==et]
        if case:rows=[x for x in rows if case in x.get("source_case_ids",[])]
        sort=_one(p,"sort","display_priority"); key={"degree":"degree","evidence_count":"evidence_count"}.get(sort,"display_priority_score")
        return sorted(rows,key=lambda x:(-(x.get(key) or 0),x.get("display_label","")))

    def _triples(self,p):
        rows=self.triples; case=_one(p,"case_id"); q=_one(p,"q").casefold(); status=_one(p,"conflict_status")
        if case:rows=[x for x in rows if case in x.get("case_ids",[])]
        if q:rows=[x for x in rows if q in f"{x.get('subject_display_label','')} {x.get('relation_normalized','')} {x.get('object_display_label','')}".casefold()]
        if _bool(p,"has_fulltext"):rows=[x for x in rows if x.get("fulltext_evidence_count",0)>0]
        if _bool(p,"has_results"):rows=[x for x in rows if x.get("results_section_evidence_count",0)>0]
        if status:rows=[x for x in rows if x.get("conflict_status")==status]
        return sorted(rows,key=lambda x:-x.get("display_priority_score_v2",0))

    def _chains(self,p):
        rows=self.chains; case=_one(p,"case_id"); q=_one(p,"q").casefold(); start=_one(p,"start_entity").casefold(); end=_one(p,"end_entity").casefold(); etype=_one(p,"entity_type")
        if case:rows=[x for x in rows if case in x.get("case_ids",[])]
        if q:rows=[x for x in rows if q in " ".join(x.get("entity_path",[])).casefold()]
        if start:rows=[x for x in rows if x.get("entity_path") and start in x["entity_path"][0].casefold()]
        if end:rows=[x for x in rows if x.get("entity_path") and end in x["entity_path"][-1].casefold()]
        if etype:
            typed={x.get("display_label") for x in self.entities if x.get("entity_type")==etype};rows=[x for x in rows if any(label in typed for label in x.get("entity_path",[]))]
        if _bool(p,"has_fulltext"):rows=[x for x in rows if x.get("fulltext_evidence_count_sum",0)>0]
        if _bool(p,"has_results"):rows=[x for x in rows if x.get("results_section_evidence_count_sum",0)>0]
        if _bool(p,"has_conflict"):rows=[x for x in rows if x.get("conflict_statuses")]
        return sorted(rows,key=lambda x:-x.get("chain_quality_score",0))

    def _chain_detail(self, chain_id):
        """Return enriched chain detail including triples, evidence, contexts, and review status."""
        chain = self.chain_by_id.get(chain_id)
        if not chain:
            return None
        triple_ids = chain.get("triple_ids", [])
        case_ids = chain.get("case_ids", [])

        # Collect triples in this chain
        triples = []
        evidence_by_triple = {}
        contexts_by_triple = {}
        for tid in triple_ids:
            triple = self.triple_by_id.get(tid)
            if triple:
                triples.append(triple)
            evidence_by_triple[tid] = self.evidence_by_triple.get(tid, [])
            contexts_by_triple[tid] = self.context_by_triple.get(tid, [])

        # Validator annotations linked to these cases
        validator_annotations = [
            x for x in self.validators
            if any(c in case_ids for c in (x.get("case_id", ""), x.get("case_ids", [])))
        ]

        # Conflict lens records linked to these triples
        conflict_records = []
        seen = set()
        for tid in triple_ids:
            for cr in self.conflict_by_triple.get(tid, []):
                rid = cr.get("record_id") or json.dumps(cr, sort_keys=True, default=str)
                if rid not in seen:
                    seen.add(rid)
                    conflict_records.append(self._enriched_conflict(cr))

        # Manual review summary
        review_items = [x for x in self.review if x.get("case_id") in case_ids]
        review_summary = {
            "total": len(review_items),
            "reviewed": sum(1 for x in review_items
                           if self.annotations.get(x["review_item_id"])),
            "by_type": dict(Counter(x.get("item_type", "unknown") for x in review_items)),
        }

        return {
            "chain": chain,
            "triples": triples,
            "evidence_by_triple": evidence_by_triple,
            "contexts_by_triple": contexts_by_triple,
            "validator_annotations": validator_annotations,
            "conflict_lens_records": conflict_records,
            "manual_review_summary": review_summary,
            "scientific_boundary": BOUNDARY,
        }

    def _conflicts(self,p):
        """Return enriched conflicts with bucketing and optional filtering.

        Query params:
          bucket: potential_conflict | mechanism_diagnostic | rejected_non_comparable
                  | data_quality | all (default: potential_conflict)
          case_id: filter by case
          record_type: filter by exact record_type
          include_hidden: true|false (default: false)
        """
        rows = self.conflicts
        case = _one(p, "case_id")
        kind = _one(p, "record_type")
        bucket = _one(p, "bucket", "potential_conflict")
        include_hidden = _bool(p, "include_hidden")

        if case:
            rows = [x for x in rows if x.get("case_id") == case]
        if kind:
            rows = [x for x in rows if x.get("record_type") == kind]

        # Enrich and classify all records
        enriched = [self._enriched_conflict(x) for x in rows]
        classified = [self._classify_conflict(x) for x in enriched]

        # Build summary across ALL records (before bucket filtering)
        summary = self._conflict_summary(classified)

        # Filter by bucket unless "all"
        if bucket != "all":
            classified = [x for x in classified if x.get("display_bucket") == bucket]

        # Filter out hidden records unless include_hidden
        if not include_hidden:
            classified = [x for x in classified if x.get("display_recommended", True)]

        items = [self._strip_classification_fields(x) for x in classified]
        result = _page(items, p)
        result["summary"] = summary
        return result

    @staticmethod
    def _classify_conflict(record):
        """Classify a conflict record into a display bucket."""
        rt = record.get("record_type", "")
        ct = record.get("candidate_type", "")
        has_a = record.get("observation_a_has_content", False)
        has_b = record.get("observation_b_has_content", False)
        has_pair_preview = has_a or has_b

        # Determine bucket
        is_mechanism = (rt == "mechanism_split" or ct == "mechanism_split" or
                        "mechanism_split" in str(rt).lower())
        is_non_comparable = (rt == "non_comparable_direction_pair" or
                             "non_comparable" in str(record.get("comparability_label", "")).lower())
        is_potential = rt in ("weak_candidate", "context_split", "formal_hypothesis")

        if not has_pair_preview:
            bucket = "data_quality"
            recommended = False
            hide_reason = "missing_observation_preview"
        elif is_mechanism:
            bucket = "mechanism_diagnostic"
            recommended = True
            hide_reason = None
        elif is_non_comparable:
            bucket = "rejected_non_comparable"
            recommended = True
            hide_reason = None
        elif is_potential and has_pair_preview:
            bucket = "potential_conflict"
            recommended = True
            hide_reason = None
        else:
            # Fallback: treat as data quality if unclear
            bucket = "data_quality"
            recommended = False
            hide_reason = "unclassified_record_type"

        return {
            **record,
            "display_bucket": bucket,
            "display_recommended": recommended,
            "has_observation_a": has_a,
            "has_observation_b": has_b,
            "has_pair_preview": has_pair_preview,
            "hide_from_default_reason": hide_reason,
        }

    @staticmethod
    def _conflict_summary(classified):
        """Build summary statistics from classified conflict records."""
        counts = {
            "potential_conflict_count": 0,
            "mechanism_diagnostic_count": 0,
            "rejected_non_comparable_count": 0,
            "data_quality_count": 0,
            "hidden_missing_preview_count": 0,
            "total_records": len(classified),
        }
        for x in classified:
            bucket = x.get("display_bucket", "data_quality")
            key = f"{bucket}_count"
            if key in counts:
                counts[key] += 1
            if x.get("hide_from_default_reason") == "missing_observation_preview":
                counts["hidden_missing_preview_count"] += 1
        return counts

    @staticmethod
    def _strip_classification_fields(record):
        """Remove internal classification fields from the record before returning to client."""
        strip_keys = {
            "display_bucket", "display_recommended", "has_observation_a",
            "has_observation_b", "has_pair_preview", "hide_from_default_reason",
        }
        return {k: v for k, v in record.items() if k not in strip_keys}

    def _extract_observation(self, record, prefix):
        """Extract observation fields from conflict record with multiple field name fallbacks."""
        obs = {}
        # Try prefixed fields: observation_a_subject, observation_a_preview, etc.
        for field in OBSERVATION_FIELDS:
            for key in (f"{prefix}_{field}", f"{prefix}{field}"):
                if key in record and record[key]:
                    obs[field] = record[key]
                    break
            else:
                obs[field] = None
        # Try alternative naming: left_observation, right_observation, claim_a, claim_b
        if not any(obs.values()):
            alt_prefixes = {
                "observation_a": ("left_observation", "claim_a", "supporting_observation"),
                "observation_b": ("right_observation", "claim_b", "opposing_observation"),
            }
            for alt in alt_prefixes.get(prefix, ()):
                if isinstance(record.get(alt), dict):
                    obs.update({k: record[alt].get(k) for k in OBSERVATION_FIELDS if record[alt].get(k)})
                elif isinstance(record.get(alt), str):
                    obs["preview"] = record[alt]
        # Fallback: try supporting_observations_preview / opposing_observations_preview
        if prefix == "observation_a" and not any(obs.values()):
            for key in ("supporting_observations_preview", "supporting_observation_preview"):
                if record.get(key):
                    obs["preview"] = str(record[key])
                    break
        if prefix == "observation_b" and not any(obs.values()):
            for key in ("opposing_observations_preview", "opposing_observation_preview"):
                if record.get(key):
                    obs["preview"] = str(record[key])
                    break
        return obs

    def _enriched_conflict(self, record):
        """Enrich a conflict record with extracted observation A/B fields."""
        obs_a = self._extract_observation(record, "observation_a")
        obs_b = self._extract_observation(record, "observation_b")
        has_a = any(v for v in obs_a.values())
        has_b = any(v for v in obs_b.values())
        return {
            **record,
            "observation_a_extracted": obs_a,
            "observation_b_extracted": obs_b,
            "observation_a_has_content": has_a,
            "observation_b_has_content": has_b,
            "observation_a_warning": None if has_a else "Source record lacks observation A preview.",
            "observation_b_warning": None if has_b else "Source record lacks observation B preview.",
        }

    def _review_workspace(self):
        """Build case-first review workspace with layers."""
        review_cases = sorted(set(x.get("case_id", "unknown") for x in self.review))
        workspace = {"cases": [], "total_items": len(self.review)}
        for case_id in review_cases:
            case_items = [x for x in self.review if x.get("case_id") == case_id]
            layers = {}
            for item in case_items:
                itype = item.get("item_type", "unknown")
                layer_id = itype
                if layer_id not in layers:
                    layers[layer_id] = {
                        "layer_id": layer_id,
                        "label": LAYER_MAP.get(itype, itype.replace("_", " ").title()),
                        "total": 0, "reviewed": 0, "unreviewed": 0,
                        "valid": 0, "partial": 0, "invalid": 0, "unclear": 0,
                    }
                layers[layer_id]["total"] += 1
                annot = self.annotations.get(item["review_item_id"])
                if annot:
                    layers[layer_id]["reviewed"] += 1
                    lbl = (annot.get("final_label") or "").upper()
                    if lbl == "VALID": layers[layer_id]["valid"] += 1
                    elif lbl == "PARTIAL": layers[layer_id]["partial"] += 1
                    elif lbl == "INVALID": layers[layer_id]["invalid"] += 1
                    elif lbl == "UNCLEAR": layers[layer_id]["unclear"] += 1
                else:
                    layers[layer_id]["unreviewed"] += 1
            total = len(case_items)
            reviewed = sum(1 for x in case_items if self.annotations.get(x["review_item_id"]))
            workspace["cases"].append({
                "case_id": case_id,
                "total": total,
                "reviewed": reviewed,
                "unreviewed": total - reviewed,
                "layers": sorted(layers.values(), key=lambda l: l["label"]),
            })
        return workspace

    def _review_items(self,p):
        rows=[];case=_one(p,"case_id");kind=_one(p,"item_type");status=_one(p,"review_status");label=_one(p,"final_label").upper();q=_one(p,"q").casefold()
        for item in self.review:
            annotation=self.annotations.get(item["review_item_id"]);row=self._review_item_payload(item);row.update({"review_status":"reviewed" if annotation else "unreviewed"})
            if case and item.get("case_id")!=case:continue
            if kind and item.get("item_type")!=kind:continue
            if status and status!="all" and row["review_status"]!=status:continue
            if label and (annotation or {}).get("final_label")!=label:continue
            if q and q not in " ".join(str(item.get(x,"")) for x in ("claim_text","evidence_sentence","subject","relation","object","pmid","paper_title")).casefold():continue
            rows.append(row)
        return rows

    def _review_item_payload(self, item):
        schema = schema_for_item_type(item.get("item_type", ""))
        return {
            **item,
            "annotation": self.annotations.get(item["review_item_id"]),
            "schema_id": schema.schema_id if schema else None,
            "schema_version": schema.version if schema else None,
            "schema_hash": schema.sha256 if schema else None,
            "form_definition": form_projection(schema),
        }

    def _case_summary(self,case):
        triples=[x for x in self.case_triples if x["case_id"]==case]; chains=[x for x in self.case_chains if x["case_id"]==case]
        evidence=[x for rows in self.evidence_by_triple.values() for x in rows if x.get("case_id")==case]
        contexts=[x for rows in self.context_by_triple.values() for x in rows if x.get("case_id")==case]
        traces=[x.get("reasoning_trace") for x in evidence if isinstance(x.get("reasoning_trace"),dict)]
        conflicts=[x for x in self.conflicts if x.get("case_id")==case]
        annotations=sum(1 for x in self.review if x.get("case_id")==case and self.annotations.get(x.get("review_item_id")))
        review_total=sum(x.get("case_id")==case for x in self.review)
        title,question,short_name=CASE_CATALOG.get(case,(case.replace("_"," ").title(),"查看该研究问题下的机制证据。",case))
        return {
            "case_id":case,"short_name":short_name,"display_name":title,"research_question":question,
            "display_triples_count":len(triples),"display_chains_count":len(chains),
            "evidence_count":len(evidence),"fulltext_evidence_count":sum("full" in str(x.get("source_scope","")).casefold() for x in evidence),
            "paper_count":len({x.get("pmid") or x.get("pmcid") or x.get("paper_title") for x in evidence if x.get("pmid") or x.get("pmcid") or x.get("paper_title")}),
            "non_comparable_records":sum(x.get("record_type")=="non_comparable_direction_pair" for x in conflicts),
            "weak_candidates":sum(x.get("record_type")=="weak_candidate" for x in conflicts),
            "formal_conflict_count":sum(x.get("record_type")=="formal_hypothesis" for x in conflicts),
            "review_queue_items":review_total,"reviewed_items":annotations,
            "review_progress":round(annotations/review_total,4) if review_total else None,
            "capabilities":{
                "fulltext": "available" if evidence and any("full" in str(x.get("source_scope","")).casefold() for x in evidence) else "unavailable",
                "reasoning": "available" if traces and all(x.get("trace_status") not in {None,"","invalid"} for x in traces) else "partial" if traces else "unavailable",
                "context": "available" if contexts else "unavailable",
                "reentry": "available" if evidence else "legacy_unknown",
            },
            "last_synced_at":self.projection_manifest.get("generated_at"),
        }

    def _case(self,case):
        triples=sorted((x for x in self.case_triples if x["case_id"]==case),key=lambda x:x.get("case_display_rank",999)); chains=sorted((x for x in self.case_chains if x["case_id"]==case),key=lambda x:x.get("case_display_rank",999))
        entity_ids={tid for x in triples[:50] for tid in (self.triple_by_id.get(x["triple_id"],{}).get("subject_id"),self.triple_by_id.get(x["triple_id"],{}).get("object_id")) if tid}
        dossiers=self.dossiers.list({"case_id":[case],"limit":["10"],"sort":["evidence"]})["items"]
        contexts=[x for rows in self.context_by_triple.values() for x in rows if x.get("case_id")==case]
        context_fields=("species","cell_type","tissue","treatment","dose","duration","assay_method")
        common_context={field:Counter(str(x.get(field)) for x in contexts if x.get(field)).most_common(3) for field in context_fields}
        return {**self._case_summary(case),"triples":triples[:150],"chains":chains[:300],"key_dossiers":dossiers,"common_context":common_context,"top_entities":sorted((self.entity_by_id[x] for x in entity_ids if x in self.entity_by_id),key=lambda x:-x.get("display_priority_score",0))[:20],"conflicts":[x for x in self.conflicts if x.get("case_id")==case]}

    def _entity(self,eid):
        entity=self.entity_by_id.get(eid)
        if not entity:return None
        incoming=[x for x in self.triples if x.get("object_id")==eid]; outgoing=[x for x in self.triples if x.get("subject_id")==eid]; label=entity.get("display_label","")
        return {**entity,"incoming_triples":incoming,"outgoing_triples":outgoing,"chains":[x for x in self.chains if label in x.get("entity_path",[])][:100],"conflicts":[x for x in self.conflicts if label.casefold() in f"{x.get('subject','')} {x.get('object','')} {x.get('observation_a_preview','')} {x.get('observation_b_preview','')}".casefold()]}

    def _triple(self,tid,p):
        triple=self.triple_by_id.get(tid)
        if not triple:return None
        evidence=self.evidence_by_triple[tid]
        scope=_one(p,"scope")
        if scope=="fulltext":evidence=[x for x in evidence if "full" in str(x.get("source_scope",""))]
        elif scope=="abstract":evidence=[x for x in evidence if x.get("source_scope")=="abstract"]
        elif scope=="results":evidence=[x for x in evidence if "result" in str(x.get("section_title","")).casefold()]
        try: limit=max(1,min(200,int(_one(p,"evidence_limit","50"))))
        except ValueError:raise ValueError("evidence_limit must be an integer")
        cases=set(triple.get("case_ids",[]))
        enriched=[]
        for link in evidence[:limit]:
            item_id=f"{link.get('case_id')}::{link.get('item_type')}::{link.get('source_file')}::{link.get('source_line')}";item=self.review_by_id.get(item_id)
            enriched.append({**link,"review_item_id":item_id if item else None,"review_status":"reviewed" if item and self.annotations.get(item_id) else "unreviewed" if item else "not_in_review_queue","annotation":self.annotations.get(item_id) if item else None})
        return {**triple,"evidence_links":enriched,"evidence_total":len(evidence),"contexts":self.context_by_triple[tid],"validator_annotations":[x for x in self.validators if x.get("case_id") in cases],"conflict_lens_records":self.conflict_by_triple[tid],"manual_review_status":{"status":"evidence_level","note":"Manual labels assess extraction and triage quality, not biological validation."}}

    def _search(self,q,p):
        if not q:return {"cases":[],"dossiers":[],"entities":[],"papers":[],"paths":[]}
        def rank_text(labels,aliases=()):
            candidates=[str(x or "") for x in list(labels)+list(aliases) if x]
            folded=[x.casefold() for x in candidates]
            if any(x==q for x in folded):return 0,"exact"
            if any(x.startswith(q) for x in folded):return 1,"prefix"
            qtokens=[x for x in q.split() if x]
            if qtokens and any(all(tok in x.split() for tok in qtokens) for x in folded):return 2,"token"
            if any(q in x for x in folded):return 3,"contains"
            return 99,"no_match"
        cases=[]
        for c in self.cases:
            rank,reason=rank_text([c.replace("_"," "),c],[c.split("_")[0] if "_" in c else ""])
            if rank<99:
                row=self._case_summary(c);row.update({"search_rank":rank,"match_reason":reason});cases.append(row)
        cases=sorted(cases,key=lambda x:(x["search_rank"],x["case_id"]))[:20]
        dossiers=[]
        for row in self.dossiers.list({"limit":["200"]})["items"]:
            labels=[row.get("humanized_statement"),row.get("dossier_id"),row.get("backing_triple_id")]
            aliases=[row.get("subject",{}).get("label"),row.get("object",{}).get("label"),row.get("relation",{}).get("normalized")]
            rank,reason=rank_text(labels,aliases)
            if rank<99:
                row={**row,"search_rank":rank,"match_reason":reason};dossiers.append(row)
        dossiers=sorted(dossiers,key=lambda x:(x["search_rank"],-x.get("priority_score",0),x["dossier_id"]))[:20]
        entities=[]
        for entity in self.entities:
            rank,reason=rank_text([entity.get("display_label"),entity.get("label"),entity.get("entity_id")],entity.get("aliases",[]))
            if rank<99:
                entities.append({**entity,"search_rank":rank,"match_reason":reason})
        entities=sorted(entities,key=lambda x:(x["search_rank"],-(x.get("display_priority_score") or 0),x.get("display_label","")))[:20]
        paths=[]
        for chain in self.chains:
            rank,reason=rank_text(chain.get("entity_path",[]),chain.get("relation_path",[])+[chain.get("chain_id")])
            if rank<99:
                paths.append({**chain,"search_rank":rank,"match_reason":reason})
        paths=sorted(paths,key=lambda x:(x["search_rank"],-x.get("chain_quality_score",0),x.get("chain_id","")))[:20]
        papers=[];seen={}
        for e in self.evidence:
            key=e.get("pmid") or e.get("pmcid") or e.get("paper_title")
            if not key:continue
            rank,reason=rank_text([e.get("paper_title"),e.get("pmid"),e.get("pmcid")],[e.get("evidence_sentence")])
            if rank>=99:continue
            if q in {str(e.get("pmid","")).casefold(),str(e.get("pmcid","")).casefold()}:rank=-1;reason="identifier_exact"
            row={"paper_title":e.get("paper_title"),"pmid":e.get("pmid"),"pmcid":e.get("pmcid"),"case_id":e.get("case_id"),"evidence_sentence":e.get("evidence_sentence"),"search_rank":rank,"match_reason":reason}
            prior=seen.get(key)
            if prior is None or (row["search_rank"],row.get("paper_title") or "")<(prior["search_rank"],prior.get("paper_title") or ""):
                seen[key]=row
        papers=sorted(seen.values(),key=lambda x:(x["search_rank"],x.get("paper_title") or "",x.get("pmid") or ""))[:20]
        return {"cases":cases,"dossiers":dossiers,"entities":entities,"papers":papers,"paths":paths}
