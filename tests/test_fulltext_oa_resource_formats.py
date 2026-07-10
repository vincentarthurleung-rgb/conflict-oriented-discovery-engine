import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path

from code_engine.fulltext.pmc_oa_client import check_oa_availability
from code_engine.fulltext.pmc_oa_downloader import download_oa_article
from code_engine.fulltext.discovery_escalation import finalize_discovery_escalation,prepare_discovery_escalation
from code_engine.fulltext.stage import run_l35_pmc_oa_stage


JATS=b"<article><front><article-meta><title-group><article-title>Example</article-title></title-group></article-meta></front><body><sec><title>Results</title><p>A specific mechanism increased a measured target.</p></sec></body></article>"


def archive(entries):
    output=io.BytesIO()
    with tarfile.open(fileobj=output,mode="w:gz") as tar:
        for name,data in entries:
            info=tarfile.TarInfo(name);info.size=len(data);tar.addfile(info,io.BytesIO(data))
    return output.getvalue()


class PMCResourceFormatTests(unittest.TestCase):
    def availability(self,fmt="tgz",url="https://ftp.ncbi.nlm.nih.gov/article.tar.gz"):
        xml=f'<OA><records><record license="CC"><link format="{fmt}" href="{url}"/></record></records></OA>'.encode()
        return check_oa_availability("PMC-X",network_enabled=True,transport=lambda _:xml)

    def archive_availability(self):
        oa=self.availability();return {**oa,"selected_resource":next(x for x in oa["download_resources"] if x["resource_type"]=="pmc_oa_archive")}

    def test_archive_resource_selected_and_nxml_parsed(self):
        oa=self.availability();archive_resource=next(x for x in oa["download_resources"] if x["resource_type"]=="pmc_oa_archive")
        self.assertTrue(archive_resource["supported"]);self.assertTrue(archive_resource["url"].startswith("https://ftp.ncbi.nlm.nih.gov/"))
        oa={**oa,"selected_resource":archive_resource}
        with tempfile.TemporaryDirectory() as td:
            result=download_oa_article({"paper_id":"p","pmcid":"PMC-X"},oa,td,network_enabled=True,transport=lambda _:archive([("pkg/article.nxml",JATS)]))
            self.assertEqual(result["full_text_status"],"available");self.assertTrue(result["archive_extracted"])
            self.assertEqual(result["selected_xml_file"],"pkg/article.nxml");self.assertGreater(result["parsed_section_count"],0)
            self.assertTrue((Path(td)/"PMC-X/article_text.json").is_file())

    def test_archive_path_traversal_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            result=download_oa_article({"paper_id":"p","pmcid":"PMC-X"},self.archive_availability(),td,network_enabled=True,transport=lambda _:archive([("../article.nxml",JATS)]))
            self.assertEqual(result["reason"],"archive_unsafe_path");self.assertFalse((Path(td).parent/"article.nxml").exists())

    def test_archive_without_xml_has_specific_reason(self):
        with tempfile.TemporaryDirectory() as td:
            result=download_oa_article({"paper_id":"p","pmcid":"PMC-X"},self.archive_availability(),td,network_enabled=True,transport=lambda _:archive([("readme.txt",b"none")]))
            self.assertEqual(result["reason"],"archive_contains_no_xml")

    def test_direct_nxml_detected_by_content_and_parsed(self):
        with tempfile.TemporaryDirectory() as td:
            oa=self.availability("nxml","https://www.ncbi.nlm.nih.gov/content/download")
            result=download_oa_article({"paper_id":"p","pmcid":"PMC-X"},oa,td,network_enabled=True,transport=lambda _:JATS)
            self.assertEqual(result["download_status"],"success");self.assertEqual(result["parse_status"],"success")
            self.assertGreater(result["parsed_section_count"],0)

    def test_bioc_xml_is_normalized_to_sections(self):
        bioc=b'<collection><document><id>PMC-X</id><passage><infon key="section_type">RESULTS</infon><text>A measured result.</text></passage></document></collection>'
        with tempfile.TemporaryDirectory() as td:
            oa=self.availability();self.assertEqual(oa["selected_resource"]["resource_type"],"bioc_xml")
            result=download_oa_article({"paper_id":"p","pmcid":"PMC-X"},oa,td,network_enabled=True,transport=lambda _:bioc)
            self.assertEqual(result["parse_status"],"success");self.assertEqual(result["selected_xml_kind"],"bioc");self.assertEqual(result["parsed_section_count"],1)

    def test_pdf_only_is_explicitly_unsupported(self):
        oa=self.availability("pdf","https://www.ncbi.nlm.nih.gov/article.pdf")
        self.assertEqual(oa["reason"],"only_pdf_resources_available");self.assertIsNone(oa["selected_resource"])
        result=download_oa_article({"paper_id":"p","pmcid":"PMC-X"},oa,"/tmp/unused",network_enabled=True,transport=lambda _:b"")
        self.assertEqual(result["reason"],"only_pdf_resources_available")

    def test_archive_parse_mocked_l1_and_discovery_reentry(self):
        with tempfile.TemporaryDirectory() as td:
            run=Path(td);artifacts=run/"artifacts";artifacts.mkdir()
            candidate={"paper_id":"paper-x","pmid":"paper-x","pmcid":"PMC-X","pmcid_verification_status":"verified","selection_score":.9,"anchor_strength":"strong","selection_source":"anchored_reviewable","linked_observation_ids":["abstract-x"]}
            (artifacts/"fulltext_discovery_escalation_candidates.jsonl").write_text(json.dumps(candidate)+"\n")
            (artifacts/"semantic_search_intent.json").write_text(json.dumps({"seed_triple":{"subject":{"name":"specific mechanism"},"object":{"name":"measured target"},"context":{}}}))
            (artifacts/"search_plan_replay.json").write_text(json.dumps({"enabled":True}));(artifacts/"intake.json").write_text("{}")
            for name,value in (("l2_retained_observations.jsonl",""),("pipeline_stage_summary.json","{}"),("hypothesis_summary.json",'{"formal_hypothesis_count":0}')):(artifacts/name).write_text(value)
            prepared=prepare_discovery_escalation(run,enabled=True)
            oa=lambda _:b'<OA><records><record license="CC"><link format="tgz" href="https://ftp.ncbi.nlm.nih.gov/article.tar.gz"/></record></records></OA>'
            extractor=lambda text,context:[{"subject":"specific mechanism","predicate":"increased","object":"measured target","polarity":"positive","evidence_sentence":"A specific mechanism increased a measured target."}]
            bioc=b'<collection><document><id>PMC-X</id><passage><infon key="section_type">RESULTS</infon><text>A specific mechanism increased a measured target.</text></passage></document></collection>'
            shared=run_l35_pmc_oa_stage(run,enabled=True,network_enabled=True,extractor=extractor,id_transport=lambda _:{"records":[{"pmcid":"PMC-X"}]},oa_transport=oa,download_transport=lambda _:bioc)
            self.assertEqual(shared["fulltext_l1_claim_count"],1);self.assertEqual(shared["xml_file_selected_count"],1)
            summary=finalize_discovery_escalation(run,prepared=prepared,expected=True,explicitly_disabled=False,shared_summary=shared)
            self.assertEqual(summary["fulltext_claims_reentered_l2"],1);self.assertGreater(summary["parsed_section_count"],0)
            self.assertTrue((artifacts/"l35_fulltext_discovery_observations.jsonl").read_text().strip())


if __name__=="__main__": unittest.main()
