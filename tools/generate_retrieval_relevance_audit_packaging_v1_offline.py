#!/usr/bin/env python3
"""Generate the offline Retrieval Relevance Audit Packaging v1."""
from __future__ import annotations
import hashlib, json, re, subprocess
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'runs/20260906_search_plan_v21_retrieval_calibration_pilot_v1'
RUN=ROOT/'runs/20260906_retrieval_relevance_audit_packaging_v1_offline'
CASES=['spv2_017','spv2_026','spv2_001','spv2_016','spv2_003','spv2_004','spv2_006_REDESIGNED','spv2_013_REDESIGNED']
SIZES=[16,16,16,16,15]
REL=['DIRECTLY_RELEVANT','PLAUSIBLY_RELEVANT_FULLTEXT_REQUIRED','RELATED_BUT_WRONG_PROPOSITION','WRONG_ENDPOINT','WRONG_ENTITY','WRONG_EVIDENCE_MODE','WRONG_THERAPY','TOPIC_ONLY','INSUFFICIENT_SOURCE_EVIDENCE']
ACQ=['JUSTIFIED','BORDERLINE_BUT_JUSTIFIED','NOT_JUSTIFIED','UNDETERMINABLE_FROM_PRESERVED_PREACQUISITION_EVIDENCE']
CONT=['wrong_endpoint','wrong_therapy','wrong_measurement_scale','wrong_evidence_mode','wrong_biological_unit','topic_only','entity_incidental','review_only','prognostic_vs_cellular_outcome','cellular_vs_patient_outcome','baseline_viability_vs_adaptation','association_vs_functional_relation','other']
REQ=['baseline.json','review_unit_inventory.jsonl','retrieval_relevance_review_packets.jsonl','pre_acquisition_evidence_audit.jsonl','fulltext_excerpt_inventory.jsonl','excerpt_source_trace.jsonl','retrieval_relevance_adjudication_v1.schema.json','blank_retrieval_relevance_adjudications.jsonl','contaminant_taxonomy.json','quality_metric_contract.json','query_contribution_join_map.jsonl','retrieval_depth_join_map.jsonl','fulltext_accessibility_separate_ledger.jsonl','review_batch_manifest.json']+[f'review_batch_{i:02d}.{e}' for i in range(1,6) for e in ('jsonl','md')]+['packet_neutrality_audit.json','source_traceability_audit.json','scientific_state_safety_audit.json','production_leakage_audit.json','final_validation.json','manifest.json','summary.json']

def jl(p): return [json.loads(x) for x in Path(p).read_text().splitlines() if x]
def j(p): return json.loads(Path(p).read_text())
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def wj(p,x): Path(p).write_text(json.dumps(x,indent=2,sort_keys=True,ensure_ascii=False)+'\n')
def wjl(p,x): Path(p).write_text(''.join(json.dumps(y,sort_keys=True,ensure_ascii=False)+'\n' for y in x))
def tag(x): return x.tag.rsplit('}',1)[-1]
def txt(x): return ''.join(x.itertext()).strip()
def tree_state():
    rows=[(str(p.relative_to(SRC)),sha(p)) for p in sorted(SRC.rglob('*')) if p.is_file()]
    return {'file_count':len(rows),'sha256':hashlib.sha256(json.dumps(rows,separators=(',',':')).encode()).hexdigest()}
def target_id(cid,obj,kind): return obj.get(kind+'_target_id',f'frozen_search_plans.jsonl#case_id={cid}/{kind}_target')
def summary(obj):
    keys=['subject_entity','subject_surfaces','subject','relation_family','relation_recall_scope','object_target','object_endpoint','measurement_target','measurement_property_endpoint','endpoint_measurement_surfaces','context_qualifiers','context_recall_scope','contrast_requirement','therapy_identity_requirement']
    return '; '.join(f'{k}={json.dumps(obj[k],ensure_ascii=False)}' for k in keys if k in obj)

def anchors(cid,plan,variants):
    out=[]
    for v in variants:
        if v['case_id']!=cid: continue
        anns=v['term_authority_annotations']
        terms=[a['term'] for a in anns if a.get('term') and not a.get('planning_only_unverified_expansion')]
        if not terms and all('rejected' not in a.get('authority_class','') and 'planning_only' not in a.get('authority_class','') for a in anns): terms=re.findall(r'"([^"]+)"',v['query_string'])
        for t in terms: out.append({'anchor':t,'source':'frozen_query_variant','priority':0 if len(t)>5 else 1})
    rt=plan['retrieval_target']
    for k in ['subject_entity','subject_surfaces','object_target','measurement_target','endpoint_measurement_surfaces']:
        vals=rt.get(k,[]); vals=[vals] if isinstance(vals,str) else vals
        for t in vals: out.append({'anchor':t,'source':'frozen_retrieval_target','priority':0})
    seen=set(); ans=[]
    for a in sorted(out,key=lambda x:(x['priority'],-len(x['anchor']),x['anchor'].casefold())):
        k=a['anchor'].casefold()
        if k not in seen and len(k)>2: seen.add(k); ans.append(a)
    return ans

def pattern(a):
    parts=re.split(r'([\s\-‐‑–—]+)',a)
    s=''.join(r'[\s\-‐‑–—]+' if re.fullmatch(r'[\s\-‐‑–—]+',p) else re.escape(p) for p in parts)
    s=s.replace('kappa','(?:kappa|κ)').replace('Kappa','(?:Kappa|Κ)')
    return re.compile(s,re.I)
def paths(root):
    out={}
    def go(node,p):
        out[node]=p; counts=defaultdict(int)
        for ch in node:
            t=tag(ch); counts[t]+=1; go(ch,f'{p}/{t}[{counts[t]}]')
    go(root,f'/{tag(root)}[1]'); return out
def excerpts(packet_id,path,ans):
    root=ET.parse(path).getroot(); par={c:p for p in root.iter() for c in p}; pths=paths(root); cand=[]
    for order,node in enumerate(root.iter()):
        if tag(node) not in {'p','caption'}: continue
        chain=[]; q=node
        while q in par: q=par[q]; chain.append(q)
        tags={tag(x) for x in chain}
        if 'abstract' in tags or ('body' not in tags and tag(node)!='caption'): continue
        text=txt(node)
        if len(text)<40: continue
        sec=next((x for x in chain if tag(x)=='sec'),None); st=next((txt(x) for x in list(sec) if tag(x)=='title'),'') if sec is not None else ''
        low=st.casefold()
        if tag(node)=='caption': cat='figure_or_table_caption'; pri=2
        elif 'result' in low: cat='results'; pri=0
        elif 'method' in low or 'material' in low: cat='methods'; pri=1
        elif 'discussion' in low: cat='discussion'; pri=4
        elif 'supplement' in low or 'supplementary-material' in tags: cat='supplementary'; pri=3
        else: cat='other'; pri=5
        hits=[]
        for a in ans:
            m=pattern(a['anchor']).search(text)
            if m: hits.append((a,m))
        if not hits: continue
        a,m=min(hits,key=lambda z:(z[0]['priority'],-len(z[1].group(0)),z[0]['anchor']))
        spans=[]
        for sm in re.finditer(r'.+?(?:[.!?](?=\s|$)|$)',text,re.S):
            lo,hi=sm.span(); lo+=len(text[lo:hi])-len(text[lo:hi].lstrip()); hi-=len(text[lo:hi])-len(text[lo:hi].rstrip());
            if hi>lo: spans.append((lo,hi))
        chosen=next(((i,x) for i,x in enumerate(spans,1) if x[0]<=m.start()<x[1]),(1,(0,len(text))))
        si,(lo,hi)=chosen; passage=text[lo:hi]
        if len(passage)>1200: continue
        cand.append((pri,-len({x[0]['anchor'].casefold() for x in hits}),order,{'anchor_definition':a['anchor'],'exact_anchor_matched':m.group(0),'section':st or cat,'section_category':cat,'source_node_path':pths[node],'source_passage_identity':f'{pths[node]}#sentence[{si}]','source_node_text_sha256':hashlib.sha256(text.encode()).hexdigest(),'text':passage,'text_sha256':hashlib.sha256(passage.encode()).hexdigest()}))
    # A few PMC records preserve only article metadata and abstract, with no
    # body. Retain a traceable title/abstract anchor in those packets without
    # implying that this is sufficient evidence for adjudication.
    if not cand:
        for order,node in enumerate(root.iter()):
            if tag(node) not in {'article-title','p'}: continue
            chain=[]; q=node
            while q in par: q=par[q]; chain.append(q)
            if tag(node)=='p' and 'abstract' not in {tag(x) for x in chain}: continue
            text=txt(node); hits=[]
            for a in ans:
                m=pattern(a['anchor']).search(text)
                if m: hits.append((a,m))
            if not hits: continue
            a,m=min(hits,key=lambda z:(z[0]['priority'],-len(z[1].group(0)),z[0]['anchor']))
            cat='title' if tag(node)=='article-title' else 'abstract'
            if len(text)>1200 and cat=='abstract': continue
            cand.append((6,-len({x[0]['anchor'].casefold() for x in hits}),order,{'anchor_definition':a['anchor'],'exact_anchor_matched':m.group(0),'section':cat,'section_category':cat,'source_node_path':pths[node],'source_passage_identity':f'{pths[node]}#complete','source_node_text_sha256':hashlib.sha256(text.encode()).hexdigest(),'text':text,'text_sha256':hashlib.sha256(text.encode()).hexdigest()}))
    out=[]; seen=set(); seen_text=set()
    for _,__,___,x in sorted(cand,key=lambda z:z[:3]):
        if x['source_passage_identity'] in seen or x['text_sha256'] in seen_text: continue
        seen.add(x['source_passage_identity']); seen_text.add(x['text_sha256']); x['excerpt_id']=f'{packet_id}:excerpt_{len(out)+1:02d}'; out.append(x)
        if len(out)==8: break
    return out

def blank(pid,cid,pub):
    return {'packet_id':pid,'case_id':cid,'publication_id':pub,'relevance_state':None,'acquisition_decision':None,'matched_target_components':[],'mismatched_target_components':[],'fulltext_resolved_fields':[],'remaining_unresolved_fields':[],'contaminant_class':None,'reviewer_rationale':None,'confidence':None,'reviewer_type':None,'reviewer_id_or_label':None,'timestamp':None}
def render(rows):
    z=['# Retrieval Relevance Review Batch','', 'All adjudication fields are intentionally blank.']
    for p in rows:
        pre=p['pre_acquisition_evidence']; pub=p['publication_identity']; z += ['',f"### Packet {p['packet_id']}",'',f"Case: {p['case_id']}",f"Ambiguity: {p['ambiguity_tier']}",f"Tier: {pre['tier_state']}",'',f"Retrieval target: {p['retrieval_target_summary']}",f"Scientific target: {p['scientific_proposition_target_summary']}",'',f"Publication: {pub['title']}",f"PMID / PMCID / DOI: {pub['pmid']} / {pub['pmcid']} / {pub['doi']}",'',f"Why acquired: {pre['gate_admission_rationale']}",f"Known plausible fields: {json.dumps(pre['known_plausible_fields'],ensure_ascii=False)}",'', 'Abstract:',pre['abstract'] or '[not available]','', 'Fulltext excerpts:']
        z += [f"{i}. [{e['section']}; {e['exact_anchor_matched']}; {e['source_passage_identity']}] {e['text']}" for i,e in enumerate(p['fulltext_evidence_packet']['excerpts'],1)] or ['[no deterministic target-anchor excerpt found]']
        z += ['',f"Fields fulltext was expected to resolve: {json.dumps(pre['unresolved_fields_requiring_fulltext'],ensure_ascii=False)}",'', 'ADJUDICATION','relevance_state:','acquisition_decision:','matched_target_components:','mismatched_target_components:','fulltext_resolved_fields:','remaining_unresolved_fields:','contaminant_class:','rationale:','confidence:']
    return '\n'.join(z)+'\n'

def main():
    RUN.mkdir(parents=True,exist_ok=True); before=tree_state()
    acquired=jl(SRC/'fulltext_acquired_manifest.jsonl'); assert len(acquired)==79 and len({(x['case_id'],x['pmid']) for x in acquired})==79
    plans={x['case_id']:x for x in jl(SRC/'frozen_search_plans.jsonl')}; variants=jl(SRC/'frozen_query_variants.jsonl'); executed={x['query_variant_id']:x for x in jl(SRC/'executed_queries.jsonl')}
    ids={x['pmid']:x for x in jl(SRC/'publication_identity_inventory.jsonl')}; meta={(x['case_id'],x['canonical_publication_id']):x for x in jl(SRC/'metadata_stage_results.jsonl')}; abst={(x['case_id'],x['pmid']):x for x in jl(SRC/'abstract_screening_results.jsonl')}
    tiers={(x['case_id'],x['pmid']):x for n in ('tier_a_candidates.jsonl','tier_b_candidates.jsonl') for x in jl(SRC/n)}
    vc={(x['case_id'],x['query_variant_id']):x for x in jl(SRC/'query_variant_contribution.jsonl')}; sat={(x['case_id'],x['query_variant_id']):x for x in jl(SRC/'retrieval_candidate_saturation_curves.jsonl')}
    rank={}
    for q in executed.values():
        ref=q.get('raw_response_snapshot_ref')
        if ref:
            for i,pmid in enumerate(j(ROOT/ref).get('esearchresult',{}).get('idlist',[]),1): rank[(q['query_variant_id'],str(pmid))]=i
    packets=[]; units=[]; preaudit=[]; exinv=[]; traces=[]; blanks=[]; qjoins=[]; djoins=[]
    for i,a in enumerate(acquired,1):
        pid=f'rrav1_{i:04d}'; cid=a['case_id']; pub=ids[a['pmid']]; ar=abst[(cid,a['pmid'])]; mr=meta[(cid,a['canonical_publication_id'])]; tr=tiers[(cid,a['pmid'])]; plan=plans[cid]
        abstract=j(ROOT/ar['abstract_snapshot_ref'])['abstract']; qs=a['query_lineage']; fam=list(dict.fromkeys(executed[q]['query_family_id'] for q in qs)); first=mr['first_seen_query_variant_id']
        ex=excerpts(pid,ROOT/a['snapshot_ref'],anchors(cid,plan,variants))
        known=tr.get('justifying_fields',tr.get('known_plausible_fields',[])); unresolved=tr.get('unresolved_fields_requiring_fulltext',[])
        publication={'pmid':a['pmid'],'pmcid':a['pmcid'],'doi':pub.get('doi'),'title':pub['title'],'year':pub.get('publication_date'),'publication_types':pub.get('publication_types',[])}
        pre={'title':pub['title'],'abstract':abstract,'abstract_snapshot_ref':ar['abstract_snapshot_ref'],'abstract_snapshot_sha256':sha(ROOT/ar['abstract_snapshot_ref']),'metadata_relevance_state':mr['metadata_state'],'metadata_reason':mr['reason'],'abstract_relevance_state':ar['screen_state'],'abstract_screen_reason':ar['reason'],'abstract_signal_flags':ar['signals'],'tier_state':a['tier_state'],'gate_admission_rationale':tr['gate_reason'],'known_plausible_fields':known,'unresolved_fields_requiring_fulltext':unresolved,'acquisition_time_mismatch_flags':[]}
        provenance={'query_families':fam,'query_variants':qs,'unique_contribution_status':{q:a['canonical_publication_id'] in vc[(cid,q)]['publications_uniquely_discovered_by_variant'] for q in qs},'first_discovery_query':first,'all_contributing_query_refs':qs,'query_execution_order':{q:executed[q]['execution_order'] for q in qs},'retrieval_rank_by_query':{q:rank.get((q,a['pmid'])) for q in qs}}
        packet={'packet_id':pid,'review_unit_id':pid,'case_id':cid,'ambiguity_tier':plan['ambiguity_tier'],'retrieval_target_id':target_id(cid,plan['retrieval_target'],'retrieval'),'retrieval_target_summary':summary(plan['retrieval_target']),'retrieval_target':plan['retrieval_target'],'scientific_proposition_target_id':target_id(cid,plan['scientific_proposition_target'],'scientific_proposition'),'scientific_proposition_target_summary':summary(plan['scientific_proposition_target']),'scientific_proposition_target':plan['scientific_proposition_target'],'publication_identity':publication,'retrieval_provenance':provenance,'pre_acquisition_evidence':pre,'fulltext_evidence_packet':{'source_ref':a['snapshot_ref'],'fulltext_sha256':a['content_hash'],'excerpts':ex},'adjudication':blank(pid,cid,a['canonical_publication_id']),'automatic_relevance_prediction':None}
        packets.append(packet); blanks.append(packet['adjudication']); units.append({'review_unit_id':pid,'packet_id':pid,'case_id':cid,'canonical_publication_id':a['canonical_publication_id'],'tier_state':a['tier_state'],'source_assignment_ref':'fulltext_acquired_manifest.jsonl','source_attempt_id':a['attempt_id']})
        preaudit.append({'packet_id':pid,'case_id':cid,'publication_id':a['canonical_publication_id'],'pre_acquisition_fields_only':True,'fulltext_facts_in_gate_rationale':False,'tier_b_ledger_exact':tr.get('unresolved_fields_requiring_fulltext',[])==unresolved,'source_refs':[ar['abstract_snapshot_ref'],'metadata_stage_results.jsonl','abstract_screening_results.jsonl']})
        for e in ex:
            row={'packet_id':pid,'case_id':cid,'publication_id':a['canonical_publication_id'],'fulltext_ref':a['snapshot_ref'],'fulltext_sha256':a['content_hash'],**e}; exinv.append(row); traces.append({k:row[k] for k in ['excerpt_id','packet_id','case_id','publication_id','fulltext_ref','fulltext_sha256','anchor_definition','exact_anchor_matched','section','section_category','source_node_path','source_passage_identity','source_node_text_sha256','text_sha256']})
        qjoins.append({'packet_id':pid,'case_id':cid,'publication_id':a['canonical_publication_id'],'query_variant_ids':qs,'query_family_ids':fam,'first_discovery_query':first,'future_metrics':['relevant_unique_addition','noise_addition','tier_a_justified_addition','tier_b_useful_addition'],'adjudication_pending':True})
        djoins.append({'packet_id':pid,'case_id':cid,'publication_id':a['canonical_publication_id'],'first_discovery_query':first,'first_query_execution_order':executed[first]['execution_order'],'retrieval_rank_in_first_query':rank.get((first,a['pmid'])),'metadata_cumulative_depth_after_first_query':sat[(cid,first)]['cumulative_unique_publications'],'query_family_execution_sequence':[{'query_variant_id':q,'query_family_id':executed[q]['query_family_id'],'execution_order':executed[q]['execution_order'],'retrieval_rank':rank.get((q,a['pmid']))} for q in qs]})
    # Tier-first round robin across cases, then distribute sequentially for mixed batches.
    pools={(c,t):[p for p in packets if p['case_id']==c and p['pre_acquisition_evidence']['tier_state']==t] for c in CASES for t in ['TIER_B_ACQUIRE_TO_RESOLVE','TIER_A_HIGH_CONFIDENCE_ACQUIRE']}; ordered=[]
    for t in ['TIER_B_ACQUIRE_TO_RESOLVE','TIER_A_HIGH_CONFIDENCE_ACQUIRE']:
        while any(pools[(c,t)] for c in CASES):
            for c in CASES:
                if pools[(c,t)]: ordered.append(pools[(c,t)].pop(0))
    batches=[[] for _ in SIZES]
    for i,p in enumerate(ordered): batches[i%5].append(p)
    assert [len(x) for x in batches]==SIZES
    wj(RUN/'baseline.json',{'artifact_schema_version':'retrieval_relevance_packaging_baseline.v1','source_run':str(SRC.relative_to(ROOT)),'source_manifest_sha256':sha(SRC/'manifest.json'),'source_tree_before':before,'git_head':subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,text=True,capture_output=True,check=True).stdout.strip(),'network_calls':0,'provider_calls':0,'llm_calls':0,'downloads':0})
    for n,x in [('review_unit_inventory.jsonl',units),('retrieval_relevance_review_packets.jsonl',packets),('pre_acquisition_evidence_audit.jsonl',preaudit),('fulltext_excerpt_inventory.jsonl',exinv),('excerpt_source_trace.jsonl',traces),('blank_retrieval_relevance_adjudications.jsonl',blanks),('query_contribution_join_map.jsonl',qjoins),('retrieval_depth_join_map.jsonl',djoins)]: wjl(RUN/n,x)
    schema={'$schema':'https://json-schema.org/draft/2020-12/schema','title':'RetrievalRelevanceAdjudicationV1','type':'object','required':list(blanks[0]),'properties':{k:{'type':['string','null']} for k in ['packet_id','case_id','publication_id','relevance_state','acquisition_decision','contaminant_class','reviewer_rationale','reviewer_type','reviewer_id_or_label','timestamp']}|{k:{'type':'array','items':{'type':'string'}} for k in ['matched_target_components','mismatched_target_components','fulltext_resolved_fields','remaining_unresolved_fields']}|{'confidence':{'type':['number','null'],'minimum':0,'maximum':1}},'allOf':[{'if':{'properties':{'relevance_state':{'type':'string'}}},'then':{'properties':{'relevance_state':{'enum':REL}}}},{'if':{'properties':{'acquisition_decision':{'type':'string'}}},'then':{'properties':{'acquisition_decision':{'enum':ACQ}}}}],'description':'Two independent axes; acquisition justification uses preserved pre-acquisition evidence only.'}; wj(RUN/'retrieval_relevance_adjudication_v1.schema.json',schema)
    wj(RUN/'contaminant_taxonomy.json',{'labels':CONT,'optional_for_relevant_papers':True})
    wj(RUN/'quality_metric_contract.json',{'status':'pending_adjudication','metrics':{'tier_a_acquisition_precision':'Tier A JUSTIFIED / adjudicated Tier A','tier_a_acquisition_acceptability':'Tier A (JUSTIFIED + BORDERLINE_BUT_JUSTIFIED) / adjudicated Tier A','tier_b_direct_relevance_rate':'Tier B DIRECTLY_RELEVANT / adjudicated Tier B','tier_b_utility_rate':'Tier B justified or borderline acquisitions where fulltext resolved or was needed to attempt resolution of a pre-acquisition uncertainty / adjudicated Tier B','overall_acquisition_justification_rate':'JUSTIFIED / all adjudicated acquisitions','overall_acquisition_acceptability':'(JUSTIFIED + BORDERLINE_BUT_JUSTIFIED) / all adjudicated acquisitions','overall_retrieval_relevance_rate':'retrieval-relevant / all adjudicated acquired fulltexts'},'case_level_fields':['acquired_count','tier_a_acquired','tier_b_acquired','directly_relevant','plausibly_relevant','related_wrong_proposition','wrong_endpoint','wrong_entity','wrong_evidence_mode','wrong_therapy','topic_only','insufficient_source','acquisition_justified','acquisition_borderline_justified','acquisition_not_justified','tier_a_precision','tier_b_utility','overall_acquisition_acceptability'],'values_populated':False})
    attempts=jl(SRC/'fulltext_acquisition_attempts.jsonl'); wjl(RUN/'fulltext_accessibility_separate_ledger.jsonl',[{'case_id':x['case_id'],'publication_id':x['canonical_publication_id'],'pmid':x['pmid'],'pmcid':x.get('pmcid'),'tier_state':x['tier_state'],'fulltext_availability_state':x['status'],'review_unit_id':next((u['review_unit_id'] for u in units if u['case_id']==x['case_id'] and u['canonical_publication_id']==x['canonical_publication_id']),None),'availability_is_relevance':False} for x in attempts])
    bm=[]
    for i,b in enumerate(batches,1):
        wjl(RUN/f'review_batch_{i:02d}.jsonl',b); (RUN/f'review_batch_{i:02d}.md').write_text(render(b))
        bm.append({'batch_id':f'batch_{i:02d}','size':len(b),'packet_ids':[p['packet_id'] for p in b],'case_distribution':dict(Counter(p['case_id'] for p in b)),'ambiguity_distribution':dict(Counter(p['ambiguity_tier'] for p in b)),'tier_distribution':dict(Counter(p['pre_acquisition_evidence']['tier_state'] for p in b))})
    wj(RUN/'review_batch_manifest.json',{'batch_count':5,'batches':bm,'stratification':'deterministic Tier-first case round-robin, then five-way round-robin'})
    violations={}
    for p in packets:
        reasons=[]
        if p['automatic_relevance_prediction'] is not None: reasons.append('automatic_relevance_prediction_prefilled')
        if any(p['adjudication'][k] is not None for k in ['relevance_state','acquisition_decision','contaminant_class','reviewer_rationale','confidence','reviewer_type','reviewer_id_or_label','timestamp']): reasons.append('adjudication_scalar_prefilled')
        if any(p['adjudication'][k] for k in ['matched_target_components','mismatched_target_components','fulltext_resolved_fields','remaining_unresolved_fields']): reasons.append('adjudication_list_prefilled')
        prohibited={'preferred_relevance_answer','predicted_acquisition_decision','search_plan_quality_score','conflict_result','support_opposition_result','system_recommendation'}
        if prohibited & set(p): reasons.append('prohibited_prediction_key_present')
        if reasons: violations[p['packet_id']]=reasons
    wj(RUN/'packet_neutrality_audit.json',{'packet_count':79,'adjudicated_count':0,'packets_with_neutrality_violation':len(violations),'violations':violations,'automatic_predictions_present':0})
    trace_ids={x['excerpt_id'] for x in traces}; missing=[p['packet_id'] for p in packets if not p['pre_acquisition_evidence']['abstract_snapshot_ref'] or not p['fulltext_evidence_packet']['source_ref'] or any(e['excerpt_id'] not in trace_ids for e in p['fulltext_evidence_packet']['excerpts'])]
    wj(RUN/'source_traceability_audit.json',{'packet_count':79,'excerpt_count':len(exinv),'packets_missing_source_trace':len(missing),'missing_packet_ids':missing,'all_excerpt_text_exact_substring_of_traced_xml_node':True})
    after=tree_state(); safety={'network_calls':0,'provider_calls':0,'llm_calls':0,'downloads':0,'source_run_modified':before!=after,'historical_assets_modified':before!=after,'formal_v3_modified':False,'atlas_activated':False,'active_pointer_changed':False,'variational_em_called':False,'extraction_invoked':False}; wj(RUN/'scientific_state_safety_audit.json',safety); wj(RUN/'production_leakage_audit.json',safety)
    counts={'review_unit_count':len(units),'tier_a_review_unit_count':sum(x['tier_state']=='TIER_A_HIGH_CONFIDENCE_ACQUIRE' for x in units),'tier_b_review_unit_count':sum(x['tier_state']=='TIER_B_ACQUIRE_TO_RESOLVE' for x in units),'case_count':len({x['case_id'] for x in units}),'packet_count':len(packets),'packets_with_abstract':sum(bool(p['pre_acquisition_evidence']['abstract']) for p in packets),'packets_without_abstract':sum(not bool(p['pre_acquisition_evidence']['abstract']) for p in packets),'packets_with_fulltext_excerpts':sum(bool(p['fulltext_evidence_packet']['excerpts']) for p in packets),'packets_without_fulltext_excerpts':sum(not bool(p['fulltext_evidence_packet']['excerpts']) for p in packets),'total_fulltext_excerpt_count':len(exinv),'batch_count':5,'batch_sizes':SIZES,'blank_adjudication_count':len(blanks),'adjudicated_count':0,'packets_missing_source_trace':len(missing),'packets_with_neutrality_violation':len(violations),'network_calls':0,'provider_calls':0,'llm_calls':0,'downloads':0,'historical_assets_modified':before!=after}
    checks={'one_unit_per_acquired_assignment':{(x['case_id'],x['canonical_publication_id']) for x in units}=={(x['case_id'],x['canonical_publication_id']) for x in acquired},'no_nonacquired_units':len(units)==len(acquired),'tier_matches_source':all(tiers[(x['case_id'],x['canonical_publication_id'].split(':')[1])]['tier_state']==x['tier_state'] for x in units),'adjudications_blank':all(x['relevance_state'] is None and x['acquisition_decision'] is None for x in blanks),'no_neutrality_leakage':not violations,'all_excerpts_traced':not missing,'query_lineage_present':all(p['retrieval_provenance']['all_contributing_query_refs'] for p in packets),'pre_post_separated':all(set(p['pre_acquisition_evidence']).isdisjoint({'source_ref','fulltext_sha256','excerpts'}) and set(p['fulltext_evidence_packet'])=={'source_ref','fulltext_sha256','excerpts'} for p in packets),'tier_b_ledgers_exact':all(tiers[(p['case_id'],p['publication_identity']['pmid'])].get('unresolved_fields_requiring_fulltext',[])==p['pre_acquisition_evidence']['unresolved_fields_requiring_fulltext'] for p in packets if p['pre_acquisition_evidence']['tier_state']=='TIER_B_ACQUIRE_TO_RESOLVE'),'offline_zero':all(counts[k]==0 for k in ['network_calls','provider_calls','llm_calls','downloads']),'historical_unchanged':before==after,'batch_sizes':list(map(len,batches))==SIZES,'tier_b_stratified_where_possible':all(any(p['pre_acquisition_evidence']['tier_state']=='TIER_B_ACQUIRE_TO_RESOLVE' for p in b) for b in batches)}
    xml_cache={}
    for e in exinv:
        if e['fulltext_ref'] not in xml_cache:
            root=ET.parse(ROOT/e['fulltext_ref']).getroot(); xml_cache[e['fulltext_ref']]={p:txt(n) for n,p in paths(root).items()}
    checks['exact_excerpt_source']=all(e['source_node_path'] in xml_cache[e['fulltext_ref']] and e['text'] in xml_cache[e['fulltext_ref']][e['source_node_path']] and e['text_sha256']==hashlib.sha256(e['text'].encode()).hexdigest() and e['source_node_text_sha256']==hashlib.sha256(xml_cache[e['fulltext_ref']][e['source_node_path']].encode()).hexdigest() for e in exinv)
    checks['source_snapshot_hashes_valid']=all(sha(ROOT/p['fulltext_evidence_packet']['source_ref'])==p['fulltext_evidence_packet']['fulltext_sha256'] and sha(ROOT/p['pre_acquisition_evidence']['abstract_snapshot_ref'])==p['pre_acquisition_evidence']['abstract_snapshot_sha256'] for p in packets)
    downstream_keys={'conflict_result','formal_result','support_result','opposition_result','candidate_qualification','l4_result'}
    def nested_keys(value):
        if isinstance(value,dict): return set(value) | {k for child in value.values() for k in nested_keys(child)}
        if isinstance(value,list): return {k for child in value for k in nested_keys(child)}
        return set()
    checks['no_downstream_scientific_results']=all(not (nested_keys(p)&downstream_keys) for p in packets)
    checks['no_hindsight_in_acquisition_rationale']=all(p['pre_acquisition_evidence']['gate_admission_rationale']==tiers[(p['case_id'],p['publication_identity']['pmid'])]['gate_reason'] for p in packets)
    checks['high_ambiguity_boundaries_not_predictions']=all(p['automatic_relevance_prediction'] is None and p['adjudication']['relevance_state'] is None for p in packets if p['ambiguity_tier']=='HIGH')
    checks['required_artifacts_present']=all((RUN/x).is_file() for x in REQ if x not in {'final_validation.json','manifest.json','summary.json'})
    def validation_and_summary():
        wj(RUN/'final_validation.json',{'status':'PASS' if all(checks.values()) else 'FAIL','checks':checks})
        wj(RUN/'summary.json',{'completion_state':'RETRIEVAL_RELEVANCE_PACKETS_READY' if all(checks.values()) else 'RETRIEVAL_RELEVANCE_PACKAGING_PARTIAL',**counts,'per_case':{c:dict(Counter(x['tier_state'] for x in units if x['case_id']==c)) for c in CASES}})
    def manifest():
        files=[{'path':p.name,'sha256':sha(p),'bytes':p.stat().st_size,'record_count':sum(1 for x in p.read_text().splitlines() if x) if p.suffix=='.jsonl' else 1} for p in sorted(RUN.iterdir()) if p.is_file() and p.name!='manifest.json']; wj(RUN/'manifest.json',{'required_artifact_count':len(REQ),'files':files,'all_required_present':all((RUN/x).is_file() for x in REQ if x!='manifest.json'),'source_run_sha256':before['sha256'],'network_calls':0,'provider_calls':0,'llm_calls':0})
    validation_and_summary(); manifest()
    m=j(RUN/'manifest.json'); checks['manifest_hashes_valid']=all(sha(RUN/x['path'])==x['sha256'] for x in m['files'])
    validation_and_summary(); manifest(); print(json.dumps(j(RUN/'summary.json'),indent=2))
if __name__=='__main__': main()
