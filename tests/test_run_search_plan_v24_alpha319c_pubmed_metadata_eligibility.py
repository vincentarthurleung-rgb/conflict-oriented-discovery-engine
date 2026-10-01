import pytest

from scripts.run_search_plan_v24_alpha319c_pubmed_metadata_eligibility import parse_metadata


def xml(pmid="12345", ids='''<ArticleId IdType="pubmed">12345</ArticleId>
    <ArticleId IdType="pmc">PMC987</ArticleId><ArticleId IdType="doi">10.1/x</ArticleId>''',
        year="2024", refs=""):
    return f'''<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>{pmid}</PMID>
      <Article><Journal><JournalIssue><PubDate><Year>{year}</Year></PubDate>
      </JournalIssue></Journal><PublicationTypeList><PublicationType>Journal Article</PublicationType>
      </PublicationTypeList></Article>{refs}</MedlineCitation><PubmedData>
      <ArticleIdList>{ids}</ArticleIdList><ReferenceList><Reference><ArticleIdList>
      <ArticleId IdType="pmc">PMC999</ArticleId><ArticleId IdType="doi">10.1/wrong</ArticleId>
      </ArticleIdList></Reference></ReferenceList></PubmedData></PubmedArticle></PubmedArticleSet>'''.encode()


def test_direct_primary_ids_only():
    result = parse_metadata(xml(), "12345")
    assert result["pmcid"] == "PMC987"
    assert result["doi"] == "10.1/x"
    assert result["date_state"] == "CLEAR"
    assert result["reference_article_ids_scanned"] is False
    assert len(result["direct_primary_article_ids"]) == 3


def test_mismatched_primary_pmid_fails_source():
    with pytest.raises(ValueError, match="PRIMARY_CITATION_PMID"):
        parse_metadata(xml(pmid="67890"), "12345")


def test_ambiguous_direct_pmcid_is_unresolved_under_frozen_contract():
    ids = '<ArticleId IdType="pmc">PMC987</ArticleId><ArticleId IdType="pmc">PMC654</ArticleId>'
    result = parse_metadata(xml(ids=ids), "12345")
    assert result["metadata_state"] == "UNRESOLVED"
    assert result["pmcid"] is None
    assert result["metadata_unresolved_reasons"] == ["PMCID_MISSING_OR_AMBIGUOUS"]


def test_out_of_cohort_is_ineligible():
    assert parse_metadata(xml(year="2023"), "12345")["date_state"] == "INELIGIBLE"


def test_updateof_relationship_is_direct_citation():
    refs = '<CommentsCorrectionsList><CommentsCorrections RefType="UpdateOf"><PMID>77</PMID></CommentsCorrections></CommentsCorrectionsList>'
    result = parse_metadata(xml(refs=refs), "12345")
    assert result["correction_relationships"] == [
        {"ref_type": "UpdateOf", "linked_pmid": "77", "ref_source": None}]
