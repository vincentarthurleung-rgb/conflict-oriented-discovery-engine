"""Lossless provisional tables alongside existing case_bundle_manifest_v1.

No replacement scientific schema: native V3, Core and AI reviews are preserved
unchanged. New files index those contracts and their provenance. Default export
is restricted internal data; no full text or redistributable release is assumed.
"""
from pathlib import Path
import hashlib,json
from code_engine.discovery.ai_review_shadow import content_hash
from code_engine.system_b.annotation_schemas.registry import canonical_json
from code_engine.discovery.ai_review_shadow import ShadowAuthority

TABLES={'scientific_inclusion':'Versioned paper/experiment/observation applicability decisions, exact source evidence and unresolved scope; no Core authority',
 'scientific_inclusion_coverage':'Separate retrieval/access/inclusion/extraction/downstream coverage; no publication recall',
 'semantic_intake':'Frozen question-bound intake reuse or explicit deterministic degraded status; no new model execution',
 'linkage_stage_inputs':'Original V3 response lineage, exact source spans, scope/applicability assessments and unsigned candidate request',
 'linkage_stage_outcomes':'Original candidate responses, structural acceptance/rejection, materialization refusal and native versus hypothetical V2',
 'scientific_stage_completion':'Explicit executed/skipped/failed stage status; never full L0–L6 certification',
 'extraction_observation_instances':'Unmodified per-window hydrated observation instances; overlap aliases retained without counting duplicate scientific records','fulltext_windows':'Complete source window plans, exact coordinates, overlap and per-window pending/failed/processed states; not scientific completeness','observation_window_provenance':'Exact coordinate deduplication and window occurrence provenance', 'cases':'Case identity, question, scope, terminal and partial-work status',
 'search_queries':'Frozen queries and pagination coverage', 'papers':'Included/excluded/unavailable/failed sources with exact identities and case links',
 'builder_quality':'Source-bound propositions and Quality decisions; deterministic replay labeled',
 'experimental_observations':'Unmodified ExperimentalObservationV3', 'experimental_core':'Unmodified Experimental Core records, including factors, comparators, measurements, results and linkages',
 'evidence_index':'Exact source spans/offsets/hashes, access-controlled original text references',
 'evidence_projection':'Unmodified reviewable projected observations, preserving measured properties and authority exclusions',
 'model_execution':'Exact model request/result/usage references and zero-charge reuse provenance',
 'entity_normalization':'Normalized and explicitly unresolved reviewable entities',
 'ai_scientific_reviews':'Unmodified AI field reviews, no scientific authorization',
 'alignment_context':'Existing Shadow pair alignment, context and comparability',
 'contradictions':'Source-supported provisional candidates only', 'hypotheses':'Existing justified hypotheses and falsifiable tests only',
 'failures_uncertainty':'Missing Core, errors, skipped/blocked stages and limitations',
 'workflow_fixture_reviews':'Explicit software-workflow annotations, excluded from human scientific review data',
 'human_reviews':'Actual exported Atlas decisions if explicitly supplied; empty is not an approval'}

def export_attempt_dataset(manifest,case_dir,output,*,pairs=(),human_reviews=()):
 case_dir=Path(case_dir).resolve();output=Path(output)
 if output.exists() and any(output.iterdir()):raise ValueError('immutable_dataset_revision_exists; choose a new output directory')
 output.mkdir(parents=True,exist_ok=True);cid=manifest['case_id'];tables={k:[] for k in TABLES};tables['cases']=[{**{k:v for k,v in manifest.items() if k in ('case_id','question','scope','evidence_mode','input_sha256','historical_root','sources','terminal_state','terminal_reason','literature_coverage','fulltext_coverage','has_deterministic_model_stubs')},'stages':[x for x in manifest['stages'] if x['stage'] not in ('dataset_export','atlas_export')],'snapshot_boundary':'before_dataset_export'}]
 aliases=set()
 def read(p):return json.loads(p.read_text())
 for s in manifest.get('sources',[]):tables['papers'].append(s)
 if manifest.get('literature_coverage'):
  cov=manifest['literature_coverage'];tables['search_queries']=[{'query':q,'pages':[p for p in cov.get('pages',[]) if p['query_id']==q['query_id']],'inclusion_criteria':cov.get('inclusion_criteria',[]),'exclusion_criteria':cov.get('exclusion_criteria',[])} for q in cov.get('queries',[])];tables['papers'].extend(cov.get('papers',[]))
 for p in sorted(case_dir.rglob('*.json')):
  if output in p.parents:continue
  name=p.name
  if name=='scientific_inclusion_final.json':tables['scientific_inclusion'].extend(read(p)['rows'])
  elif name=='scientific_inclusion_coverage.json':tables['scientific_inclusion_coverage'].append(read(p))
  elif name=='semantic_intake_trace.json':tables['semantic_intake'].append(read(p))
  elif name.endswith('_linkage_input.json'):
   d=read(p);tables['linkage_stage_inputs'].append(d);tables['evidence_index'].extend({'source':d['input']['source_identity'],'span':span,'lane':'linkage_sidecar_only'} for span in d['additional_evidence'])
  elif name.endswith('_linkage_outcome.json'):tables['linkage_stage_outcomes'].append(read(p))
  elif name=='scientific_stage_completion.json':tables['scientific_stage_completion'].append(read(p))
  elif name.endswith(('_builder.json','_quality.json')):tables['builder_quality'].append({'artifact':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'record':read(p)})
  elif name.endswith(('_source_window_plan.json','_source_window_coverage.json')):tables['fulltext_windows'].append(read(p))
  elif name.endswith('_observation_window_provenance.json'):
   row=read(p);tables['observation_window_provenance'].append(row);aliases.update(x['observation_id'] for x in row.get('observation_occurrences',[]))
  elif name=='core.json':
   d=read(p);tables['experimental_observations'].append(d['ExperimentalObservationV3']);tables['experimental_core'].append(d['ExperimentalCore'])
  elif name=='packet.json':
   d=read(p);tables['evidence_index'].extend({'source':d['source'],'span':s} for s in d['evidence_spans'])
  elif name.endswith('_review.json'):tables['ai_scientific_reviews'].append(read(p))
  elif name=='normalized_builder_claims.json':tables['entity_normalization'].extend(read(p))
  elif name.endswith('_incomplete_experimental_records.json'):
   incomplete=read(p);tables['failures_uncertainty'].append(incomplete);tables['extraction_observation_instances'].extend((incomplete.get('output') or {}).get('incomplete',{}).get('formal_v3',{}).get('experimental_observations',[]))
  elif name=='projected_native_observations.json':tables['evidence_projection'].extend(read(p))
  elif name.endswith(('_model_receipt.json','_reuse.json')):tables['model_execution'].append(read(p))
 observations={x['observation_id']:x for x in tables['experimental_observations']}
 for row in tables['extraction_observation_instances']:
  oid=row['observation_id']
  if oid in aliases and oid not in observations:continue
  if oid in observations and observations[oid]!=row:raise ValueError('same_observation_ID_has_different_native_payload')
  observations.setdefault(oid,row)
 tables['experimental_observations']=list(observations.values())
 for s in manifest['stages']:
  if s['status'] in ('failed','blocked','skipped'):tables['failures_uncertainty'].append(s)
 for pair in pairs:
  tables['alignment_context'].append(pair['alignment'])
  if pair['terminal_state']=='PROVISIONAL_CONTRADICTION':tables['contradictions'].append(pair['alignment'])
  tables['hypotheses'].extend(pair['alignment']['hypotheses'])
 for review in human_reviews:
  target='workflow_fixture_reviews' if 'SYNTHETIC' in str(review.get('notes','')).upper() else 'human_reviews'
  tables[target].append(review)
 files={}
 for name,rows in tables.items():
  p=output/(name+'.jsonl');p.write_text(''.join(canonical_json({'case_id':cid,'authority_label':ShadowAuthority().authority_label,'record':row})+'\n' for row in rows))
  files[p.name]={'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'rows':len(rows),'description':TABLES[name]}
 dictionary={'schema_version':'case_dataset_dictionary_v1','envelope':{'case_id':'Exact parent case; not a paper-level canonical ID','authority_label':'AI_PROVISIONAL_NOT_INDEPENDENTLY_VALIDATED','record':'Unmodified native contract payload, or explicit stage/source inventory record'},'tables':files,'native_contracts':['case_bundle_manifest_v1','fulltext_l1_experimental_observation_schema_v3','StructuredExperimentalObservationRevision','AIReview','ExperimentalCore']}
 (output/'data_dictionary.json').write_text(canonical_json(dictionary)+'\n')
 value={**ShadowAuthority().model_dump(mode='json'),'schema_version':'case_bundle_manifest_v1','case_id':cid,'query':manifest['question'],'source_run_id':manifest['input_sha256'],'pipeline_complete':all(x['source_processing_complete'] for x in manifest.get('fulltext_coverage',{}).values()) and not manifest.get('literature_coverage',{}).get('partial',False) and manifest['terminal_state'] not in ('BUDGET_STOP','MODEL_FAILED','INTEGRITY_FAILED','PARTIAL_RESOURCE_STOP'),'terminal_state':manifest['terminal_state'],'dataset_product':'ai_provisional_scientific_tables','files':files,'data_dictionary_sha256':hashlib.sha256((output/'data_dictionary.json').read_bytes()).hexdigest(),'scientific_counts':{k:len(v) for k,v in tables.items()},'licensing':{'distribution':'restricted_internal','public_release_authorized':False,'fulltext_redistribution':'NOT_AUTHORIZED; per-source license and span redistribution assessment required','contains_source_evidence_spans':bool(tables['evidence_index'])},'source_hashes':manifest.get('sources',[])}
 value['source_processing_complete']=bool(manifest.get('fulltext_coverage')) and all(x['source_processing_complete'] for x in manifest['fulltext_coverage'].values())
 value['pipeline_complete']=False
 value['pipeline_complete_semantics']='Full original L0–L6 scientific execution is not certified by this provisional Pilot product'
 value['scientific_stage_completion']=manifest.get('scientific_stage_completion',{'full_L0_L6_scientific_execution':False,'reason':'No scientific completion certificate; see attempted stages'})
 value['scientific_inclusion_assessment']=manifest.get('scientific_inclusion_summary',{'assessment_completion':False,'reason':'not assessed/interrupted'})
 value['extraction_coverage']=manifest.get('fulltext_coverage',{})
 value['attempt_terminal_status']=manifest['terminal_state']
 value['dataset_version']=content_hash(value)
 (output/'case_bundle_manifest.json').write_text(canonical_json(value)+'\n');return value

def verify_dataset(path):
 path=Path(path);v=json.loads((path/'case_bundle_manifest.json').read_text())
 if content_hash({k:x for k,x in v.items() if k!='dataset_version'})!=v['dataset_version']:raise ValueError('dataset_manifest_hash_drift')
 for name,item in v['files'].items():
  raw=(path/name).read_bytes()
  if hashlib.sha256(raw).hexdigest()!=item['sha256'] or len(raw.splitlines())!=item['rows']:raise ValueError('dataset_table_integrity_failure')
 if hashlib.sha256((path/'data_dictionary.json').read_bytes()).hexdigest()!=v['data_dictionary_sha256']:raise ValueError('dataset_dictionary_integrity_failure')
 return v


def atlas_review_records(export,package):
 """Bind existing owner-exported Atlas rows; never treat them as Human Gold.

 The operator must supply a trusted Atlas export; content hashes are integrity,
 not a new identity/signature system or scientific reviewer verification.
 """
 from code_engine.orchestration.pilot_delivery import case_review_rows
 expected={r['review_item_id']:hashlib.sha256(canonical_json(r).encode()).hexdigest() for r in case_review_rows(package)}
 pages=export.get('pages') or [export];records=[]
 for page in pages:
  if content_hash({k:v for k,v in page.items() if k!='page_sha256'})!=page.get('page_sha256'):raise ValueError('Atlas_export_page_integrity_failure')
  for row in page['items']:
   if row.get('case_id')!=package['case_id']:continue
   if expected.get(row.get('review_item_id'))!=row.get('review_item_source_hash'):raise ValueError('Atlas_review_source_binding_mismatch')
   if not row.get('reviewer_user_id') or not row.get('schema_hash') or not row.get('instructions_hash'):raise ValueError('Atlas_review_identity_and_contract_required')
   records.append(row)
 return records
