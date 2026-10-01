"""Synthetic article-level JATS license URI path and conflict tests."""

import pytest

from scripts.search_plan_v24_alpha318a6_license_extraction import (
    construction_oa_v2, extract_license_v2)


BY = 'https://creativecommons.org/licenses/by/4.0/'
BY_SA = 'https://creativecommons.org/licenses/by-sa/4.0/'
BY_NC = 'https://creativecommons.org/licenses/by-nc/4.0/'
CC0 = 'https://creativecommons.org/publicdomain/zero/1.0/'


def jats(licenses, extra=''):
    return (f'<article xmlns:xlink="http://www.w3.org/1999/xlink" '
            f'xmlns:ali="http://www.niso.org/schemas/ali/1.0/">'
            f'<front><article-meta><permissions>{licenses}</permissions></article-meta></front>'
            f'{extra}</article>').encode()


def direct(uri):
    return f'<license xlink:href="{uri}"><license-p>License text</license-p></license>'


def link(uri):
    return f'<license><license-p><ext-link xlink:href="{uri}">License</ext-link></license-p></license>'


def ali(*uris):
    refs = ''.join(f'<ali:license_ref start_date="2020-01-01">{x}</ali:license_ref>' for x in uris)
    return f'<license>{refs}</license>'


@pytest.mark.parametrize('xml,expected_class,path', [
    (jats(direct(BY)), 'CC_BY', 'A'),
    (jats(link(BY)), 'CC_BY', 'C'),
    (jats(ali(BY_SA)), 'CC_BY_SA', 'B'),
    (jats(direct(CC0)), 'CC0', 'A'),
])
def test_whitelisted_machine_paths(xml, expected_class, path):
    result = extract_license_v2(xml)
    assert result['state'] == 'ELIGIBLE'
    assert result['normalized_license_class'] == expected_class
    assert result['representation_paths'] == [path]


def test_direct_and_ext_link_same_class_consistent():
    xml = jats(f'<license xlink:href="http://www.creativecommons.org/licenses/by/4.0">'
               f'<license-p><ext-link xlink:href="{BY}">License</ext-link></license-p></license>')
    result = extract_license_v2(xml)
    assert result['state'] == 'ELIGIBLE'
    assert result['path_a_c_class_consistent'] is True
    assert result['candidate_count'] == 2
    assert len({item['normalized_uri'] for item in result['candidates']}) == 1


def test_direct_and_ext_link_conflict_fails_closed():
    xml = jats(f'<license xlink:href="{BY}"><license-p>'
               f'<ext-link xlink:href="{BY_NC}">License</ext-link></license-p></license>')
    result = extract_license_v2(xml)
    assert result['state'] == 'UNRESOLVED'
    assert result['reason'] == 'LICENSE_MACHINE_URI_CONFLICT'
    assert result['path_a_c_class_consistent'] is False


def test_multiple_ali_same_class_and_start_date_preserved():
    result = extract_license_v2(jats(ali(BY, 'http://www.creativecommons.org/licenses/by/3.0')))
    assert result['state'] == 'ELIGIBLE'
    assert result['normalized_license_class'] == 'CC_BY'
    assert [item['start_date'] for item in result['candidates']] == ['2020-01-01'] * 2


def test_multiple_ali_different_class_unresolved():
    result = extract_license_v2(jats(ali(BY, BY_NC)))
    assert result['state'] == 'UNRESOLVED'
    assert result['reason'] == 'LICENSE_MACHINE_URI_CONFLICT'


def test_prose_without_machine_uri_unresolved():
    result = extract_license_v2(jats('<license><license-p>Creative Commons Attribution license</license-p></license>'))
    assert result['state'] == 'UNRESOLVED'
    assert result['reason'] == 'LICENSE_MACHINE_URI_UNRESOLVED'


def test_nonwhitelisted_machine_cc_ineligible():
    result = extract_license_v2(jats(link(BY_NC)))
    assert result['state'] == 'INELIGIBLE'
    assert construction_oa_v2('PMC123', True, jats(link(BY_NC)))['state'] == 'CONSTRUCTION_OA_INELIGIBLE'


def test_figure_level_license_does_not_classify_article():
    result = extract_license_v2(jats('<license><license-p>Article prose</license-p></license>',
        f'<body><fig><permissions>{direct(BY)}</permissions></fig></body>'))
    assert result['state'] == 'UNRESOLVED'
    assert result['candidate_count'] == 0


def test_bibliography_link_does_not_classify_article():
    result = extract_license_v2(jats('<license><license-p>Article prose</license-p></license>',
        f'<back><ref-list><ref><ext-link xlink:href="{BY}">CC</ext-link></ref></ref-list></back>'))
    assert result['state'] == 'UNRESOLVED'
    assert result['candidate_count'] == 0


def test_oa_subset_negative_stays_ineligible_even_with_whitelisted_jats():
    result = construction_oa_v2('PMC123', False, jats(link(BY)))
    assert result == {'state': 'CONSTRUCTION_OA_INELIGIBLE', 'reason': 'NOT_IN_PMC_OA_SUBSET'}
