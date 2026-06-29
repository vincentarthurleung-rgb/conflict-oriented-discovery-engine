import tempfile
import unittest
from pathlib import Path

from code_engine.validation.clients.chembl_client import ChEMBLClient


class GuardedRemoteClientTests(unittest.TestCase):
    def test_guards_and_fake_response(self):
        client = ChEMBLClient()
        self.assertEqual(client.can_execute(False, True, True)[1], "external_lookup_not_enabled")
        self.assertEqual(client.can_execute(True, False, True)[1], "network_disabled")
        self.assertEqual(client.can_execute(True, True, False)[1], "external_validation_disabled")
        planned = client.build_request_plan(params={"q": "MTOR"})
        self.assertEqual(client.execute_request(planned).status, "external_lookup_not_enabled")
        with tempfile.TemporaryDirectory() as tmp:
            result = client.execute_request(planned, fake_response={"record_id": "1"}, raw_payload_path=Path(tmp) / "raw.json")
            self.assertEqual(result.status, "completed")
            self.assertEqual(len(result.records), 1)

    def test_validators_do_not_call_requests_directly(self):
        root = Path(__file__).parents[1] / "src/code_engine/validation"
        for path in root.glob("*.py"):
            self.assertNotIn("requests.get", path.read_text(encoding="utf-8"))


if __name__ == "__main__": unittest.main()
