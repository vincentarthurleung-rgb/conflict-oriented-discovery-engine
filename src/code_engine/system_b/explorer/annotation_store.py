"""Atomic local annotation persistence and manual-review metrics for Atlas."""
from __future__ import annotations
import csv
import json
import os
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

FINAL_LABELS={"VALID","PARTIAL","INVALID","VALID_MECHANISM_SPLIT","VALID_CONTEXT_SPLIT","VALID_WEAK_CONFLICT","CORRECTLY_REJECTED_NON_COMPARABLE","WRONGLY_REJECTED_SHOULD_BE_WEAK","NOISE","DUPLICATE","UNCLEAR"}
BOOL_FIELDS={"evidence_supported","subject_correct","relation_correct","object_correct","direction_correct","context_captured","anchor_correct","comparability_correct","candidate_type_correct","correctly_rejected","should_have_been_weak"}
ORDINAL_FIELDS={"seed_relevance","mechanistic_usefulness","worth_followup"}
FIELDS=("review_item_id","case_id","item_type","final_label","review_disposition","uncertainty_reason","evidence_supported","seed_relevance","subject_correct","relation_correct","object_correct","direction_correct","context_captured","anchor_correct","mechanistic_usefulness","comparability_correct","candidate_type_correct","correctly_rejected","should_have_been_weak","worth_followup","error_type","notes","reviewer_id","updated_at")
METRIC_NOTE="Manual-review metrics assess extraction and triage quality; they are not biological truth or validation."

def _atomic(path:Path,text:str):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=f".{path.name}.",dir=path.parent,text=True)
    try:
        with os.fdopen(fd,"w",encoding="utf-8",newline="") as handle:handle.write(text);handle.flush();os.fsync(handle.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

class AnnotationStore:
    def __init__(self,review_root,queue):
        self.root=Path(review_root) if review_root else None;self.queue=queue;self.queue_by_id={x["review_item_id"]:x for x in queue};self.records={}
        if self.root:self._load()
    @property
    def available(self):return self.root is not None and self.root.exists()
    def _load(self):
        path=self.root/"manual_review_annotations_live.json"
        try:value=json.loads(path.read_text(encoding="utf-8"))
        except (OSError,json.JSONDecodeError):value=[]
        if isinstance(value,dict):value=value.get("annotations",[])
        if isinstance(value,list):self.records={x["review_item_id"]:x for x in value if isinstance(x,dict) and x.get("review_item_id") in self.queue_by_id}
    def get(self,item_id):return self.records.get(item_id)
    def validate(self,payload):
        errors=[];label=str(payload.get("final_label","")).strip().upper();disposition=str(payload.get("review_disposition","submitted")).strip().lower()
        if disposition not in {"submitted","skipped","revisit"}:errors.append("review_disposition must be submitted, skipped, or revisit")
        if disposition=="submitted" and label not in FINAL_LABELS:errors.append("final_label must be one of: "+", ".join(sorted(FINAL_LABELS)))
        if disposition!="submitted" and label and label not in FINAL_LABELS:errors.append("final_label must be one of: "+", ".join(sorted(FINAL_LABELS)))
        for field in BOOL_FIELDS:
            if field in payload and str(payload[field]).upper() not in {"","0","1","NA"}:errors.append(f"{field} must be 1, 0, or NA")
        for field in ORDINAL_FIELDS:
            if field in payload and str(payload[field]).upper() not in {"","0","1","2","NA"}:errors.append(f"{field} must be 0, 1, 2, or NA")
        if errors:raise ValueError("; ".join(errors))
    def save(self,item_id,payload):
        if not self.available:raise RuntimeError("Review root is unavailable; configure an existing --review-root before saving annotations.")
        item=self.queue_by_id.get(item_id)
        if not item:raise KeyError("review_item_not_found")
        self.validate(payload);prior=self.records.get(item_id,{})
        record={field:"" for field in FIELDS};record.update(prior);record.update({k:str(v).upper() if k in BOOL_FIELDS|ORDINAL_FIELDS else v for k,v in payload.items() if k in FIELDS})
        disposition=str(payload.get("review_disposition") or prior.get("review_disposition") or "submitted").lower()
        label=str(payload.get("final_label") or "").upper() if disposition=="submitted" or payload.get("final_label") else ""
        record.update({"review_item_id":item_id,"case_id":item.get("case_id","") ,"item_type":item.get("item_type","") ,"final_label":label,"review_disposition":disposition,"reviewer_id":payload.get("reviewer_id") or prior.get("reviewer_id") or "local_user","updated_at":datetime.now(timezone.utc).isoformat()})
        self.records[item_id]=record;self.write_all();return record
    def write_all(self):
        rows=[self.records[x] for x in sorted(self.records)]
        _atomic(self.root/"manual_review_annotations_live.json",json.dumps({"annotations":rows},indent=2,ensure_ascii=False)+"\n")
        _atomic(self.root/"manual_review_annotations_live.jsonl","".join(json.dumps(x,ensure_ascii=False)+"\n" for x in rows))
        self._write_csv(rows);metrics=self.metrics();_atomic(self.root/"manual_review_metrics_live.json",json.dumps(metrics,indent=2,ensure_ascii=False)+"\n");_atomic(self.root/"manual_review_metrics_live.md",self._metrics_md(metrics))
    def export_rows(self):
        output=[]
        for item in self.queue:
            flat={k:(json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v) for k,v in item.items() if k!="suggested_review_fields"};flat.update({field:"" for field in FIELDS if field not in {"review_item_id","case_id","item_type"}});flat.update(self.records.get(item["review_item_id"],{}));output.append(flat)
        return output
    def _csv_text(self,rows):
        import io
        merged=self.export_rows();fields=list(merged[0]) if merged else list(FIELDS);handle=io.StringIO(newline="");writer=csv.DictWriter(handle,fieldnames=fields,extrasaction="ignore");writer.writeheader();writer.writerows(merged);return handle.getvalue()
    def _write_csv(self,rows):_atomic(self.root/"manual_review_annotations_live.csv",self._csv_text(rows))
    def csv_text(self):return self._csv_text(list(self.records.values()))
    def jsonl_text(self):return "".join(json.dumps(x,ensure_ascii=False)+"\n" for x in self.export_rows())
    @staticmethod
    def _ratio(n,d):return round(n/d,6) if d else None
    def metrics(self):
        reviewed=list(self.records.values());total=len(self.queue);labels=Counter(x["final_label"] for x in reviewed if x.get("final_label"));dispositions=Counter(x.get("review_disposition") or "submitted" for x in reviewed);types=Counter(x["item_type"] for x in reviewed);cases=Counter(x["case_id"] for x in reviewed)
        claims=[x for x in reviewed if x["item_type"]=="fulltext_l1_claim"];reviewable=[x for x in reviewed if x["item_type"] in {"abstract_reviewable_observation","fulltext_reviewable_observation"}];noncomp=[x for x in reviewed if x["item_type"]=="non_comparable_direction_pair"]
        follow=[x for x in reviewed if str(x.get("worth_followup","")).upper() not in {"","NA"}]
        return {"reviewed_count":len(reviewed),"unreviewed_count":total-len(reviewed),"reviewed_fraction":self._ratio(len(reviewed),total),"counts_by_final_label":dict(labels),"counts_by_disposition":dict(dispositions),"counts_by_item_type":dict(types),"counts_by_case":dict(cases),"claim_precision":self._ratio(sum(x["final_label"]=="VALID" for x in claims),len(claims)),"claim_usable_rate":self._ratio(sum(x["final_label"] in {"VALID","PARTIAL"} for x in claims),len(claims)),"reviewable_valid_rate":self._ratio(sum(x["final_label"]=="VALID" for x in reviewable),len(reviewable)),"noise_rate":self._ratio(labels["NOISE"],len(reviewed)),"non_comparable_rejection_accuracy":self._ratio(sum(x["final_label"]=="CORRECTLY_REJECTED_NON_COMPARABLE" for x in noncomp),len(noncomp)),"should_have_been_weak_rate":self._ratio(sum(x["final_label"]=="WRONGLY_REJECTED_SHOULD_BE_WEAK" for x in noncomp),len(noncomp)),"worth_followup_rate":self._ratio(sum(int(x["worth_followup"])>=1 for x in follow),len(follow)),"note":METRIC_NOTE}
    def _metrics_md(self,m):return "# Live Manual Review Metrics\n\n"+"\n".join(f"- {k}: {v}" for k,v in m.items() if k!="note")+f"\n\n{m['note']}\n"
