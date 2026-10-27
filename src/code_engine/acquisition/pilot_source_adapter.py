"""Bind the existing prospective OA/JATS journal to its verified handoff adapter."""
from dataclasses import replace
from pathlib import Path
import json
from code_engine.acquisition import prospective_workflow as workflow
from code_engine.construction import handoff_adapter as adapter
from code_engine.fulltext.jats_parser import parse_jats
from code_engine.fulltext.source_windows import jats_source_view
from code_engine.discovery.ai_review_shadow import file_hash,content_hash
from code_engine.system_b.annotation_schemas.registry import canonical_json
from scripts.run_code_post_pilot_handoff_to_construction_adapter_offline import CONFIG as BASELINE
from scripts import search_plan_v24_alpha318a3_correction_reference as correction

class ProspectiveSourceAcquirer:
 def __init__(self,root,*,repository,execute_authorized=False,transport=None):
  self.root=Path(root).resolve();self.repository=Path(repository).resolve();self.authorized=execute_authorized;self.transport=transport
 def __call__(self,metadata):
  if not self.authorized and not getattr(self.transport,'offline',False):raise RuntimeError('new_literature_acquisition_not_authorized')
  identity={k:metadata[k] for k in ('pmid','pmcid','doi')}
  if not all(identity.values()) or 'publication_types' not in metadata or 'correction_relationships' not in metadata:raise ValueError('verified_metadata_and_correction_fields_required')
  source={'source_id':str(identity['pmid']),**identity,'publication_types':metadata['publication_types'],'correction_relationships':metadata['correction_relationships']}
  status=correction.classify(source['publication_types'],source['correction_relationships'])
  if status['state']!='CORRECTION_REFERENCE_CLEAR':return {'status':'ineligible','reason':'Existing correction-reference pre-OA gate: '+status['state']}
  source['pre_oa_handoff_state']='PRE_OA_CLEAR';pilot=self.root/str(identity['pmid']);pilot.mkdir(parents=True,exist_ok=True);source_path=pilot/'source_identity.json'
  if source_path.exists() and json.loads(source_path.read_text())!=source:raise ValueError('source_identity_drift')
  if not source_path.exists():source_path.write_text(canonical_json(source))
  manifest=workflow.build_manifest([workflow.reference(source_path)],run_id='source:'+str(identity['pmid']))
  journal=pilot/'journal'
  index=workflow.run(journal,manifest,transport=self.transport,authorize_live_network=self.authorized,create=not (journal/'request_manifest.json').exists())
  if not index.get('handoff'):return {'status':'unavailable','reason':'Existing OA/JATS/license/source/correction gates did not produce an eligible handoff','evidence_index':str(journal/'evidence_index.json')}
  marker='pilot_source_root_sha256';root_hash=adapter.root_hash(pilot,marker);marker_path=pilot/marker
  if marker_path.exists() and marker_path.read_text().strip()!=root_hash:raise ValueError('immutable_source_root_drift')
  if not marker_path.exists():marker_path.write_text(root_hash+'\n')
  cfg=replace(BASELINE,repository_root=self.repository,pilot_directory=str(pilot),pilot_marker=marker,pilot_root_sha256=root_hash,handoff_sha256=file_hash(journal/'handoff.json'),source_id=str(identity['pmid']),**identity)
  private=self.root/'derived'/str(identity['pmid']);private.mkdir(parents=True,exist_ok=True);token_path=private/'token_authority.json'
  authority=json.loads(token_path.read_text()) if token_path.exists() else adapter.issue_opaque_source_token(cfg)
  if not token_path.exists():token_path.write_text(canonical_json(authority));token_path.chmod(0o600)
  envelope=adapter.adapt_verified_handoff(cfg,authority)
  normalized=Path(envelope['controller_private_provenance']['normalized_jats_reference']['artifact_path']);article={**jats_source_view(normalized,identity),'article_path':str(private/'article_text.json')}
  article_path=private/'article_text.json';raw=canonical_json(article)+'\n'
  if article_path.exists() and article_path.read_text()!=raw:raise ValueError('derived_source_drift')
  if not article_path.exists():article_path.write_text(raw)
  envelope_path=private/'construction_envelope.json';envelope_path.write_text(canonical_json(envelope))
  return {'status':'available','acquisition_execution':'offline_frozen_transport_replay' if getattr(self.transport,'offline',False) else 'authorized_live','article_path':str(article_path),'source_sha256':file_hash(article_path),'handoff':{'path':str(journal/'handoff.json'),'sha256':file_hash(journal/'handoff.json')},'construction_envelope':{'path':str(envelope_path),'sha256':file_hash(envelope_path)},'verified_identity':identity,'verification_basis':'NCBI_JATS_identity_binding','redistribution':'Source passed existing license gate; public dataset release still requires separate assessment'}

class CorpusStageCatalog:
 def __init__(self,corpus,frozen_cases,*,execute_authorized=False,continue_work=lambda:True):
  self.continue_work=continue_work;self.execute_authorized=execute_authorized;self.corpus=corpus;self.cases=frozen_cases;self.fingerprint=content_hash({'cases':frozen_cases,'implementation':file_hash(Path(__file__))})
 def select_sources(self,request):
  if not self.execute_authorized and not getattr(self.corpus.client,'fixture',False):raise RuntimeError('pilot_acquisition_not_authorized')
  frozen=self.cases[request['case_id']]
  if request['question']!=frozen['question'] or request['scope']!=frozen['scope']:raise ValueError('frozen_scientific_scope_drift')
  self.corpus.discover(frozen,continue_work=self.continue_work);self.corpus.download(request['case_id'],continue_work=self.continue_work);return self.corpus.selected(request['case_id'])
 def coverage(self,cid):return self.corpus.coverage(cid)
 def construction_bundle(self,s):
  ref=s['binding']['construction_envelope'];p=Path(ref['path'])
  if file_hash(p)!=ref['sha256']:raise ValueError('construction_envelope_hash_drift')
  e=json.loads(p.read_text())
  if len(e['construction_document']['body_text'])>=60000 or len(e['construction_document']['abstract_text'])>=10000:
   from code_engine.acquisition.pilot_corpus import ResourcePause
   raise ResourcePause('frozen_construction_window_requires_complete_window_strategy; full source retained, not scientific completion')
  priv=e['controller_private_provenance'];identity=s['identity']
  return {'source':s,'token':priv['opaque_source_token'],'document':e['construction_document'],'private_identity':{**identity,'title_1':json.loads(Path(s['article_path']).read_text())['title']},'immutable_handoff':s['handoff']}

 def window_source(self,s):
  # Verify the existing immutable envelope even when its construction window is
  # saturated. Windowing wraps that contract; the sealed BODY is never replaced.
  ref=s['binding']['construction_envelope'];p=Path(ref['path'])
  if file_hash(p)!=ref['sha256']:raise ValueError('construction_envelope_hash_drift')
  e=json.loads(p.read_text());priv=e['controller_private_provenance']
  return {'token':priv['opaque_source_token'],'envelope':e,'article':json.loads(Path(s['article_path']).read_text())}
