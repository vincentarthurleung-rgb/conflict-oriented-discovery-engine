"""Authentic historical pins; software transport only, no scientific approvals."""
from pathlib import Path
import json
from code_engine.discovery.ai_review_shadow import content_hash, file_hash
import hashlib
from code_engine.orchestration.pilot_native_representation import VERSION, COORDINATES
from tests.pilot_semantic_support import cross_semantic, trib_comparison
from tests.pilot_inclusion_support import R, E, pin, write

HIST=R/'runs/20260902_single_source_provider_extraction_smoke_pmc10515557_v1'


def manifest(path):
    m=json.loads((HIST/'artifacts/provider_request_manifest.json').read_text())
    packet=json.loads((E/'E3/right/evidence_packet.json').read_text())
    native=HIST/'artifacts/validated_observations.jsonl'
    rows=[json.loads(x) for x in native.read_text().splitlines()]
    inventory=[{'observation_id':f['observation_id'],'formal_sha256':content_hash(f),
        'endpoint_raw':f['measurement']['endpoint_raw'],'design_type_raw':f['experiment']['design_type_raw'],
        'cohort_raw':f['experiment']['cohort_raw']} for f in rows]
    cfg={'schema_version':VERSION,'original_xml':pin(R/m['source_fulltext_path']),
        'article_json':pin(Path(packet['source']['article_path'])),'native_jsonl':pin(native),
        'provider_request_manifest':pin(HIST/'artifacts/provider_request_manifest.json'),
        'source_payload':pin(R/m['source_payload_sent_path']),'rendered_prompt':pin(R/m['rendered_prompt_path']),
        'raw_provider_response':pin(HIST/'artifacts/raw_provider_response.txt'),
        'projection_producer':pin(E/'explore_three_pairs.py'),
        'block_producer':pin(R/'tools/run_single_source_provider_extraction_smoke_pmc10515557_v1.py'),
        'native_producer':pin(R/'tools/generate_single_source_provider_extraction_smoke_pmc10515557_v1.py'),
        'source_representation':'JATS_XML','projection_representation':'frozen_jats_paragraph_projection',
        'projection_transform':'itertext_whitespace_collapse_v1','coordinate_mapping':COORDINATES,
        'historical_run_id':HIST.name,'source_identity':{'pmid':'37744426','pmcid':'PMC10515557','doi':None},
        'record_inventory':inventory}
    article=json.loads(Path(packet['source']['article_path']).read_text())
    cfg['cohort_dependency']={'identity':'source_bound:PMC10515557:parent_archival_NB_cohort',
        'section_index':3,'source_section_text_sha256':hashlib.sha256(article['sections'][3]['text'].encode()).hexdigest(),
        'native_observation_ids':[f['observation_id'] for f in rows],
        'authority':'source_bound_Work_provisional_not_independent',
        'reason':'Frozen Methods identify one archival 56-patient parent cohort; original all/risk/stage analyses remain dependent, not independent publications or replications'}
    return pin(write(Path(path)/'native_representation_manifest.json',cfg))


def trib_native(path):
    b,c,req=cross_semantic(trib_comparison,path)
    req['model_stages'].pop('source_grounded_linkage',None)
    req['native_representation_handoffs']={'PMC10515557':manifest(path)}
    return b,c,req
