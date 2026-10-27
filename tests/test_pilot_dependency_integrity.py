"""Bounded Batch 1 regressions; retained source evidence and software transports."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil

import pytest

from code_engine.discovery.ai_review_shadow import content_hash, file_hash
from code_engine.orchestration.pilot_backend import PilotProviderTransport, RetryableProviderFailure
from code_engine.orchestration.pilot_budget import ModelBudget, BudgetStop
from code_engine.orchestration.pilot_case import PilotCaseExecutor, CaseIntegrity
from code_engine.orchestration.pilot_dependencies import DEPENDENCIES, REPOSITORY_DEPENDENCIES, DEFAULT_REVIEW_PROMPT
from code_engine.orchestration.pilot_model_cache import SourceModelCache
from code_engine.system_b.annotation_schemas.registry import canonical_json
from tests.pilot_offline_support import request
from tests.test_pilot_unlimited_integration import existing_backend, offline, seen


def req(cid):
    r=request(cid);r.pop('source_count')
    r['model_stages']={s:'review' if s=='ai_review' else 'batch' for s in r['model_stages']}
    return r


def mirror_dependencies(backend,tmp_path):
    root=tmp_path/'dependency_mirror'
    paths=[Path('src/code_engine')/p for group in DEPENDENCIES.values() for p in group]
    paths += [Path(p) for p in (*REPOSITORY_DEPENDENCIES,DEFAULT_REVIEW_PROMPT)]
    for p in paths:
        dest=root/p;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
    backend.repository=root
    return root


def tree_hashes(root):
    return {str(p.relative_to(root)):file_hash(p) for p in root.rglob('*') if p.is_file()}


def test_same_path_prompt_content_invalidates_completed_package(tmp_path,seen):
    backend,cfg=existing_backend(tmp_path)
    p=tmp_path/'software_prompt.txt';p.write_text('SOFTWARE VERSION A');backend.review_prompt=str(p)
    before=backend.fingerprint
    executor=PilotCaseExecutor(tmp_path/'cases',seen,ModelBudget(tmp_path/'b.db',cfg,offline=True),backend)
    old=executor.run(req('PROMPT'));old_hashes=tree_hashes(tmp_path/'cases/PROMPT')
    p.write_text('SOFTWARE VERSION B')
    assert backend.fingerprint!=before
    with pytest.raises(CaseIntegrity,match='new immutable revision'):executor.run(req('PROMPT'))
    assert old_hashes==tree_hashes(tmp_path/'cases/PROMPT')
    assert old['run_manifest']['effective_dependencies_sha256']==before


@pytest.mark.parametrize('dependency',[
    'fulltext/fulltext_l1_v2.py','fulltext/fulltext_l1_draft_hydration_v3.py',
    'extraction_assets/experimental_core/assembly.py','discovery/ai_review_shadow.py',
    'fulltext/registries/experimental_semantics_registry_v1.json',
    'fulltext/evidence_projection.py','orchestration/pilot_dataset.py',
])
def test_derived_dependency_drift_rejects_old_package_but_reuses_raw(tmp_path,seen,dependency):
    backend,cfg=existing_backend(tmp_path);root=mirror_dependencies(backend,tmp_path)
    cache=SourceModelCache(tmp_path/'shared');budget=ModelBudget(tmp_path/'b.db',cfg,offline=True)
    ex=PilotCaseExecutor(tmp_path/'cases',seen,budget,backend,model_cache=cache)
    old=ex.run(req('ORIGINAL'));before=tree_hashes(tmp_path/'cases/ORIGINAL');sends=len(backend.transport.calls)
    p=root/'src/code_engine'/dependency;p.write_bytes(p.read_bytes()+b'\n')
    with pytest.raises(CaseIntegrity,match='input_drift'):ex.run(req('ORIGINAL'))
    assert tree_hashes(tmp_path/'cases/ORIGINAL')==before
    derived=[];original=backend.derive_response
    def current(*args,**kwargs):derived.append(args[0]);return original(*args,**kwargs)
    backend.derive_response=current
    new=ex.run(req('NEW-REVISION'))
    assert new['terminal_state']==old['terminal_state']
    assert new['run_manifest']['effective_dependencies_sha256']!=old['run_manifest']['effective_dependencies_sha256']
    assert len(derived)==6 and len(backend.transport.calls)==sends
    assert new['costs']['accounted_nusd']==0
    entries=[json.loads(p.read_text()) for p in cache.root.glob('raw_v1_*.json')]
    assert len(entries)==6 and all('raw_provider_response' in e and 'response' not in e for e in entries)


def test_raw_identity_uses_exact_request_provider_and_fixture_namespace(tmp_path):
    backend,_=existing_backend(tmp_path);body={'model':'software-fixture','max_tokens':1,'messages':[]}
    one=backend.raw_request_identity('DeepSeek',body)
    assert one==backend.raw_request_identity('deepseek',body)
    assert one!=backend.raw_request_identity('deepseek',{**body,'max_tokens':2})
    backend.fixture=False
    assert one!=backend.raw_request_identity('deepseek',body)


def test_unknown_dispatch_is_not_automatically_resent_even_after_dependency_change(tmp_path,seen):
    backend,cfg=existing_backend(tmp_path);root=mirror_dependencies(backend,tmp_path);calls=[]
    def timeout(*a):calls.append(1);raise TimeoutError('SOFTWARE unknown dispatch fixture')
    backend.transport.send=timeout
    ex=PilotCaseExecutor(tmp_path/'cases',seen,ModelBudget(tmp_path/'b.db',cfg,offline=True),backend)
    a=ex.run(req('UNKNOWN'));assert a['terminal_state']=='MODEL_FAILED' and len(calls)==1
    assert 'unknown_paid_dispatch' in a['reason']
    p=root/'src/code_engine/extraction_assets/experimental_core/assembly.py';p.write_bytes(p.read_bytes()+b'\n')
    b=ex.run(req('ANOTHER'));assert b['terminal_state']=='BUDGET_STOP' and len(calls)==1
    assert 'unreconciled_prior_dispatch' in b['reason']


def test_unbindable_legacy_pending_dispatch_stops_new_raw_cache(tmp_path):
    cache=SourceModelCache(tmp_path);cache.intent('old_derived_key','OLD','request')
    with pytest.raises(BudgetStop,match='legacy_dispatch'):cache.check_unbound_legacy_dispatches()


def test_known_429_rejection_can_use_only_reserved_retry(tmp_path,seen):
    backend,cfg=existing_backend(tmp_path);send=backend.transport.send;rejections=[]
    def once(*args):
        if not rejections:
            rejections.append(1);raise RetryableProviderFailure('SOFTWARE known 429',safe_to_retry=True)
        return send(*args)
    backend.transport.send=once
    p=PilotCaseExecutor(tmp_path/'cases',seen,ModelBudget(tmp_path/'b.db',cfg,offline=True),backend).run(req('REJECTED'))
    assert p['terminal_state']=='NO_CONTRADICTION_AFTER_COMPARISON'
    assert len(p['costs']['requests'])==7
    assert all(r['attempt']<=2 for r in p['costs']['requests'])


def test_unverifiable_receipt_preserves_response_but_does_not_allow_reuse(tmp_path,seen):
    backend,cfg=existing_backend(tmp_path);send=backend.transport.send
    def invalid(*args):raw=send(*args);raw['usage']={};return raw
    backend.transport.send=invalid
    cache=SourceModelCache(tmp_path/'cache')
    p=PilotCaseExecutor(tmp_path/'cases',seen,ModelBudget(tmp_path/'b.db',cfg,offline=True),backend,model_cache=cache).run(req('BAD-USAGE'))
    assert p['terminal_state']=='BUDGET_STOP'
    assert list(cache.root.glob('*.captured')) and list(cache.root.glob('*.pending'))
    assert not list(cache.root.glob('*.json'))


def test_conditional_linkage_requires_actual_response_and_supported_v3(tmp_path):
    from tests.test_linkage_candidate_component_probe import retained_provider_v3
    from code_engine.orchestration.component_probe import conditional_linkage_request
    a,p,b,raw,validated,ctx=retained_provider_v3(tmp_path)
    kwargs=dict(source_artifact=p,source_blocks=b,actual_v3_response_file=raw,validated_v3_file=validated,hydration_context=ctx)
    with pytest.raises(ValueError,match='context_required'):conditional_linkage_request(a,**{**kwargs,'hydration_context':None})
    wrong=tmp_path/'unrelated.json';wrong.write_text('{}')
    with pytest.raises(ValueError):conditional_linkage_request(a,**{**kwargs,'actual_v3_response_file':wrong})
    empty=tmp_path/'empty.json';empty.write_text(json.dumps({'schema_version':json.loads(raw.read_text())['schema_version'],'experimental_observations':[]}))
    with pytest.raises(ValueError,match='response_observation'):conditional_linkage_request(a,**{**kwargs,'actual_v3_response_file':empty})
    # A copied completed Core cannot stand in for its claimed model response.
    with pytest.raises(ValueError):conditional_linkage_request(a,**{**kwargs,'actual_v3_response_file':validated})
    truncated=tmp_path/'truncated.json';truncated.write_text(json.dumps({'choices':[{'finish_reason':'length','message':{'content':raw.read_text()}}]}))
    with pytest.raises(ValueError,match='not_complete'):conditional_linkage_request(a,**{**kwargs,'actual_v3_response_file':truncated})


def test_genuine_retained_raw_response_reuse_is_distinct_from_hydration(tmp_path):
    from tests.test_linkage_candidate_component_probe import retained_provider_v3
    from code_engine.fulltext.fulltext_l1_v2 import parse_draft_response
    from code_engine.fulltext.fulltext_l1_draft_hydration_v3 import hydrate_draft_response_v3
    a,source,blocks,raw_path,validated,ctx=retained_provider_v3(tmp_path)
    # Retained provider text, not a generated fixture; origin is explicitly the
    # historical diagnostic, not an alleged response to today's routed request.
    base=raw_path.parent;manifest=json.loads((base/'provider_request_manifest.json').read_text())
    exact_prompt=Path(manifest['rendered_prompt_path']).read_bytes()
    assert hashlib.sha256(exact_prompt).hexdigest()==manifest['rendered_prompt_sha256']
    identity=content_hash({'historical_manifest_sha256':file_hash(base/'provider_request_manifest.json'),'exact_prompt_sha256':hashlib.sha256(exact_prompt).hexdigest()})
    cache=SourceModelCache(tmp_path/'historical_diagnostic_cache')
    cache.store(identity,{'historical_provider_text':raw_path.read_text(),'historical_provider_text_sha256':file_hash(raw_path),'scope':'retained genuine response parser replay; not today request'})
    reused=cache.load(identity)
    parsed=hydrate_draft_response_v3(parse_draft_response(json.loads(reused['historical_provider_text'])),ctx)
    assert a['envelope']['ExperimentalObservationV3'] in parsed.formal_response['experimental_observations']


def test_transport_sends_identical_prepared_bytes_without_network(tmp_path,monkeypatch):
    import httpx
    from code_engine.orchestration.component_probe import prepare_v3_component_request
    from tests.test_fulltext_window_core_integration import ar_view
    from code_engine.fulltext.source_windows import grouped_plan_windows,extraction_block
    a=ar_view();w=next(w for w in grouped_plan_windows(a,content_hash(a))['windows'] if any(f['section_index']==5 for f in w['fragments']))
    prepared=prepare_v3_component_request(a,extraction_block(w,a['pmcid'],a['pmid']),question_domain='general_biomedical')
    exact=canonical_json(prepared['body']).encode();captured=[]
    def post(url,*,content,headers):
        captured.append(content)
        return httpx.Response(200,json={'SOFTWARE_ONLY':'not an extraction'},request=httpx.Request('POST',url))
    monkeypatch.setenv('DEEPSEEK_API_KEY','SOFTWARE_DUMMY_NEVER_SENT')
    PilotProviderTransport(execute_authorized=True,post=post).send('deepseek',prepared['body'])
    assert captured==[exact] and hashlib.sha256(exact).hexdigest()==prepared['body_sha256']
