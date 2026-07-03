from __future__ import annotations
from collections import Counter
def confirm_fulltext_conflicts(candidates:list[dict], claims:list[dict], retrieval_results:list[dict])->dict:
    available={str(x.get("paper_id")) for x in retrieval_results if x.get("full_text_status")=="available"}; rows=[]
    for c in candidates:
        cid=str(c.get("candidate_id")); linked=[x for x in claims if cid in map(str,x.get("linked_conflict_candidate_ids",[]))]; polarities={str(x.get("polarity") or x.get("direction")) for x in linked}-{"neutral","unknown","None"}
        paper_ids={str(x) for x in c.get("paper_ids",[])}
        if {"positive","negative"} <= polarities or {"increase","decrease"} <= polarities: status="full_text_supported"
        elif linked and paper_ids-available: status="full_text_partial"
        elif linked: status="full_text_mixed"
        elif paper_ids and not (paper_ids & available): status="full_text_unavailable"
        else: status="abstract_only"
        rows.append({"abstract_conflict_candidate_id":cid,"full_text_confirmation_status":status,"full_text_claim_ids":[x.get("claim_id") for x in linked],"no_oa_is_negative_evidence":False})
    counts=Counter(x["full_text_confirmation_status"] for x in rows)
    return {"confirmations":rows,"summary":{"status":"completed" if rows else "completed_no_candidates","candidate_count":len(rows),"fulltext_confirmed_conflict_count":counts["full_text_supported"],"status_counts":dict(counts),"copyright_safe":True}}
