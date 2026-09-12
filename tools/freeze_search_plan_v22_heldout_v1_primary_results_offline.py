#!/usr/bin/env python3
"""Merge frozen metadata and PASS A/B by packet_id; freeze without metrics."""
from collections import Counter
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT/'runs/20260909_search_plan_v22_heldout_v1_case_freeze_offline'
CORPUS = ROOT/'runs/20260910_search_plan_v22_heldout_v1_neutral_review_freeze_offline'
BLINDED = ROOT/'runs/20260910_search_plan_v22_heldout_v1_blinded_adjudication_views_offline'
PASS_A = ROOT/'runs/20260910_search_plan_v22_heldout_v1_pass_a_acquisition_adjudication_freeze_offline'
PASS_B = ROOT/'runs/20260912_search_plan_v22_heldout_v1_pass_b_relevance_adjudication_freeze_offline'
WORKSPACE = ROOT/'pass_b_primary_evaluator_workspace'
RUN = ROOT/'runs/20260912_search_plan_v22_heldout_v1_primary_results_freeze_offline'
HASHES = {
 'heldout_v1_protocol_sha256':'2aac90361272de64eb055099602ae68e696c760628fec3835c0f29eca63ca127',
 'heldout_v1_review_corpus_sha256':'f2cfe4f1657667a66b18d3123e82d76cc4bf1af9da2863ac6b10f9efc3d092fb',
 'heldout_v1_blinded_adjudication_views_sha256':'2940e058b63df5dc02fb6ed07d970f651a74f9a000c9b6784affe3e6fac1dc0e',
 'heldout_v1_pass_a_acquisition_adjudications_sha256':'333fc6f20bab33b21387f2453905c2c9c11d92797177688a9e75cc2bab2e52df',
 'heldout_v1_pass_b_relevance_adjudications_sha256':'b3d4a5a93572666fa8a0986e4fddad13641969f9b874eac08a48c435f48ee465'}
A_FIELDS=['acquisition_decision','rationale','confidence','reviewer_type']
B_FIELDS=['relevance_state','matched_target_components','mismatched_target_components',
 'fulltext_resolved_fields','remaining_unresolved_fields','contaminant_class','rationale','confidence','reviewer_type']
ZERO_CALLS={k:0 for k in ['network_calls','provider_calls','llm_calls','downloads','scientific_extraction_calls','new_adjudication_calls']}
ZERO_MODS={k:0 for k in ['case_modifications','target_modifications','query_modifications','gate_modifications',
 'budget_modifications','sample_modifications','batch_assignment_modifications','pass_a_label_modifications','pass_b_label_modifications']}
REQUIRED=['heldout_v1_primary_results.jsonl','primary_results_identity_validation.json',
 'primary_results_schema_validation.json','primary_results_merge_validation.json','root_hash_verification.json',
 'pass_a_import_verification.json','pass_b_import_verification.json','frozen_packet_metadata_verification.json',
 'scientific_state_safety_audit.json','freeze_manifest.json','validation.json','summary.json']

def digest(data): return hashlib.sha256(data).hexdigest()
def sha(path): return digest(Path(path).read_bytes())
def canon(value): return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()
def pretty(value): return (json.dumps(value,indent=2,sort_keys=True,ensure_ascii=False)+'\n').encode()
def readj(path): return json.loads(Path(path).read_bytes())
def readl(path): return [json.loads(x) for x in Path(path).read_bytes().splitlines() if x.strip()]
def require(value,message):
 if not value: raise RuntimeError(message)

def aggregate_root(base,field,expected):
 m=readj(base/'freeze_manifest.json'); pairs=[]
 for row in m['components']:
  actual=sha(base/row['path']); require(actual==row['sha256'],f'component mismatch: {row["path"]}');pairs.append((row['path'],actual))
 actual=digest(canon(pairs));require(actual==m[field]==expected,f'root mismatch: {field}')
 return {'field':field,'actual':actual,'expected':expected,'match':True}

def corpus_root(base,field,expected):
 m=readj(base/'freeze_manifest.json'); ref=base/m['corpus'];actual=sha(ref)
 require(actual==m[field]==expected,f'corpus root mismatch: {field}')
 return {'field':field,'actual':actual,'expected':expected,'match':True,'corpus_ref':str(ref.relative_to(ROOT))}

def protected():
 paths=[p for base in [PROTOCOL,CORPUS,BLINDED,PASS_A,PASS_B,WORKSPACE] for p in sorted(base.rglob('*')) if p.is_file()]
 return {str(p.relative_to(ROOT)):sha(p) for p in paths}

def identities(packets,a,b):
 ids=[[x['packet_id'] for x in rows] for rows in [packets,a,b]]; counters=list(map(Counter,ids)); canonical=counters[0]
 missing_a=canonical-counters[1];missing_b=canonical-counters[2];extra_a=counters[1]-canonical;extra_b=counters[2]-canonical
 dup={x for c in counters for x,n in c.items() if n>1}
 result={'canonical_packet_count':len(packets),'pass_a_record_count':len(a),'pass_b_record_count':len(b),
  'canonical_unique_packet_ids':len(set(ids[0])),'pass_a_unique_packet_ids':len(set(ids[1])),
  'pass_b_unique_packet_ids':len(set(ids[2])),'missing_pass_a':sum(missing_a.values()),
  'missing_pass_b':sum(missing_b.values()),'extra_pass_a':sum(extra_a.values()),'extra_pass_b':sum(extra_b.values()),
  'duplicate_packet_ids':len(dup),'pass_a_packet_identity_bijection':counters[1]==canonical,
  'pass_b_packet_identity_bijection':counters[2]==canonical,'authoritative_join_key':'packet_id'}
 require(all(result[k]==70 for k in ['canonical_packet_count','pass_a_record_count','pass_b_record_count',
  'canonical_unique_packet_ids','pass_a_unique_packet_ids','pass_b_unique_packet_ids']),'input count mismatch')
 require(all(result[k]==0 for k in ['missing_pass_a','missing_pass_b','extra_pass_a','extra_pass_b','duplicate_packet_ids']),
  'input identity mismatch')
 require(result['pass_a_packet_identity_bijection'] and result['pass_b_packet_identity_bijection'],'input bijection failed')
 return result

def merge_record(packet,a,b):
 return {'artifact_schema_version':'HeldoutV1PrimaryResultV1','packet_id':packet['packet_id'],
  'case_id':packet['case_id'],'ambiguity':packet['ambiguity'],'tier':packet['tier'],
  'frozen_gate_states':packet['pre_acquisition_gate_states'],
  'frozen_acquisition_metadata':{'metadata_depth':packet['metadata_depth'],
   'query_family_variant_provenance':packet['query_family_variant_provenance'],
   'fields_expected_to_resolve':packet['fields_expected_to_resolve'],'fulltext_ref':packet['fulltext_ref'],
   'fulltext_sha256':packet['fulltext_sha256']},'scientific_target':packet['scientific_target'],
  'retrieval_target':packet['retrieval_target'],'source_identity':packet['publication_identity'],
  'pass_a':{k:a[k] for k in A_FIELDS},'pass_b':{k:b[k] for k in B_FIELDS},
  'canonical_packet_sha256':digest(canon(packet))}

def generate():
 roots=[aggregate_root(PROTOCOL,'heldout_v1_protocol_sha256',HASHES['heldout_v1_protocol_sha256']),
  aggregate_root(CORPUS,'heldout_v1_review_corpus_sha256',HASHES['heldout_v1_review_corpus_sha256']),
  aggregate_root(BLINDED,'heldout_v1_blinded_adjudication_views_sha256',HASHES['heldout_v1_blinded_adjudication_views_sha256']),
  corpus_root(PASS_A,'heldout_v1_pass_a_acquisition_adjudications_sha256',HASHES['heldout_v1_pass_a_acquisition_adjudications_sha256']),
  corpus_root(PASS_B,'heldout_v1_pass_b_relevance_adjudications_sha256',HASHES['heldout_v1_pass_b_relevance_adjudications_sha256'])]
 before=protected();packets=readl(CORPUS/'frozen_neutral_review_packets.jsonl')
 a=readl(PASS_A/'pass_a_acquisition_adjudications.jsonl');b=readl(PASS_B/'pass_b_relevance_adjudications.jsonl')
 ident=identities(packets,a,b); amap={x['packet_id']:x for x in a};bmap={x['packet_id']:x for x in b}
 merged=[merge_record(p,amap[p['packet_id']],bmap[p['packet_id']]) for p in packets]
 pids=[p['packet_id'] for p in packets];mids=[r['packet_id'] for r in merged]
 require(mids==pids and len(mids)==len(set(mids))==70,'merged identity/order mismatch')
 body=b''.join(canon(r)+b'\n' for r in merged);require(readl_bytes(body)==merged,'serialization changed values')
 primary=digest(body);all_hashes={**HASHES,'heldout_v1_primary_results_sha256':primary}
 outputs={'heldout_v1_primary_results.jsonl':body}
 def put(name,value): outputs[name]=pretty(value)
 identity={**ident,'merged_record_count':70,'merged_unique_packet_ids':70,'merged_packet_identity_bijection':True}
 put('primary_results_identity_validation.json',identity)
 a_exact=all(r['pass_a']=={k:amap[r['packet_id']][k] for k in A_FIELDS} for r in merged)
 b_exact=all(r['pass_b']=={k:bmap[r['packet_id']][k] for k in B_FIELDS} for r in merged)
 meta_exact=all(r['case_id']==p['case_id'] and r['ambiguity']==p['ambiguity'] and r['tier']==p['tier'] and
  r['frozen_gate_states']==p['pre_acquisition_gate_states'] and r['scientific_target']==p['scientific_target'] and
  r['retrieval_target']==p['retrieval_target'] and r['source_identity']==p['publication_identity'] and
  r['canonical_packet_sha256']==digest(canon(p)) for r,p in zip(merged,packets))
 put('primary_results_schema_validation.json',{'status':'PASS','record_count':70,
  'artifact_schema_version':'HeldoutV1PrimaryResultV1','required_top_level_fields':list(merged[0]),
  'pass_a_fields':A_FIELDS,'pass_b_fields':B_FIELDS,'all_records_structurally_valid':all(list(r)==list(merged[0]) for r in merged),
  'gate_outcomes_recomputed':False,'scientific_fields_transformed':False,'metrics_fields_populated':False})
 put('primary_results_merge_validation.json',{'status':'PASS','join_key':'packet_id',
  'joined_by_other_identity':False,'canonical_order_preserved':mids==pids,'pass_a_fields_preserved_exactly':a_exact,
  'pass_b_fields_preserved_exactly':b_exact,'frozen_packet_metadata_preserved_exactly':meta_exact,
  'merged_packet_identity_bijection':True,'scientific_relabeling_performed':False,'gate_states_recomputed':False,
  'metrics_calculated':False})
 put('root_hash_verification.json',{'status':'PASS','roots':roots,'all_five_upstream_hashes_verified':True,**HASHES})
 put('pass_a_import_verification.json',{'status':'PASS','source_sha256':sha(PASS_A/'pass_a_acquisition_adjudications.jsonl'),
  'frozen_root_sha256':HASHES['heldout_v1_pass_a_acquisition_adjudications_sha256'],'record_count':70,
  'unique_packet_ids':70,'packet_identity_bijection':True,'fields_preserved_exactly':a_exact,'label_modifications':0})
 put('pass_b_import_verification.json',{'status':'PASS','source_sha256':sha(PASS_B/'pass_b_relevance_adjudications.jsonl'),
  'frozen_root_sha256':HASHES['heldout_v1_pass_b_relevance_adjudications_sha256'],'record_count':70,
  'unique_packet_ids':70,'packet_identity_bijection':True,'fields_preserved_exactly':b_exact,'label_modifications':0})
 mapping={'packet_id':'packet_id','case_id':'case_id','ambiguity':'ambiguity','tier':'tier',
  'pre_acquisition_gate_states':'frozen_gate_states','publication_identity':'source_identity',
  'scientific_target':'scientific_target','retrieval_target':'retrieval_target',
  **{k:f'frozen_acquisition_metadata.{k}' for k in ['metadata_depth','query_family_variant_provenance',
    'fields_expected_to_resolve','fulltext_ref','fulltext_sha256']}}
 put('frozen_packet_metadata_verification.json',{'status':'PASS','source_sha256':sha(CORPUS/'frozen_neutral_review_packets.jsonl'),
  'record_count':70,'metadata_projection_preserved_exactly':meta_exact,'preserved_field_mapping':mapping,
  'gate_outcomes_derived_or_recomputed':False,'targets_modified':False,'sample_membership_modified':False})
 after=protected();require(before==after,'frozen source changed')
 put('scientific_state_safety_audit.json',{**ZERO_CALLS,**ZERO_MODS,'offline_only':True,
  'canonical_source_modified':False,'review_corpus_modified':False,'blinded_views_modified':False,
  'pass_a_frozen_corpus_modified':False,'pass_b_frozen_corpus_modified':False,'evaluator_workspace_modified':False,
  'historical_assets_modified':False,'git_mutation_invoked':False,'protected_hashes_before':before,'protected_hashes_after':after})
 put('freeze_manifest.json',{**all_hashes,'hash_algorithm':'sha256(exact canonical ordered UTF-8 JSONL bytes)',
  'canonical_serialization':'sort_keys=true; ensure_ascii=false; compact separators; LF after each record',
  'corpus':'heldout_v1_primary_results.jsonl','record_count':70,'ordering':'exact frozen review-corpus packet order',
  'join_key':'packet_id','primary_results_frozen':True,'metrics_embargo_active':True,
  'future_metrics_run_must_verify_all_six_hashes':True,'future_metrics_required_hashes':list(all_hashes)})
 summary={'status':'completed',**all_hashes,**identity,**ZERO_CALLS,**ZERO_MODS,'canonical_order_preserved':True,
  'heldout_metrics_calculated':False,'performance_distribution_reported':False,'heuristics_evaluated':False,
  'canonical_source_modified':False,'review_corpus_modified':False,'blinded_views_modified':False,
  'pass_a_frozen_corpus_modified':False,'pass_b_frozen_corpus_modified':False,'evaluator_workspace_modified':False,
  'historical_assets_modified':False,'primary_results_frozen':True}
 put('summary.json',summary)
 checks={'five_upstream_roots_verified':True,'all_structural_counts_70':True,'identity_bijections_valid':True,
  'canonical_order_preserved':mids==pids,'pass_a_fields_exact':a_exact,'pass_b_fields_exact':b_exact,
  'frozen_packet_metadata_exact':meta_exact,'primary_results_hash_valid':digest(body)==primary,
  'no_scientific_transformations':True,'metrics_embargo_active':True,'historical_assets_unchanged':before==after,
  'offline_all_calls_zero':True,'required_payloads_present':all(x in outputs for x in REQUIRED if x not in ['validation.json','summary.json'])}
 put('validation.json',{'status':'PASS','checks':checks})
 return outputs

def readl_bytes(data): return [json.loads(x) for x in data.splitlines() if x.strip()]

def main():
 outputs=generate()
 if RUN.exists():
  require(RUN.is_dir() and not RUN.is_symlink(),'invalid existing output')
  require({p.name for p in RUN.iterdir()}==set(outputs),'existing output membership differs')
  require(all((RUN/n).read_bytes()==d for n,d in outputs.items()),'existing output differs; no overwrite')
 else:
  RUN.mkdir()
  for name,data in outputs.items():
   with (RUN/name).open('xb') as handle: handle.write(data)
 print(outputs['summary.json'].decode())

if __name__=='__main__': main()
