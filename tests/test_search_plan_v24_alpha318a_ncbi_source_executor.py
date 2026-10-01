"""Offline executor preflight and synthetic parsing checks; no network."""

import json

import pytest

from scripts import search_plan_v24_alpha318a_execute_ncbi_source_acquisition as run


def test_authoritative_manifest_and_all_references_match():
    manifest = run.verify_before_network()
    assert len(manifest["queries"]) == 6
    assert manifest["network_scope"]["allowed_host"] == "eutils.ncbi.nlm.nih.gov"


def test_esearch_page_and_malformed_identifier():
    raw = json.dumps({"esearchresult": {"count": "2", "retstart": "0",
                                        "idlist": ["123", "456"]}}).encode()
    assert run.parse_esearch(raw, 0, 50) == (2, ["123", "456"])
    with pytest.raises(ValueError):
        run.parse_esearch(raw.replace(b'"123"', b'"00123"'), 0, 50)


def test_oa_subset_exact_identity():
    yes = b'{"esearchresult":{"count":"1","idlist":["123"]}}'
    no = b'{"esearchresult":{"count":"0","idlist":[]}}'
    assert run.parse_subset(yes, "PMC123") is True
    assert run.parse_subset(no, "PMC123") is False
    assert run.parse_subset(yes, "PMC124") is None


def test_metadata_ignores_date_completed_and_extracts_correction_direction():
    raw = b'''<PubmedArticleSet><PubmedArticle><MedlineCitation>
    <PMID>12345678</PMID><DateCompleted><Year>2025</Year></DateCompleted>
    <Article><Journal><JournalIssue><PubDate><Year>2020</Year></PubDate></JournalIssue></Journal>
    <PublicationTypeList><PublicationType>Journal Article</PublicationType></PublicationTypeList></Article>
    <CommentsCorrectionsList><CommentsCorrections RefType="RetractionIn">
    <RefSource>Private citation</RefSource></CommentsCorrections></CommentsCorrectionsList>
    </MedlineCitation><PubmedData><ArticleIdList><ArticleId IdType="pmc">PMC123</ArticleId>
    <ArticleId IdType="doi">10.1000/example</ArticleId></ArticleIdList></PubmedData>
    </PubmedArticle></PubmedArticleSet>'''
    result = run.parse_metadata(raw, "12345678")
    assert result["publication_year"] == 2020
    assert result["pmcid"] == "PMC123"
    assert result["correction_relationships"][0]["ref_type"] == "RetractionIn"
    assert result["correction_relationships"][0]["linked_pmid"] is None


def test_preliminary_publication_type_gate():
    assert run.preliminary_type(["Journal Article"])["state"] == "PRELIMINARY_TYPE_ACCEPTED"
    assert run.preliminary_type(["Journal Article", "Retracted Publication"])["state"] == "SOURCE_TYPE_INELIGIBLE"
    assert run.preliminary_type(["Future Type"])["state"] == "SOURCE_TYPE_UNRESOLVED"


def test_canonical_article_identity():
    raw = b'<pmc-articleset><article><front><article-meta><article-id pub-id-type="pmc">123</article-id></article-meta></front><body><p>Text.</p></body></article></pmc-articleset>'
    assert run.canonical_article(raw, "PMC123").startswith(b"<article>")
    with pytest.raises(ValueError):
        run.canonical_article(raw, "PMC124")
