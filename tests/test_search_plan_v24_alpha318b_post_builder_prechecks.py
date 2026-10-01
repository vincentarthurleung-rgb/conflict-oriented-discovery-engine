"""Synthetic no-provider checks for the preregistered Builder-to-Quality boundary."""

import json
from pathlib import Path

import pytest

from scripts import search_plan_v24_alpha318b_post_builder_prechecks as checks
from scripts import search_plan_v24_alpha318b_preregister_builder_execution_offline as prereg


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / 'runs/20260927_search_plan_v24_dev_alpha3_17c_builder_cardinality_reconciliation_offline'
                     / 'proposition_builder_output_schema_v2.json').read_text())['schema']
TOKEN = 'src_' + 'a' * 64
BODY = 'Treatment with agent reduces cellular response in culture.'


def candidate(text=BODY, start=0):
    return {'actor_or_intervention': 'agent', 'action': 'treatment',
            'relation_direction': 'DECREASES', 'response_or_endpoint': 'cellular response',
            'biological_unit': 'cultured cells', 'species': None,
            'intrinsic_conditioning': None, 'intrinsic_therapy_context': None,
            'intrinsic_disease_or_genotype_context': None,
            'neutral_proposition': 'agent decreases cellular response in cultured cells',
            'construction_evidence_span': {'source_field': 'body', 'exact_text': text,
                                           'start_offset': start, 'end_offset': start + len(text)}}


def document():
    return {'body_text': BODY, 'paragraphs': [{'section_path': [1], 'ordinal': 1,
             'text': BODY, 'start_offset': 0, 'end_offset': len(BODY),
             'span_id': 'spanv1_' + checks.source.digest([
                 checks.source.SPAN_VERSION, TOKEN, [1], 1,
                 checks.source.sha_text(BODY)])}]}


def test_zero_is_valid_and_not_a_retry_trigger():
    raw = json.dumps({'source_record_token': TOKEN, 'candidates': []}).encode()
    result = checks.validate_builder_response(raw, TOKEN, SCHEMA)
    assert result['candidates'] == []
    assert checks.precheck_candidates(result, document(), 'Private title')[
        'quality_adjudication_input_candidates'] == 0


def test_schema_invalid_and_wrong_source_fail():
    with pytest.raises(ValueError, match='BUILDER_SCHEMA_ARRAY_LENGTH'):
        checks.validate_builder_response(json.dumps({'source_record_token': TOKEN,
            'candidates': [candidate()] * 4}).encode(), TOKEN, SCHEMA)
    with pytest.raises(ValueError, match='BUILDER_RESPONSE_SOURCE_IDENTITY_MISMATCH'):
        checks.validate_builder_response(json.dumps({'source_record_token': TOKEN,
            'candidates': []}).encode(), 'src_' + 'b' * 64, SCHEMA)


def test_exact_dedup_grounding_and_canonical_identity():
    parsed = checks.validate_builder_response(json.dumps({'source_record_token': TOKEN,
        'candidates': [candidate(), candidate()]}).encode(), TOKEN, SCHEMA)
    checked = checks.precheck_candidates(parsed, document(), 'Unrelated private title')
    assert checked['exact_duplicate_candidates_removed'] == 1
    assert checked['grounding_reference_failures'] == 0
    assert checked['quality_adjudication_input_candidates'] == 1
    assert checked['candidate_records_private'][0]['candidate_id'].startswith('pcv2_')


def test_invalid_body_reference_excluded_without_repair():
    bad = candidate(text='not in source')
    parsed = checks.validate_builder_response(json.dumps({'source_record_token': TOKEN,
        'candidates': [bad]}).encode(), TOKEN, SCHEMA)
    checked = checks.precheck_candidates(parsed, document(), 'Private title')
    assert checked['grounding_reference_failures'] == 1
    assert checked['quality_adjudication_input_candidates'] == 0


def test_quality_payload_hides_source_token_and_anchor():
    parsed = checks.validate_builder_response(json.dumps({'source_record_token': TOKEN,
        'candidates': [candidate()]}).encode(), TOKEN, SCHEMA)
    checked = checks.precheck_candidates(parsed, document(), 'Unrelated private title')
    payload = checks.build_quality_payload(TOKEN, checked['survivors_private'],
        document(), {'pmid': '12345678', 'pmcid': 'PMC123', 'doi': '10.1234/private'})
    serialized = json.dumps(payload)
    assert TOKEN not in serialized
    assert 'spanv1_' not in serialized
    assert payload['source_group_id'].startswith('qgv2_')


def test_private_jats_identity_extracts_only_front_matter_for_firewall():
    jats = (b'<article><front><journal-meta><journal-title-group><journal-title>Private Journal'
            b'</journal-title></journal-title-group></journal-meta><article-meta><title-group>'
            b'<article-title>Private Article Title</article-title></title-group><contrib-group>'
            b'<contrib contrib-type="author"><name><given-names>Ada</given-names><surname>Smith'
            b'</surname></name></contrib></contrib-group></article-meta></front></article>')
    private = checks.private_identity_from_jats(jats, '12345678', 'PMC123', None)
    assert private['title_1'] == 'Private Article Title'
    assert private['journal_1'] == 'Private Journal'
    assert private['author_surname_1'] == 'Smith'


def test_frozen_28_source_request_preflight_is_offline_and_exact():
    frozen = prereg.preflight()
    assert len(frozen['sources']) == len(frozen['requests']) == 28
    assert frozen['quality_protocol_root'] == prereg.QUALITY_SHA
    assert [row['source_token'] for row in frozen['sources']] == [
        row['source_token'] for row in frozen['requests']]


def test_quality_request_uses_frozen_machine_appendix_and_no_hidden_identity():
    parsed = checks.validate_builder_response(json.dumps({'source_record_token': TOKEN,
        'candidates': [candidate()]}).encode(), TOKEN, SCHEMA)
    checked = checks.precheck_candidates(parsed, document(), 'Unrelated private title')
    payload = checks.build_quality_payload(TOKEN, checked['survivors_private'], document(),
        {'pmid': '12345678', 'pmcid': 'PMC123', 'doi': '10.1234/private'})
    quality_dir = prereg.QUALITY_DIR
    schema = json.loads((quality_dir / 'proposition_quality_adjudication_v2_schema.json').read_text())['schema']
    appendix = json.loads((quality_dir / 'quality_machine_output_contract.json').read_text())['appendix_utf8']
    request = checks.build_quality_request(payload, schema,
        (quality_dir / 'quality_adjudicator_system_prompt.txt').read_text(),
        (quality_dir / 'quality_adjudicator_user_prompt_template.txt').read_text(), appendix)
    assert request['stream'] is False
    assert appendix in request['messages'][1]['content']
    assert TOKEN not in json.dumps(request)
