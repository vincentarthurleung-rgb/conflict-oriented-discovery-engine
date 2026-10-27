"""One case, one append-only stage chain, existing scientific engines only."""
from __future__ import annotations
from pathlib import Path
import fcntl,hashlib,itertools,json,os,unicodedata
from contextlib import nullcontext
from code_engine.acquisition.pilot_corpus import ResourcePause
from code_engine.orchestration.pilot_dataset import export_attempt_dataset
from code_engine.orchestration.pilot_model_cache import SourceModelCache
from code_engine.fulltext.source_windows import coverage as window_coverage,aggregate_observations
from code_engine.system_b.annotation_schemas.registry import canonical_json
from code_engine.discovery.ai_review_shadow import content_hash,file_hash,load_bound_packet,bind_review
from code_engine.discovery.pilot_acceptance import export_review_package
from code_engine.orchestration.pilot_delivery import make_case_package,case_queue_row,case_review_rows,STAGES
from code_engine.orchestration.pilot_budget import ModelBudget,BudgetStop,cost_nusd
from code_engine.corpus.historical_seen import SeenBlocked
from code_engine.construction.handoff_adapter import validate_construction_document,NORMALIZATION,construction
from code_engine.construction.builder_quality_bridge import project_quality_accepted_builder_claims
from code_engine.construction.builder_quality_bridge_v2 import normalize_reviewable_builder_claims
from code_engine.fulltext.experimental_projection_handoff import prepare_experimental_handoff
from code_engine.fulltext.evidence_projection import project_fulltext_run
from code_engine.normalization.resolver import ResolverCascade
from code_engine.query.intake import parse_research_intake
from code_engine.orchestration.pilot_inclusion import frozen_intake,InclusionLedger,input_identity as inclusion_input_identity,coverage_accounting,question_identity
from scripts import search_plan_v24_alpha318b_post_builder_prechecks as prechecks
from scripts.search_plan_v24_alpha317c_reconcile_builder_offline import candidate_id
from scripts.search_plan_v24_alpha320a_v4_localizer import localize_exact_body_quote

class ModelFailure(RuntimeError):pass
class CaseIntegrity(ValueError):pass

class PilotCaseExecutor:
    def __init__(self,root:Path,seen,budget:ModelBudget,backend,*,model_cache=None):
        self.root=Path(root);self.seen=seen;self.budget=budget;self.backend=backend
        self.root.mkdir(parents=True,exist_ok=True)
        self.model_cache=model_cache or SourceModelCache(self.root.parent/'shared_model_cache')

    def run(self,request:dict):
        cid=request['case_id']
        if not cid or Path(cid).name!=cid or cid in ('.','..'):raise CaseIntegrity('invalid_case_id')
        with (self.root/('.'+cid+'.lock')).open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            if request.get('resume_partial'):
                original={k:v for k,v in request.items() if k!='resume_partial'}
                previous=self._run_locked(original)
                revisions=self.root/('.'+cid+'_continuations');index=0
                while (revisions/str(index)/cid/'review_package.json').exists():
                    previous=json.loads((revisions/str(index)/cid/'review_package.json').read_text());index+=1
                if previous['terminal_state'] not in ('BUDGET_STOP','PARTIAL_RESOURCE_STOP') and not (previous['terminal_state']=='MODEL_FAILED' and previous['run_manifest'].get('fulltext_coverage')):return previous
                continued=PilotCaseExecutor(revisions/str(index),self.seen,self.budget,self.backend,model_cache=self.model_cache).run({**original,'continuation_of_package_sha256':previous['package_sha256']})
                return continued
            return self._run_locked(request)

    def _run_locked(self,request):
        cid=request['case_id']
        from code_engine.orchestration.pilot_dependencies import effective_dependencies
        dependencies=self.backend.dependency_manifest() if hasattr(self.backend,'dependency_manifest') else effective_dependencies(Path(__file__).resolve().parents[3],fixture=self.backend.fixture)
        inclusion_inputs=inclusion_input_identity(request)
        from code_engine.orchestration.pilot_comparison import input_identity as comparison_input_identity
        comparison_inputs=comparison_input_identity(request)
        derived_dependencies=content_hash({'implementation_dependencies_sha256':dependencies['sha256'],'scientific_inclusion_inputs_sha256':inclusion_inputs,'scientific_comparison_inputs_sha256':comparison_inputs})
        dest=self.root/cid;fingerprint=content_hash({'comparison_inputs_sha256':comparison_inputs,'inclusion_inputs_sha256':inclusion_inputs,'request':request,'backend_sha256':self.backend.fingerprint,'budget_sha256':self.budget.fingerprint,'historical_root':self.seen.root,'effective_dependencies_sha256':dependencies['sha256']})
        def durable(path,text):
            temp=path.with_name(path.name+'.tmp')
            with temp.open('w') as stream:stream.write(text);stream.flush();os.fsync(stream.fileno())
            os.replace(temp,path)
        if (dest/'review_package.json').exists():
            from code_engine.orchestration.pilot_delivery import validate_case_package
            p=json.loads((dest/'review_package.json').read_text());validate_case_package(p)
            if p['run_manifest']['input_sha256']!=fingerprint:raise CaseIntegrity('case_identity_input_drift; preserve package and choose a new immutable revision directory')
            if not (dest/'manual_review_queue.jsonl').exists():durable(dest/'manual_review_queue.jsonl',canonical_json(case_queue_row(p))+'\n')
            return p
        if dest.exists():
            progress=dest/'manifest.progress.json'
            if not progress.is_file():raise CaseIntegrity('unregistered_directory_cannot_be_reused')
            m=json.loads(progress.read_text())
            if m['input_sha256']!=fingerprint:raise CaseIntegrity('interrupted_case_input_drift')
            tip=m['stages'][-1]['stage_sha256'] if m['stages'] else fingerprint
            done={r['stage'] for r in m['stages']}
            m.update(terminal_state='MODEL_FAILED',terminal_reason='INTERRUPTED_ATTEMPT; uncertain dispatch spend retained, no model re-dispatch.')
            for stage in STAGES:
                if stage in done:continue
                row={'case_id':cid,'stage':stage,'status':'executed' if stage in ('dataset_export','atlas_export') else 'blocked','reason':'Recovery exports the interrupted attempt without rerunning paid work.' if stage in ('dataset_export','atlas_export') else m['terminal_reason'],'previous_sha256':tip,'output_sha256':None}
                row['stage_sha256']=content_hash(row);tip=row['stage_sha256'];m['stages'].append(row)
            m['stage_chain_tip']=tip
            m['scientific_stage_completion']={'schema_version':'pilot_scientific_stage_completion_v1','full_L0_L6_scientific_execution':False,'formal_scientific_authorization':False,'stages':{s['stage']:{'status':s['status'],'output_sha256':s['output_sha256']} for s in m['stages']},'reason':'Interrupted attempt exported without redispatch'}
            durable(dest/'scientific_stage_completion.json',canonical_json(m['scientific_stage_completion'])+'\n')
            for pending in dest.glob('*_linkage_input.json'):
                outcome=pending.with_name(pending.name.removesuffix('_linkage_input.json')+'_linkage_outcome.json')
                if not outcome.exists():durable(outcome,canonical_json({'schema_version':'pilot_source_grounded_linkage_stage_v1','status':'interrupted_outcome_unknown_no_redispatch','input_artifact_sha256':file_hash(pending),'materialized_links':0,'scientific_authorization':False,'human_gold':False,'strict_core_eligible':False})+'\n')
            if not (dest/'scientific_inclusion_final.json').exists():
                initial=json.loads((dest/'scientific_inclusion_initial.json').read_text()) if (dest/'scientific_inclusion_initial.json').exists() else {'schema_version':'source_grounded_scientific_inclusion_v1','rows':[]}
                durable(dest/'scientific_inclusion_final.json',canonical_json({**initial,'interrupted_before_final_assessment':True})+'\n')
            m.setdefault('scientific_inclusion_summary',{'schema_version':'scientific_inclusion_coverage_v1','assessment_completion':False,'reason':'Interrupted attempt; no extraction/relevance success inferred','full_L0_L6_scientific_execution':False})
            if not (dest/'scientific_inclusion_coverage.json').exists():durable(dest/'scientific_inclusion_coverage.json',canonical_json(m['scientific_inclusion_summary'])+'\n')
            recovered_dataset=dest/'dataset'
            if recovered_dataset.exists() and any(recovered_dataset.iterdir()):
                n=0
                while (dest/('dataset_recovery_'+str(n))).exists():n+=1
                recovered_dataset=dest/('dataset_recovery_'+str(n))
            m['dataset_export']=export_attempt_dataset(m,dest,recovered_dataset)
            a=[]
            for path in sorted(dest.rglob('*')):
                if path.is_file() and path.suffix in ('.json','.jsonl','.txt'):
                    raw=path.read_text();a.append({'case_id':cid,'role':str(path.relative_to(dest)),'sha256':hashlib.sha256(raw.encode()).hexdigest(),'utf8':raw})
            package=make_case_package(m,pairs=[],artifacts=a,costs=self.budget.snapshot(cid))
            durable(dest/'review_package.json',canonical_json(package)+'\n')
            durable(dest/'manual_review_queue.jsonl',''.join(canonical_json(r)+'\n' for r in case_review_rows(package)))
            return package
        dest.mkdir();manifest={'case_id':cid,'question':request['question'],'scope':request.get('scope',{}),'evidence_mode':request['evidence_mode'],
                              'input_sha256':fingerprint,'historical_root':self.seen.root,'stages':[],
                              'sources':[],'has_deterministic_model_stubs':self.backend.fixture,'effective_dependencies_sha256':dependencies['sha256'],
                              'terminal_state':None,'terminal_reason':None,'stage_contract_version':'case_stages_v4','effective_inclusion_inputs_sha256':inclusion_inputs,'effective_comparison_inputs_sha256':comparison_inputs,'derived_execution_dependencies_sha256':derived_dependencies,'scientific_question_identity':question_identity(request),'continuation_of_package_sha256':request.get('continuation_of_package_sha256')}
        durable(dest/'manifest.progress.json',canonical_json(manifest)+'\n')
        artifacts=[];pairs=[];comparison=None;tip=fingerprint;active=None;active_window=None;source_plans={};window_states={};all_records=[];sources=[];inclusion=InclusionLedger(request);paper_decisions={}
        def save(name,value):
            path=dest/name;raw=canonical_json(value)+'\n'
            with path.open('x') as f:f.write(raw)
            artifacts.append({'case_id':cid,'role':name,'sha256':hashlib.sha256(raw.encode()).hexdigest(),'utf8':raw})
            return path
        def event(stage,status,reason,value=None):
            nonlocal tip
            row={'case_id':cid,'stage':stage,'status':status,'reason':reason,'previous_sha256':tip,
                 'output_sha256':content_hash(value) if value is not None else None,
                 'model_execution':'offline_replay_or_supplied_annotation' if self.backend.fixture and stage in ('builder_v4','quality_v2','experimental_v3_core','source_grounded_linkage','ai_review') else 'component_execution'}
            row['stage_sha256']=content_hash(row);tip=row['stage_sha256'];manifest['stages'].append(row)
            with (dest/'events.jsonl').open('a') as f:f.write(canonical_json(row)+'\n');f.flush();import os;os.fsync(f.fileno())
            durable(dest/'manifest.progress.json',canonical_json(manifest)+'\n')
        def window_progress():
            if not source_plans:return
            manifest['fulltext_coverage']={pmc:window_coverage(plan,window_states[pmc]) for pmc,plan in source_plans.items()}
            for pmc,cov in manifest['fulltext_coverage'].items():durable(dest/(pmc+'_source_window_coverage.json'),canonical_json(cov)+'\n')
            durable(dest/'manifest.progress.json',canonical_json(manifest)+'\n')
        save('effective_dependencies.json',dependencies)
        def raw_model(stage,key,payload,m):
            body=self.backend.prepare_model_request(stage,payload,provider=m['provider'],model=m['model'],max_output_tokens=m['max_output_tokens'])
            identity=self.backend.raw_request_identity(m['provider'],body)
            cache_key='raw_v1_'+content_hash(identity)
            with self.model_cache.locked(cache_key):
                self.model_cache.check_unbound_legacy_dispatches()
                cached=self.model_cache.load(cache_key)
                if cached is not None:
                    if cached.get('raw_request_identity')!=identity or cached.get('settlement')!='verified':raise CaseIntegrity('raw_provider_cache_binding_mismatch')
                    current_usage=self.backend.response_usage(stage,cached['raw_provider_response'],provider=m['provider'],model=m['model'])
                    if current_usage['model']!=m['model']:raise CaseIntegrity('cached_response_model_not_accepted_by_current_configuration')
                    save(stage+'_'+key+'_reuse.json',{'origin_case_id':cached['origin_case_id'],'request_id':cached['request_id'],'cache_sha256':cached['sha256'],'raw_request_identity':identity,'derived_dependencies_sha256':derived_dependencies,'new_charge_usd':'0'})
                    return self.backend.derive_response(stage,payload,cached['raw_provider_response'],request_body=body)
                bound=self.backend.input_upper_bound(stage,payload)
                if bound>m['max_input_tokens']:raise BudgetStop('input_token_upper_bound_limit')
                for attempt in range(1,self.budget.config['max_attempts']+1):
                    if hasattr(self.backend,'continue_work') and not self.backend.continue_work():raise ResourcePause('processing_resource_pause')
                    rid=self.budget.reserve(cid,stage+':'+key,attempt,request['model_stages'][stage],m['max_input_tokens'],m['max_output_tokens'])
                    self.model_cache.intent(cache_key,cid,rid);self.budget.dispatch(rid)
                    try:raw=self.backend.dispatch_raw(m['provider'],body)
                    except TimeoutError as error:
                        if not getattr(error,'safe_to_retry',False):raise ModelFailure('unknown_paid_dispatch_requires_reconciliation; no automatic resend') from error
                        self.model_cache.rejected_attempt(cache_key)
                        if attempt==self.budget.config['max_attempts']:raise ModelFailure('known_rejection_retry_exhausted') from error
                        if hasattr(self.backend,'retry_wait'):self.backend.retry_wait(error)
                        continue
                    except Exception as error:raise ModelFailure(stage+':'+str(error)) from error
                    usage=self.backend.response_usage(stage,raw,provider=m['provider'],model=m['model'])
                    captured={'origin_case_id':cid,'request_id':rid,'raw_request_identity':identity,'request_body':body,'raw_provider_response':raw,'usage':usage}
                    self.model_cache.capture_raw(cache_key,captured)
                    self.budget.settle(rid,usage)
                    self.model_cache.store(cache_key,{**captured,'settlement':'verified'})
                    response=self.backend.derive_response(stage,payload,raw,request_body=body)
                    save(stage+'_'+key+'_model_receipt.json',{'request_id':rid,'input_sha256':content_hash(payload),'raw_request_identity':identity,'raw_response_sha256':content_hash(raw),'derived_dependencies_sha256':derived_dependencies,'output_sha256':content_hash(response),'usage':usage,'reused':False})
                    return response
        def model_uncached(stage,key,payload,cache_key):
            # No model backend may run without a committed reservation.
            if hasattr(self.backend,'continue_work') and not self.backend.continue_work():raise ResourcePause('processing_resource_pause; exact source/model checkpoints retained')
            mkey=request['model_stages'][stage];m=self.budget.models[mkey]
            actual_bound=self.backend.input_upper_bound(stage,payload) if hasattr(self.backend,'input_upper_bound') else len(canonical_json(payload).encode())
            if actual_bound>m['max_input_tokens']:raise BudgetStop('input_token_upper_bound_limit')
            for attempt in range(1,self.budget.config['max_attempts']+1):
                rid=self.budget.reserve(cid,stage+':'+key,attempt,mkey,m['max_input_tokens'],m['max_output_tokens'])
                self.model_cache.intent(cache_key,cid,rid)
                self.budget.dispatch(rid)
                try:
                    response,usage=self.backend.complete(stage,key,payload,provider=m['provider'],model=m['model'],max_output_tokens=m['max_output_tokens'])
                except TimeoutError as e:
                    if not getattr(e,'safe_to_retry',False):raise ModelFailure('unknown_paid_dispatch_requires_reconciliation; no automatic resend') from e
                    if attempt==self.budget.config['max_attempts']:raise ModelFailure('transient_model_retry_exhausted')
                    if hasattr(self.backend,'retry_wait'):self.backend.retry_wait(e)
                    continue # Unknown spend is retained at its full reservation.
                except Exception as e:raise ModelFailure(stage+':'+str(e)) from e
                self.budget.settle(rid,usage)
                self.model_cache.store(cache_key,{'origin_case_id':cid,'request_id':rid,'response':response,'usage':usage})
                save(stage+'_'+key+'_model_receipt.json',{'request_id':rid,'input_sha256':content_hash(payload),'output_sha256':content_hash(response),'usage':usage,'reused':False})
                return response
            raise ModelFailure('model_did_not_return')
        def model(stage,key,payload):
            if hasattr(self.backend,'continue_work') and not self.backend.continue_work():raise ResourcePause('processing_resource_pause; source work retained')
            m=self.budget.models[request['model_stages'][stage]]
            routing=self.backend.request_routing(stage,payload) if hasattr(self.backend,'request_routing') else None
            if routing is not None:save(stage+'_'+key+'_prompt_routing.json',routing)
            if hasattr(self.backend,'prepare_model_request'):
                if hasattr(self.backend,'reuse'):
                    reused=self.backend.reuse(stage,key,payload)
                    if reused is not None:
                        save(stage+'_'+key+'_reuse.json',{k:v for k,v in reused.items() if k!='response'})
                        return reused['response']
                return raw_model(stage,key,payload,m)
            cache_key=content_hash({'stage':stage,'payload':payload,'model':m,'routing':routing,'backend':self.backend.cache_fingerprint(stage) if hasattr(self.backend,'cache_fingerprint') else self.backend.fingerprint})
            with self.model_cache.locked(cache_key):
                if hasattr(self.backend,'reuse'):
                    reused=self.backend.reuse(stage,key,payload)
                    if reused is not None:
                        save(stage+'_'+key+'_reuse.json',{k:v for k,v in reused.items() if k!='response'})
                        return reused['response']
                cached=self.model_cache.load(cache_key)
                if cached is not None:
                    save(stage+'_'+key+'_reuse.json',{'origin_case_id':cached['origin_case_id'],'request_id':cached['request_id'],'cache_sha256':cached['sha256'],'new_charge_usd':'0'})
                    return cached['response']
                return model_uncached(stage,key,payload,cache_key)
        try:
            if request['evidence_mode'] not in ('authentic_seen_replay','authorized_new_pilot'):raise CaseIntegrity('invalid_execution_mode')
            if request['evidence_mode']=='authorized_new_pilot' and (self.backend.fixture or self.budget.offline):raise CaseIntegrity('offline_fixture_cannot_execute_new_pilot')
            for stage in STAGES[:-2]:
                active=stage
                if stage=='intake':
                    if not request['question'].strip():raise CaseIntegrity('question_missing')
                    parsed,intake_trace=frozen_intake(request)
                    save('semantic_intake_trace.json',intake_trace);manifest['semantic_intake_trace']=intake_trace
                    save('intake.json',parsed);value={'question':request['question'],'parser_mode':parsed['parser_mode'],'scope':request['scope']}
                    if hasattr(self.backend,'bind_question_profile'):
                        manifest['question_domain_routing']=self.backend.bind_question_profile(parsed)
                        save('question_domain_routing.json',manifest['question_domain_routing'])
                elif stage=='source_selection_acquisition':
                    sources=[]
                    for spec in self.backend.select_sources(request):
                        identity=spec['identity'];binding=spec['binding']
                        if request['evidence_mode']=='authorized_new_pilot':self.seen.register_exposure(identity,spec.get('exposure_work_id',cid))
                        else:
                            try:self.seen.check_source_identity(identity)
                            except SeenBlocked as e:
                                if not str(e).startswith('historical_source_excluded:'):raise
                            else:raise CaseIntegrity('SEEN_replay_fixture_not_in_history')
                        article=self.backend.acquire(spec) # The gate above precedes source acquisition.
                        raw=Path(article).read_bytes()
                        if hashlib.sha256(raw).hexdigest()!=binding['source_sha256']:raise CaseIntegrity('acquired_source_hash_mismatch')
                        obj=json.loads(raw)
                        if str(obj['pmid'])!=str(identity['pmid']) or obj['pmcid']!=identity['pmcid']:raise CaseIntegrity('acquired_source_identity_mismatch')
                        if hasattr(self.backend,'classify_source'):save(identity['pmcid']+'_paper_design_routing.json',self.backend.classify_source(obj))
                        if request['evidence_mode']=='authorized_new_pilot':self.seen.check_source(identity,binding={**binding,'article_path':str(article)},case_id=spec.get('exposure_work_id',cid))
                        local=dest/(identity['pmcid']+'_article.json');local.write_bytes(raw)
                        sources.append({**spec,'origin_article_path':spec.get('article_path',str(article)),'article_path':str(local)})
                    manifest['sources']=[{'identity':s['identity'],'source_sha256':s['binding']['source_sha256']} for s in sources]
                    if hasattr(self.backend,'coverage'):manifest['literature_coverage']=self.backend.coverage(cid)
                    save('selection.json',manifest['sources']);value={'count':len(sources),'mode':request['evidence_mode']}
                    if not sources:
                        event(stage,'executed','No eligible sources; attempt retained.',value);manifest.update(terminal_state='NOT_EVALUABLE',terminal_reason='ZERO_ELIGIBLE_SOURCES');break
                elif stage=='immutable_handoff':
                    bundles=[]
                    for s in sources:
                        if request['evidence_mode']=='authorized_new_pilot':self.seen.check_source(s['identity'],binding={**s['binding'],'article_path':s['article_path']},case_id=s.get('exposure_work_id',cid))
                        if hasattr(self.backend,'construction_bundles'):
                            many=self.backend.construction_bundles(s)
                            if many is not None:
                                pmc=s['identity']['pmcid'];plan=self.backend._windowplans[pmc];source_plans[pmc]=plan
                                window_states[pmc]={w['window_id']:{k:{'status':'pending','reason':'not_dispatched'} for k in ('builder_v4','quality_v2','experimental_v3_core')} for w in plan['windows']}
                                save(pmc+'_source_window_plan.json',plan);window_progress();bundles.extend(many);continue
                        if hasattr(self.backend,'construction_bundle'):
                            b=self.backend.construction_bundle(s)
                            if b is not None:
                                validate_construction_document(b['document'],b['token']);bundles.append(b);continue
                            if not self.backend.fixture:raise CaseIntegrity('verified_immutable_handoff_required_for_new_source')
                        a=json.loads(Path(s['article_path']).read_text());token=self.backend.source_token(s,cid) if hasattr(self.backend,'source_token') else 'src_'+content_hash([cid,s['identity']])
                        paragraphs=[];body=''
                        for section in a['sections']:
                            if section['section_title'] not in ('results','methods','fig'):continue
                            text=' '.join(unicodedata.normalize('NFKC',section['text']).split())
                            if not text:continue
                            prefix='\n\n' if body else ''
                            start=len(body)+len(prefix);ordinal=len(paragraphs)+1;path=[section['section_title']]
                            anchor='spanv1_'+construction.digest([construction.SPAN_VERSION,token,path,ordinal,construction.sha_text(text)])
                            paragraphs.append({'section_path':path,'section_headings':path,'kind':'paragraph','ordinal':ordinal,'text':text,'start_offset':start,'end_offset':start+len(text),'span_id':anchor});body+=prefix+text
                        doc={'schema_version':'ConstructionEvidenceDocumentV1','abstract_text':'','body_text':body,'paragraphs':paragraphs,'article_title_visible':False,'bibliography_visible':False,'normalization':NORMALIZATION}
                        validate_construction_document(doc,token)
                        bundle={'source':s,'token':token,'document':doc,'private_identity':{'pmid':str(a['pmid']),'pmcid':a['pmcid'],'doi':s['identity'].get('doi'),'title_1':a['title']}}
                        bundles.append(bundle)
                    save('immutable_handoff.json',bundles);value={'source_hashes':[s['binding']['source_sha256'] for s in sources],'documents':[content_hash(b['document']) for b in bundles],'source_role':'frozen authentic fixture replay' if self.backend.fixture else 'acquired_verified_source'}
                elif stage=='scientific_inclusion':
                    for source in sources:
                        row=inclusion.decide(source);paper_decisions[source['identity']['pmcid']]=row
                        for candidate in inclusion.assessments:
                            if candidate.get('source_identity')==source['identity'] and candidate.get('scope_level') in ('experiment','observation'):
                                inclusion.decide(source,scope_level=candidate['scope_level'],scope_identity=candidate['scope_identity'])
                    # Access failures and retrieval exclusions are separate from
                    # scientific exclusion, including sources never selected.
                    coverage=manifest.get('literature_coverage') or {}
                    selected={str(s['identity'].get('pmcid') or s['identity'].get('pmid') or s['identity'].get('doi')) for s in sources}
                    for entry in coverage.get('papers',[]):
                        metadata=entry.get('metadata') or {}
                        if isinstance(metadata,str):metadata=json.loads(metadata)
                        identity={k:metadata.get(k) for k in ('pmid','pmcid','doi')}
                        if str(identity.get('pmcid') or identity.get('pmid') or identity.get('doi')) in selected:continue
                        inclusion.decide({'identity':identity,'access_state':entry.get('status','not_yet_acquired'),'retrieval_eligibility':entry.get('decision','not_assessed')})
                    save('scientific_inclusion_initial.json',inclusion.export())
                    value={'paper_decisions':{k:v['decision'] for k,v in paper_decisions.items()},'retrieval_eligibility_is_not_inclusion':True}
                elif stage=='builder_v4':
                    builders=[]
                    for b in bundles:
                        source_pmc=b['source']['identity']['pmcid']
                        if paper_decisions.get(source_pmc,{}).get('decision')=='EXCLUDED':
                            if b.get('window'):
                                window_states[source_pmc][b['window']['window_id']]={k:{'status':'scientifically_excluded','reason':paper_decisions[source_pmc]['reason']} for k in ('builder_v4','quality_v2','experimental_v3_core')};window_progress()
                            continue
                        pmc=b['source']['identity']['pmcid'];active_window=(pmc,b['window']['window_id']) if 'window' in b else None;key=pmc+'_'+b['window']['window_id'] if 'window' in b else pmc;bm=self.backend.builder_request(b)
                        save(key+'_builder_request.json',bm);br=model(stage,key,bm['request']);prechecks.validate_builder_response(canonical_json(json.loads(br['choices'][0]['message']['content'])).encode(),b['token'],bm['expected_response_schema'])
                        builders.append((b,bm,br));save(key+'_builder.json',{'request_manifest':bm,'response':br,'fixture':self.backend.fixture})
                        if active_window:window_states[pmc][active_window[1]][stage]={'status':'processed','reason':'frozen_response_validator_passed'};window_progress()
                    value={'source_windows':len(builders)}
                elif stage=='quality_v2':
                    claims=[]
                    for b,bm,br in builders:
                        pmc=b['source']['identity']['pmcid'];active_window=(pmc,b['window']['window_id']) if 'window' in b else None;key=pmc+'_'+b['window']['window_id'] if 'window' in b else pmc
                        if not json.loads(br['choices'][0]['message']['content'])['candidates']:
                            if active_window:window_states[pmc][active_window[1]][stage]={'status':'not_applicable','reason':'No Builder candidates; frozen Quality requires 1–3, no Quality call or fabricated PASS'};window_progress()
                            continue
                        qm=self.backend.quality_request(b,bm,br);qr=model(stage,key,qm['request'])
                        projection=project_quality_accepted_builder_claims(document=b['document'],private_source_token=b['token'],source_identity=b['source']['identity'],private_identity=b['private_identity'],builder_request_manifest=bm,builder_response_raw=canonical_json(br).encode(),builder_response_sha256=content_hash(br),quality_request_manifest=qm,quality_response_raw=canonical_json(qr).encode(),quality_response_sha256=content_hash(qr))
                        for claim in projection['claims']:
                            if request['evidence_mode']=='authorized_new_pilot':self.seen.check_candidate(claim['candidate_id'],content_hash(claim['builder_candidate']))
                        claims.extend([{**c,'source_window_id':b['window']['window_id']} if 'window' in b else c for c in projection['claims']]);save(key+'_quality.json',{'request_manifest':qm,'response':qr,'validated_claims':projection['claims'],'fixture':self.backend.fixture})
                        if active_window:window_states[pmc][active_window[1]][stage]={'status':'processed','reason':'frozen_quality_projection_validated'};window_progress()
                    # Only exact same candidate payloads deduplicate; retain all window occurrences.
                    distinct={}
                    for c in claims:
                        ident=content_hash([c.get('source_identity'),c.get('builder_candidate')]);distinct.setdefault(ident,{**c,'source_window_occurrences':[]})
                        if c.get('source_window_id'):distinct[ident]['source_window_occurrences'].append(c['source_window_id'])
                    claims=list(distinct.values())
                    value={'quality_accepted_claims':len(claims)}
                    if not claims:
                        event(stage,'executed','No Quality-accepted scientific claims; no extraction substituted.',value);manifest.update(terminal_state='INSUFFICIENT_EVIDENCE',terminal_reason='NO_QUALITY_ELIGIBLE_CLAIMS');break
                elif stage=='experimental_v3_core':
                    records=[]
                    for s in sources:
                        pmc=s['identity']['pmcid']
                        if paper_decisions.get(pmc,{}).get('decision')=='EXCLUDED':continue
                        if request['evidence_mode']=='authorized_new_pilot':self.seen.check_source(s['identity'],binding={**s['binding'],'article_path':s['article_path']},case_id=s.get('exposure_work_id',cid))
                        extracted=[]
                        for window in source_plans.get(pmc,{}).get('windows',[None]):
                            active_window=(pmc,window['window_id']) if window else None;key=pmc+'_'+window['window_id'] if window else pmc
                            payload={'source_sha256':s['binding']['source_sha256'],'article':json.loads(Path(s['article_path']).read_text()),'source_artifact':s.get('origin_article_path',s['article_path']),'quality_claims':[c for c in claims if c['source_identity']['pmcid']==pmc and (not window or window['window_id'] in c.get('source_window_occurrences',[]))]}
                            if window:payload['window']=window
                            out=model(stage,key,payload)
                            if window:window_states[pmc][window['window_id']][stage]={'status':'failed_validation' if (out or {}).get('assembly_failures') or (out or {}).get('incomplete',{}).get('rejected') or (out or {}).get('incomplete',{}).get('provider_parse_error') else 'processed','reason':'Actual response retained; parse/assembly failures do not imply source completion','rejected_observations':len((out or {}).get('incomplete',{}).get('rejected',[])),'output_state':'empty' if out is not None and 'formal_v3' in out.get('incomplete',{}) and not out.get('incomplete',{}).get('formal_v3',{}).get('experimental_observations') and not out.get('records') and not out.get('core_utf8') and not out.get('incomplete',{}).get('rejected') and not out.get('incomplete',{}).get('provider_parse_error') else 'nonempty_or_unresolved'};window_progress()
                            if out and out.get('records'):extracted.extend(out['records'])
                            if out and 'core_utf8' in out:extracted.append(out)
                            if not out or out.get('incomplete') or not ('core_utf8' in out or out.get('records')):
                                save(key+'_incomplete_experimental_records.json',{'source':s['identity'],'window_id':window['window_id'] if window else None,'output':out,'missing':'Missing extraction/linkage fields retained; any assembled native Core below remains provisional'})
                        if pmc in source_plans:extracted=aggregate_observations(extracted)
                        for n,out in enumerate(extracted):
                            formal=json.loads(out['core_utf8'])['ExperimentalObservationV3'];suffix=content_hash(formal['observation_id'])[:20];record_key=pmc+'_'+suffix if pmc in source_plans or len(extracted)>1 else pmc
                            d=dest/pmc/suffix if pmc in source_plans or len(extracted)>1 else dest/pmc;d.mkdir(parents=True);packet=d/'packet.json';core=d/'core.json';prompt=d/'review_prompt.txt'
                            packet.write_text(out['packet_utf8']);core.write_text(out['core_utf8']);prompt.write_text(out['review_prompt_utf8'])
                            bound=load_bound_packet(packet,prompt,core)
                            if bound.input_hashes['source']!=s['binding']['source_sha256'] or bound.packet['source']['pmcid']!=pmc:raise CaseIntegrity('experimental_core_unrelated_source')
                            prepared=prepare_experimental_handoff(json.loads(core.read_text()),d)
                            lineage=out.get('v3_lineage')
                            if out.get('v3_lineage_material'):
                                material=out['v3_lineage_material'];pins={}
                                for field,name in (('raw_provider_response','response'),('validated_formal_v3','validated')):
                                    path=save(record_key+'_V3_'+name+'.json',material[field]);pins[name]={'path':str(path.resolve()),'sha256':file_hash(path)}
                                lineage={**pins,**{k:material[k] for k in ('hydration_context','source_blocks','window')}}
                            records.append({'source':s,'record_key':record_key,'packet':packet,'core':core,'prompt':prompt,'prepared':prepared,'v3_lineage':lineage})
                            obs_decision=inclusion.decide(s,scope_level='observation',scope_identity=formal['observation_id'],observation=formal)
                            inclusion.decide(s,scope_level='experiment',scope_identity=formal['experiment']['experiment_id'],observation=formal)
                            records[-1]['inclusion']=obs_decision
                            if 'window_occurrences' in out:save(record_key+'_observation_window_provenance.json',{k:out[k] for k in ('aggregation_identity','window_occurrences','observation_occurrences','source_evidence','assembly')})
                    all_records=list(records)
                    records=[r for r in all_records if r['inclusion']['downstream_processing_permitted']]
                    save('observation_processing_decisions.json',{'retained_native_records':len(all_records),'records_permitted_downstream':len(records),'decisions':[r['inclusion'] for r in all_records]})
                    value={'retained_native_records':len(all_records),'downstream_records':len(records),'scientifically_excluded_native_records_retained':len(all_records)-len(records)}
                elif stage=='source_grounded_linkage':
                    from code_engine.orchestration.pilot_linkage import VERSION as LINKAGE_VERSION,prepare_stage,assess_stage
                    summaries=[];active_window=None
                    for r in records:
                        key=r['record_key'];envelope=json.loads(r['core'].read_text());oid=envelope['ExperimentalObservationV3']['observation_id']
                        outcome={'schema_version':LINKAGE_VERSION,'observation_identity':oid,'status':'not_prepared','materialized_links':0,'scientific_authorization':False,'human_gold':False,'strict_core_eligible':False}
                        try:
                            if not r.get('v3_lineage'):raise ValueError('original_V3_response_lineage_unavailable')
                            supplement=self.backend.linkage_supplement(oid) if hasattr(self.backend,'linkage_supplement') else None
                            settings=self.budget.models[request['model_stages'][stage]] if stage in request['model_stages'] else {}
                            prepared_linkage=prepare_stage(envelope,r['v3_lineage'],supplement=supplement,question_domain=getattr(self.backend,'question_domain',None),model=settings.get('model','deepseek-flash'),max_output_tokens=settings.get('max_output_tokens',8192),input_token_ceiling=min(40000,settings.get('max_input_tokens',40000)))
                            save(key+'_linkage_input.json',prepared_linkage)
                            replay=self.backend.linkage_replay(oid) if hasattr(self.backend,'linkage_replay') else None
                            if replay is not None:
                                save(key+'_linkage_replay_origin.json',replay)
                                outcome=assess_stage(prepared_linkage,replay['response'],proposal_origin=replay['proposal_origin'])
                            elif stage not in request['model_stages']:
                                outcome.update(status='prepared_NOT_AUTHORIZED',reason='No linkage model stage/budget selected; no dispatch',input_sha256=prepared_linkage['prepared_request']['input_sha256'])
                            else:
                                raw=model(stage,key,prepared_linkage)
                                save(key+'_linkage_response_original.json',raw)
                                if isinstance(raw,dict) and raw.get('incomplete'):
                                    outcome.update(status='model_response_invalid',reason=raw['incomplete'],raw_output=raw)
                                else:outcome=assess_stage(prepared_linkage,raw,proposal_origin='offline_transport_fixture_not_provider_linkage_output' if self.backend.fixture else 'provider_linkage_response')
                        except (ModelFailure,BudgetStop,ResourcePause) as error:
                            outcome.update(status='model_failed_or_interrupted',reason=type(error).__name__+':'+str(error))
                            save(key+'_linkage_outcome.json',outcome);raise
                        except (ValueError,KeyError,TypeError) as error:
                            outcome.update(status='rejected_input_or_response',reason=type(error).__name__+':'+str(error))
                        save(key+'_linkage_outcome.json',outcome)
                        summaries.append({'observation_identity':oid,'status':outcome['status'],'materialized_links':0})
                    save('linkage_stage_summary.json',{'schema_version':LINKAGE_VERSION,'records':summaries,'model_execution_configured':stage in request['model_stages'],'scientific_authorization':False})
                    value={'records':summaries,'materialized_links':0,'independent_scientific_authorization':False}
                elif stage=='ai_review':
                    if stage not in request['model_stages']:
                        event(stage,'skipped','No AI review configured; no synthetic review substituted.');continue
                    for r in records:
                        pmc=r['source']['identity']['pmcid'];key=r.get('record_key',pmc);out=model(stage,key,{'packet':json.loads(r['packet'].read_text()),'core':json.loads(r['core'].read_text()),'prompt':r['prompt'].read_text()})
                        review=bind_review(load_bound_packet(r['packet'],r['prompt'],r['core']),out);r['review']=save(key+'_review.json',review.model_dump(mode='json'))
                    value={'source_reviews_bound':len(records),'new_independent_review':False if self.backend.fixture else None}
                    if not records:event(stage,'skipped','No complete experimental record to review.',value);continue
                elif stage=='normalization_projection':
                    resolver=ResolverCascade(execute=False,network_enabled=False,api_enabled=False,entity_network_lookup=False,entity_llm_proposer=False,entity_llm_cleaner=False,external_clients={})
                    normalized=normalize_reviewable_builder_claims(claims,resolver);save('normalized_builder_claims.json',normalized)
                    if records:
                        inp=dest/'projection_input/artifacts';inp.mkdir(parents=True);(inp/'l35_fulltext_l1_claims.jsonl').write_text(''.join(canonical_json(json.loads(r['core'].read_text()))+'\n' for r in records))
                        summary=project_fulltext_run(inp.parent,dest/'projection')
                        projected=[json.loads(line) for line in (Path(summary['output_run'])/'artifacts/fulltext_projected_observations.jsonl').read_text().splitlines() if line.strip()]
                        if len(projected)!=len(records):raise CaseIntegrity('native_projection_record_loss')
                        save('projection_summary.json',summary);save('projected_native_observations.json',projected)
                    value={'normalized_claims':len(normalized),'native_core_records_projected':len(records)}
                elif stage=='shadow_alignment':
                    if request.get('scientific_comparison_profile') != 'legacy_shadow_v1':
                        from code_engine.orchestration.pilot_comparison import run_comparison
                        upstream={'effective_dependencies_sha256':derived_dependencies,
                                  'intake_trace_sha256':file_hash(dest/'semantic_intake_trace.json'),
                                  'inclusion_ledger_sha256':content_hash(inclusion.export()),
                                  'native_records':{r['record_key'] if r.get('record_key') else str(i):file_hash(r['core']) for i,r in enumerate(all_records)},
                                  'linkage_and_projection':{str(p.relative_to(dest)):file_hash(p) for p in dest.rglob('*.json') if
                                      p.name.endswith(('_linkage_input.json','_linkage_outcome.json')) or p.name in ('projected_native_observations.json','projection_summary.json')}}
                        comparison=run_comparison(request,inclusion.export(),all_records,bindings=upstream)
                        save('scientific_comparison.json',comparison)
                        manifest['scientific_comparison_summary']={k:comparison[k] for k in ('schema_version','input_state','denominators','coverage','formal_authority_blockers')}
                        value={'comparison_sha256':content_hash(comparison),'denominators':comparison['denominators'],'formal_scientific_authorization':False}
                        if comparison['input_state']['status']=='NOT_EVALUATED':
                            manifest.update(terminal_state='NOT_EVALUABLE',terminal_reason='B4_SEMANTIC_INPUT_UNAVAILABLE; no legacy lexical comparison substituted')
                            event(stage,'skipped','Missing pinned source-grounded semantic comparison input.',value)
                            break
                        event(stage,'executed','Source-bound provisional scientific comparison; formal L4 prerequisites preserved.',value)
                        continue
                    if not (self.backend.fixture and self.budget.offline and request['evidence_mode']=='authentic_seen_replay'):
                        raise CaseIntegrity('legacy_shadow_profile_is_offline_historical_compatibility_only')
                    eligible=[];excluded=[]
                    for record in records:
                        readiness=record['prepared']['experimental_core_handoff_audit']['readiness']['status']
                        if readiness.startswith('machine_reusable'):eligible.append(record)
                        else:excluded.append({'observation_revision_identity':record['prepared']['experimental_core']['revision']['identity'],'existing_readiness':readiness,'reason':'Reviewable native record retained; existing Core linkage readiness blocks Shadow alignment'})
                    if excluded:save('shadow_alignment_exclusions.json',excluded)
                    for a,b in itertools.combinations(eligible,2):
                        if a['source']['identity']['pmid']==b['source']['identity']['pmid']:continue
                        if a['prompt'].read_bytes()!=b['prompt'].read_bytes():raise CaseIntegrity('cross_source_review_prompt_drift')
                        pair=export_review_package(cid,[a['packet'],b['packet']],[a['review'],b['review']],[a['core'],b['core']],a['prompt']);pairs.append(pair)
                    value={'pair_count':len(pairs),'pair_hashes':[p['package_sha256'] for p in pairs]}
                    if not pairs:
                        event(stage,'skipped','Fewer than two complete source-reviewed experimental records.',value);manifest.update(terminal_state='INSUFFICIENT_EVIDENCE',terminal_reason='ONE_OR_INCOMPLETE_EXPERIMENTAL_SOURCE');break
                elif stage=='context_analysis':
                    value={'context_differences':[p['context_differences'] for p in comparison['pairs']],
                           'context_attribution':[p['context_attribution'] for p in comparison['pairs']],
                           'causal_explanation_authorized':False} if comparison is not None else {'context_differences':[p['alignment']['context_differences'] for p in pairs],'causal_explanation_authorized':False}
                    if comparison is not None:save('scientific_context_attribution.json',value)
                elif stage=='contradiction_classification':
                    if comparison is not None:
                        # Keep case terminal conservative: provisional diagnostics cannot
                        # impersonate an existing formally reviewed pair package.
                        value={'pair_qualifications':[{'pair_id':p['pair_id'],'alignment':p['alignment'],'qualification':p['qualification'],'formal_qualification':p['formal_qualification']} for p in comparison['pairs']],
                               'formal_scientific_authorization':False}
                        save('scientific_qualification.json',value)
                        manifest.update(terminal_state='NOT_EVALUABLE',terminal_reason='SOURCE_BOUND_PROVISIONAL_COMPARISON_COMPLETE; formal scientific qualification blocked; see pair diagnostics')
                        event(stage,'executed','Provisional screening and formal abstention reported separately.',value)
                        continue
                    states=[p['terminal_state'] for p in pairs]
                    terminal=next((state for state in ('PROVISIONAL_CONTRADICTION','NO_CONTRADICTION_AFTER_COMPARISON','INSUFFICIENT_EVIDENCE','NOT_SUFFICIENTLY_COMPARABLE') if state in states),'NOT_EVALUABLE')
                    manifest.update(terminal_state=terminal,terminal_reason='Existing Shadow results; no scientific qualification or authority granted.');value={'pair_terminals':states,'case_terminal':terminal}
                elif stage=='hypothesis':
                    hypotheses=comparison['hypotheses'] if comparison is not None else [h for p in pairs for h in p['alignment']['hypotheses']];value={'hypotheses':hypotheses}
                    if comparison is not None:save('scientific_hypothesis_constraints.json',{'hypotheses':hypotheses,'abstentions':[{'pair_id':p['pair_id'],'reason':p.get('hypothesis_abstention_reason',p['reason'])} for p in comparison['pairs'] if not p['hypotheses']],'qualified_hypotheses':0,'scientific_authorization':False})
                    if not hypotheses:event(stage,'skipped','Existing Shadow criteria produced zero hypotheses.',value);continue
                event(stage,'executed','Existing implementation executed on this case-bound input.',value)
                if request.get('development_stop_after')==stage:
                    if not self.backend.fixture:raise CaseIntegrity('development_stop_requires_explicit_offline_fixture')
                    manifest.update(terminal_state='NOT_EVALUABLE',terminal_reason='BOUNDED_OFFLINE_DEVELOPMENT_STOP_AFTER:'+stage);break
        except Exception as e:
            if active_window:
                window_states[active_window[0]][active_window[1]][active]={'status':'failed','reason':type(e).__name__+':'+str(e)}
            terminal='PARTIAL_RESOURCE_STOP' if isinstance(e,ResourcePause) else 'BUDGET_STOP' if isinstance(e,BudgetStop) else 'INTEGRITY_FAILED' if isinstance(e,(SeenBlocked,CaseIntegrity)) else 'MODEL_FAILED' if isinstance(e,ModelFailure) else 'INTEGRITY_FAILED'
            manifest.update(terminal_state=terminal,terminal_reason=type(e).__name__+':'+str(e))
            if active:event(active,'blocked' if isinstance(e,(BudgetStop,SeenBlocked)) else 'failed',manifest['terminal_reason'])
        done={s['stage'] for s in manifest['stages']}
        for stage in STAGES[:-2]:
            if stage not in done:event(stage,'skipped','Upstream terminal: '+str(manifest['terminal_reason']))
        if manifest['terminal_state'] is None:manifest.update(terminal_state='NOT_EVALUABLE',terminal_reason='No evaluable pair result.')
        if hasattr(self.backend,'coverage'):
            manifest['literature_coverage']=self.backend.coverage(cid)
            if manifest['literature_coverage'].get('partial') and manifest['terminal_state'] not in ('BUDGET_STOP','MODEL_FAILED','INTEGRITY_FAILED'):
                manifest.update(terminal_state='PARTIAL_RESOURCE_STOP',terminal_reason='Search/download/processing coverage incomplete; no scientific completion claim.')
        if source_plans:
            manifest['fulltext_coverage']={pmc:window_coverage(plan,window_states[pmc]) for pmc,plan in source_plans.items()}
            window_progress()
            if any(not x['source_processing_complete'] for x in manifest['fulltext_coverage'].values()) and manifest['terminal_state'] not in ('MODEL_FAILED','INTEGRITY_FAILED','BUDGET_STOP'):
                manifest.update(terminal_state='PARTIAL_RESOURCE_STOP',terminal_reason='Source windows or unprojected XML regions remain pending; not source-level scientific completion.')
        known_papers={str(r['source_identity'].get('pmcid') or r['source_identity'].get('pmid') or r['source_identity'].get('doi')) for r in inclusion.export()['rows'] if r['scope_level']=='paper'}
        for source in sources:
            if str(source['identity'].get('pmcid') or source['identity'].get('pmid') or source['identity'].get('doi')) not in known_papers:inclusion.decide(source)
        for entry in (manifest.get('literature_coverage') or {}).get('papers',[]):
            metadata=entry.get('metadata') or {}
            try:
                if isinstance(metadata,str):metadata=json.loads(metadata)
                identity={k:metadata.get(k) for k in ('pmid','pmcid','doi')}
                if str(identity.get('pmcid') or identity.get('pmid') or identity.get('doi')) not in {str(r['source_identity'].get('pmcid') or r['source_identity'].get('pmid') or r['source_identity'].get('doi')) for r in inclusion.export()['rows'] if r['scope_level']=='paper'}:inclusion.decide({'identity':identity,'access_state':entry.get('status','not_yet_acquired'),'retrieval_eligibility':entry.get('decision','not_assessed')})
            except (ValueError,TypeError):pass
        manifest['_model_usage_rows']=self.budget.snapshot(cid)['requests']
        manifest['scientific_inclusion_summary']=coverage_accounting(manifest,inclusion.export()['rows'],all_records,source_plans,window_states,dest)
        manifest.pop('_model_usage_rows',None)
        save('scientific_inclusion_final.json',inclusion.export())
        save('scientific_inclusion_coverage.json',manifest['scientific_inclusion_summary'])
        manifest['scientific_stage_completion']={'schema_version':'pilot_scientific_stage_completion_v1','stages':{s['stage']:{'status':s['status'],'output_sha256':s['output_sha256']} for s in manifest['stages']},'full_L0_L6_scientific_execution':False,'formal_scientific_authorization':False,'reason':'Stage execution records include candidates and rejected materialization; they do not certify the original L0–L6 scientific chain.'}
        save('scientific_stage_completion.json',manifest['scientific_stage_completion'])
        manifest['dataset_export']=export_attempt_dataset(manifest,dest,dest/'dataset',pairs=pairs)
        event('dataset_export','executed','Versioned native scientific tables, including failed/negative attempts.',{'dataset_version':manifest['dataset_export']['dataset_version']})
        event('atlas_export','executed','All attempted cases produce a hash-bound review package and queue item.')
        manifest['stage_chain_tip']=tip
        costs=self.budget.snapshot(cid)
        save('final_manifest.json',manifest);save('costs.json',costs)
        known={a['role'] for a in artifacts}
        for path in sorted(dest.rglob('*')):
            if path.is_file() and path.suffix in ('.json','.jsonl','.txt') and str(path.relative_to(dest)) not in known:
                raw=path.read_text();artifacts.append({'case_id':cid,'role':str(path.relative_to(dest)),'sha256':hashlib.sha256(raw.encode()).hexdigest(),'utf8':raw})
        package=make_case_package(manifest,pairs=pairs,artifacts=artifacts,costs=costs)
        durable(dest/'review_package.json',canonical_json(package)+'\n')
        durable(dest/'manual_review_queue.jsonl',''.join(canonical_json(r)+'\n' for r in case_review_rows(package)))
        return package
