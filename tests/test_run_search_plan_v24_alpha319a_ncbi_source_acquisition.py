"""Offline regression checks for the frozen 19A runtime boundary."""
import pytest

from scripts import run_search_plan_v24_alpha319a_ncbi_source_acquisition as run


def xml_metadata(year="2024", extra_year=""):
    return (f"<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>123</PMID>"
            f"<Article><Journal><JournalIssue><PubDate><Year>{year}</Year></PubDate>"
            f"</JournalIssue></Journal><ArticleDate><Year>{extra_year or year}</Year></ArticleDate>"
            f"<PublicationTypeList><PublicationType>Journal Article</PublicationType>"
            f"</PublicationTypeList></Article></MedlineCitation><PubmedData>"
            f"<ArticleIdList><ArticleId IdType='pmc'>PMC123</ArticleId>"
            f"<ArticleId IdType='doi'>10.1/current</ArticleId></ArticleIdList>"
            f"<ReferenceList><Reference><ArticleIdList>"
            f"<ArticleId IdType='pmc'>PMC999</ArticleId>"
            f"<ArticleId IdType='doi'>10.1/reference</ArticleId>"
            f"</ArticleIdList></Reference></ReferenceList></PubmedData>"
            f"</PubmedArticle></PubmedArticleSet>").encode()


def test_pre_network_integrity_gate():
    state = run.preflight()
    assert len(state["queries"]) == 6
    assert len(state["seen_pmids"]) == 1041
    assert state["manifest"]["material_runtime_policy_unresolved_count"] == 0


def test_new_cohort_date_and_direct_current_article_ids():
    record = run.bind_metadata(xml_metadata(), "123")
    assert record["metadata_state"] == "RESOLVED"
    assert record["publication_year"] == 2024
    assert record["date_state"] == "ELIGIBLE"
    assert record["pmcid"] == "PMC123"
    assert record["doi"] == "10.1/current"
    assert {x["value"] for x in record["reference_article_ids"]} == {"PMC999", "10.1/reference"}


def test_date_ambiguity_and_out_of_cohort():
    assert run.bind_metadata(xml_metadata(extra_year="2025"), "123")["date_state"] == "UNRESOLVED"
    assert run.bind_metadata(xml_metadata(year="2023"), "123")["date_state"] == "INELIGIBLE"


def test_jats_main_article_identity_not_reference_identity():
    good = (b"<pmc-articleset><article><front><article-meta>"
            b"<article-id pub-id-type='pmc'>123</article-id></article-meta></front>"
            b"<back><ref><article-id pub-id-type='pmc'>999</article-id></ref></back>"
            b"</article></pmc-articleset>")
    assert run.canonical_jats(good, "PMC123").startswith(b"<article>")
    bad = good.replace(b"pub-id-type='pmc'>123", b"pub-id-type='pmc'>999")
    with pytest.raises(ValueError, match="JATS_CURRENT_ARTICLE_PMCID_MISMATCH"):
        run.canonical_jats(bad, "PMC123")
