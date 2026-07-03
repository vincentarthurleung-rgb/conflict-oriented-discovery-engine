import json
import unittest

from code_engine.validation.external_api_smoke import ExternalAPISmokeTester


class ExternalAPISmokeResultTests(unittest.TestCase):
    def test_mocked_official_endpoints_are_reachable_but_not_runnable(self):
        def transport(request, timeout):
            url = request.full_url
            if "esearch.fcgi" in url: value = {"esearchresult": {"count": "10", "idlist": ["1"]}}
            elif "idconv" in url: value = {"records": [{"pmcid": "PMC7096777"}]}
            elif "reactome.org" in url: return 200, b"91"
            elif "addList" in url: value = {"userListId": 123}
            elif "/enrich?" in url: value = {"Reactome_2022": []}
            elif "chembl" in url: value = {"molecules": [{"molecule_chembl_id": "CHEMBL413"}]}
            elif "opentargets" in url: value = {"data": {"search": {"total": 1, "hits": []}}}
            else: raise AssertionError(url)
            return 200, json.dumps(value).encode()
        result = ExternalAPISmokeTester("configs/external_apis/external_api_registry.json", network_enabled=True, max_retries=0, transport=transport).run()
        self.assertEqual(result["reachable_count"], 6)
        for validator in ("pubmed_post_cutoff", "reactome", "enrichr", "chembl", "opentargets"):
            self.assertEqual(result["results"][validator]["status"], "reachable")
            self.assertFalse(result["results"][validator]["production_validator_ready"])
        self.assertTrue(result["results"]["pmc_oa"]["production_validator_ready"])

    def test_failure_is_recorded_without_crashing(self):
        def failed(request, timeout): raise TimeoutError("fixture timeout")
        result = ExternalAPISmokeTester("configs/external_apis/external_api_registry.json", network_enabled=True, max_retries=0, transport=failed).run(["reactome"])
        self.assertEqual(result["failed_count"], 1)
        self.assertEqual(result["results"]["reactome"]["status"], "failed")
        self.assertIn("TimeoutError", result["results"]["reactome"]["reason"])


if __name__ == "__main__": unittest.main()
