"""Synthetic path-scope regressions for the prospective alpha3.18A.5 parser."""

import pytest

from scripts.search_plan_v24_alpha318a5_primary_identity import bind_primary_citation


def article(pmid="123", direct_pmcids=("PMC123",), direct_dois=("10.1/main",),
            direct_pubmed=None, references=""):
    ids = "".join(f'<ArticleId IdType="pmc">{x}</ArticleId>' for x in direct_pmcids)
    ids += "".join(f'<ArticleId IdType="doi">{x}</ArticleId>' for x in direct_dois)
    if direct_pubmed is not None:
        ids += f'<ArticleId IdType="pubmed">{direct_pubmed}</ArticleId>'
    return (f'<PubmedArticle><MedlineCitation><PMID>{pmid}</PMID>'
            '<Article><Journal><JournalIssue><PubDate><Year>2020</Year></PubDate>'
            '</JournalIssue></Journal><PublicationTypeList><PublicationType>Journal Article'
            '</PublicationType></PublicationTypeList></Article></MedlineCitation>'
            f'<PubmedData><ArticleIdList>{ids}</ArticleIdList>{references}</PubmedData>'
            '</PubmedArticle>')


def response(*articles):
    return ('<PubmedArticleSet>' + ''.join(articles) + '</PubmedArticleSet>').encode()


def reference(pmc, doi):
    return ('<ReferenceList><Reference><ArticleIdList>'
            f'<ArticleId IdType="pmc">{pmc}</ArticleId>'
            f'<ArticleId IdType="doi">{doi}</ArticleId>'
            '</ArticleIdList></Reference></ReferenceList>')


def test_direct_pmcid_and_doi_ignore_reference_ids():
    result = bind_primary_citation(response(article(references=reference('PMC456', '10.2/ref'))), '123')
    assert result['pmcid'] == 'PMC123'
    assert result['doi'] == '10.1/main'
    assert len(result['reference_article_ids']) == 2
    assert len(result['legacy_pmcid_values']) == 2
    assert len(result['legacy_doi_values']) == 2


def test_many_and_nested_reference_lists_do_not_contaminate():
    nested = reference('PMC456', '10.2/ref') + '<ReferenceList>' + reference('PMC789', '10.3/ref') + '</ReferenceList>'
    result = bind_primary_citation(response(article(references=nested)), '123')
    assert result['direct_pmcid_values'] == ['PMC123']
    assert result['direct_doi_values'] == ['10.1/main']
    assert len(result['reference_article_ids']) == 4


def test_matching_direct_pubmed_id():
    assert bind_primary_citation(response(article(direct_pubmed='123')), '123')['metadata_state'] == 'RESOLVED'


def test_mismatching_direct_pubmed_id_fails_closed():
    with pytest.raises(ValueError, match='PRIMARY_CITATION_PMID_IDENTITY_MISMATCH'):
        bind_primary_citation(response(article(direct_pubmed='999')), '123')


def test_two_distinct_direct_pmcids_stay_ambiguous():
    result = bind_primary_citation(response(article(direct_pmcids=('PMC123', 'PMC456'))), '123')
    assert result['pmcid'] is None
    assert result['metadata_unresolved_reasons'] == ['PMCID_MISSING_OR_AMBIGUOUS']


def test_missing_direct_pmcid_stays_unresolved():
    result = bind_primary_citation(response(article(direct_pmcids=(), references=reference('PMC456', '10.2/ref'))), '123')
    assert result['pmcid'] is None
    assert result['metadata_unresolved_reasons'] == ['PMCID_MISSING_OR_AMBIGUOUS']


def test_multi_article_response_binds_by_medline_pmid_not_order():
    result = bind_primary_citation(response(article(pmid='999', direct_pmcids=('PMC999',)), article()), '123')
    assert result['pmcid'] == 'PMC123'


def test_absent_expected_pmid_fails_closed():
    with pytest.raises(ValueError, match='PRIMARY_CITATION_RECORD_MISSING'):
        bind_primary_citation(response(article(pmid='999')), '123')


def test_duplicate_expected_pmid_fails_closed():
    with pytest.raises(ValueError, match='PRIMARY_CITATION_RECORD_DUPLICATE'):
        bind_primary_citation(response(article(), article()), '123')
