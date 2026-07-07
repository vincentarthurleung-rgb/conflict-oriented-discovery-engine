"""Tests for run_case failure diagnostics: traceback, failure_reason, optional validators."""
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch, MagicMock

from code_engine.cli.run_case import main, _audit, build_parser


def _make_profile(root: Path, case_id: str = "test_case",
                  optional_validators: list | None = None,
                  expected_validators: list | None = None,
                  validator_policy: dict | None = None) -> Path:
    """Create a minimal case profile json for testing."""
    data = {
        "schema_version": "case_domain_profile_v1",
        "case_id": case_id,
        "case_version": "v1",
        "query": "test drug target pathway",
        "case_type": "drug_target_binding",
        "domain_tags": ["drug_target_binding"],
        "validation_needs": [],
        "expected_validators": expected_validators or [],
        "optional_validators": optional_validators or [],
        "excluded_validators": [],
        "validator_policy": validator_policy or {},
        "fulltext_policy": {},
        "profile_version": "1.0",
    }
    p = root / "case_profile.json"
    p.write_text(json.dumps(data))
    return p


def _make_search_plan(root: Path) -> Path:
    """Create a minimal frozen search plan."""
    p = root / "search_plan.frozen.json"
    p.write_text(json.dumps({"frozen": True, "plan_status": "ready", "executable": True}))
    return p


class OptionalValidatorNonBlockingTests(unittest.TestCase):
    """Test that recommended_but_unavailable optional validators do NOT trigger failure."""

    def test_optional_validators_unavailable_dry_run_passes(self):
        """Optional validators unavailable should not block the run."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile = _make_profile(root, optional_validators=["chembl", "opentargets"],
                                    validator_policy={"require_production_validators": False})
            plan = _make_search_plan(root)
            out = io.StringIO()
            with patch.dict(os.environ, {
                "L1_PROVIDER": "deepseek", "MODEL_NAME": "test-model",
                "DEEPSEEK_API_KEY": "sk-test"
            }, clear=True), redirect_stdout(out):
                code = main([
                    "--case-profile", str(profile),
                    "--search-plan-file", str(plan),
                    "--external-data-root", str(root / "data" / "external"),
                    "--dry-run",
                ])
            self.assertEqual(code, 0)
            output = out.getvalue()
            self.assertIn("CASE_RUN_DRY_RUN", output)
            self.assertIn("chembl", output)
            self.assertIn("opentargets", output)

    @patch("code_engine.cli.run_case.check_case_readiness")
    @patch("code_engine.cli.run_case.export_case_bundle")
    @patch("code_engine.fulltext.stage.run_l35_pmc_oa_stage")
    @patch("code_engine.fulltext.discovery_escalation.finalize_discovery_escalation")
    @patch("code_engine.fulltext.discovery_escalation.discovery_escalation_expected")
    @patch("code_engine.fulltext.discovery_escalation.prepare_discovery_escalation")
    @patch("code_engine.validation.production_v1_runner.run_production_v1_validators")
    @patch("subprocess.run")
    def test_optional_unavailable_does_not_cause_fail(
        self, mock_run, mock_validators, mock_prepare, mock_expected, mock_finalize, mock_fulltext, mock_export, mock_readiness
    ):
        """When optional validators are unavailable but no required validators blocked,
        the run should not fail for that reason alone."""
        mock_run.side_effect = [
            MagicMock(stdout='{"run_dir": "/tmp/run1"}\n', stderr="", returncode=0),
            MagicMock(stdout='{"run_dir": "/tmp/run2"}\n', stderr="", returncode=0),
        ]
        mock_export.return_value = (Path("/tmp/bundle"), {
            "ready_for_system_b": True,
            "executed_validators": [],
            "core_observation_count": 5,
            "true_graph_conflict_count": 2,
            "formal_hypothesis_count": 1,
        })
        mock_fulltext.return_value = {"status": "completed_no_candidates", "warnings": []}
        mock_finalize.return_value = {"status": "not_applicable", "warnings": []}
        mock_prepare.return_value = {"prepared": True}
        mock_expected.return_value = {"expected": False, "discovery_mode": False}
        mock_readiness.return_value = {
            "schema_version": "case_readiness_report_v1",
            "case_id": "test_case",
            "ready": True,
            "blocking_reasons": [],
            "llm": {"ready": True, "provider": "deepseek", "model": "m", "api_key_present": True, "missing_env": [], "blocking_reasons": []},
            "search_plan": {"ready": True, "status": "ready", "path": "plan.json", "frozen_metadata_present": True, "reason": None},
            "case_profile": {"ready": True, "path": "profile.json", "case_id": "test_case", "reason": None},
            "routing": {
                "selected_validators": [],
                "executed_if_run": [],
                "recommended_but_unavailable": ["chembl"],
                "blocked_required_validators": [],
                "selection_mode": "domain_aware_router",
            },
            "resources": [],
            "fulltext": {"enabled": False, "ready": True, "blocking_reasons": []},
            "warnings": [],
        }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile = _make_profile(root, optional_validators=["chembl"],
                                    validator_policy={"require_production_validators": False})
            plan = _make_search_plan(root)

            # Mock artifact existence and content without breaking profile loading
            original_is_file = Path.is_file
            original_read_text = Path.read_text
            def _is_file(self):
                # Only mock non-existent artifact paths, not real files
                if "case_profile" in str(self) or "search_plan" in str(self):
                    return original_is_file(self)
                return True
            def _read_text(self, *args, **kwargs):
                if "case_profile" in str(self) or "search_plan" in str(self):
                    return original_read_text(self, *args, **kwargs)
                return "{}"
            with patch.object(Path, "is_file", _is_file), \
                 patch.object(Path, "read_text", _read_text), \
                 patch.dict(os.environ, {
                     "L1_PROVIDER": "deepseek", "MODEL_NAME": "test-model",
                     "DEEPSEEK_API_KEY": "sk-test"
                 }, clear=True):
                out = io.StringIO()
                err = io.StringIO()
                with redirect_stdout(out), redirect_stderr(err):
                    code = main([
                        "--case-profile", str(profile),
                        "--search-plan-file", str(plan),
                        "--external-data-root", str(root / "data" / "external"),
                        "--no-write-audit",
                    ])
            output = out.getvalue()
            # Should pass (not fail) since optional validators unavailable is NOT fatal
            self.assertIn("CASE_RUN_PASS", output)
            self.assertNotIn("CASE_RUN_FAIL", output)


class RequiredValidatorBlockingTests(unittest.TestCase):
    """Test that blocked_required_validators CAN trigger failure when flag is set."""

    @patch("code_engine.cli.run_case.check_case_readiness")
    @patch("code_engine.cli.run_case.export_case_bundle")
    @patch("code_engine.fulltext.stage.run_l35_pmc_oa_stage")
    @patch("code_engine.fulltext.discovery_escalation.finalize_discovery_escalation")
    @patch("code_engine.fulltext.discovery_escalation.discovery_escalation_expected")
    @patch("code_engine.fulltext.discovery_escalation.prepare_discovery_escalation")
    @patch("code_engine.validation.production_v1_runner.run_production_v1_validators")
    @patch("subprocess.run")
    def test_fail_if_required_validator_unavailable_blocks(
        self, mock_run, mock_validators, mock_prepare, mock_expected, mock_finalize, mock_fulltext, mock_export, mock_readiness
    ):
        """When --fail-if-required-validator-unavailable is set and required validators
        are blocked, the run should fail."""
        mock_run.side_effect = [
            MagicMock(stdout='{"run_dir": "/tmp/run1"}\n', stderr="", returncode=0),
            MagicMock(stdout='{"run_dir": "/tmp/run2"}\n', stderr="", returncode=0),
        ]
        mock_export.return_value = (Path("/tmp/bundle"), {
            "ready_for_system_b": True,
            "executed_validators": [],
            "core_observation_count": 5,
            "true_graph_conflict_count": 2,
            "formal_hypothesis_count": 1,
        })
        mock_fulltext.return_value = {"status": "completed_no_candidates", "warnings": []}
        mock_finalize.return_value = {"status": "not_applicable", "warnings": []}
        mock_prepare.return_value = {"prepared": True}
        mock_expected.return_value = {"expected": False, "discovery_mode": False}
        mock_readiness.return_value = {
            "schema_version": "case_readiness_report_v1",
            "case_id": "test_case",
            "ready": True,
            "blocking_reasons": [],
            "llm": {"ready": True, "provider": "deepseek", "model": "m", "api_key_present": True, "missing_env": [], "blocking_reasons": []},
            "search_plan": {"ready": True, "status": "ready", "path": "plan.json", "frozen_metadata_present": True, "reason": None},
            "case_profile": {"ready": True, "path": "profile.json", "case_id": "test_case", "reason": None},
            "routing": {
                "selected_validators": [],
                "executed_if_run": [],
                "recommended_but_unavailable": ["chembl"],
                "blocked_required_validators": ["chembl"],
                "selection_mode": "domain_aware_router",
            },
            "resources": [],
            "fulltext": {"enabled": False, "ready": True, "blocking_reasons": []},
            "warnings": [],
        }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # chembl is listed as expected_validator (required), so it will be
            # in recommended_but_unavailable AND in required set
            profile = _make_profile(root, expected_validators=["chembl"],
                                    validator_policy={"require_production_validators": True})
            plan = _make_search_plan(root)

            original_is_file = Path.is_file
            original_read_text = Path.read_text
            def _is_file(self):
                if "case_profile" in str(self) or "search_plan" in str(self):
                    return original_is_file(self)
                return True
            def _read_text(self, *args, **kwargs):
                if "case_profile" in str(self) or "search_plan" in str(self):
                    return original_read_text(self, *args, **kwargs)
                return "{}"
            with patch.object(Path, "is_file", _is_file), \
                 patch.object(Path, "read_text", _read_text), \
                 patch.dict(os.environ, {
                     "L1_PROVIDER": "deepseek", "MODEL_NAME": "test-model",
                     "DEEPSEEK_API_KEY": "sk-test"
                 }, clear=True):
                out = io.StringIO()
                err = io.StringIO()
                with redirect_stdout(out), redirect_stderr(err):
                    code = main([
                        "--case-profile", str(profile),
                        "--search-plan-file", str(plan),
                        "--external-data-root", str(root / "data" / "external"),
                        "--fail-if-required-validator-unavailable",
                        "--no-write-audit",
                    ])
            output = out.getvalue()
            self.assertIn("CASE_RUN_FAIL", output)
            self.assertIn("failure_reason", output)
            self.assertIn("blocked_required_validators", output)


class ExceptionTracebackTests(unittest.TestCase):
    """Test that exceptions produce traceback output in stderr and failure_reason in stdout."""

    @patch("subprocess.run")
    def test_exception_emits_traceback_to_stderr(self, mock_run):
        """When an unexpected exception occurs, traceback should go to stderr."""
        mock_run.side_effect = RuntimeError("simulated pipeline failure")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile = _make_profile(root)
            plan = _make_search_plan(root)

            with patch.dict(os.environ, {
                "L1_PROVIDER": "deepseek", "MODEL_NAME": "test-model",
                "DEEPSEEK_API_KEY": "sk-test"
            }, clear=True):
                out = io.StringIO()
                err = io.StringIO()
                with redirect_stdout(out), redirect_stderr(err):
                    code = main([
                        "--case-profile", str(profile),
                        "--search-plan-file", str(plan),
                        "--external-data-root", str(root / "data" / "external"),
                        "--no-write-audit",
                    ])
            self.assertEqual(code, 1)
            stderr_output = err.getvalue()
            stdout_output = out.getvalue()

            # stderr should contain traceback
            self.assertIn("Traceback (most recent call last)", stderr_output)
            # stderr should contain failure diagnostics
            self.assertIn("failure_reason = exception", stderr_output)
            self.assertIn("exception_type = RuntimeError", stderr_output)
            self.assertIn("exception_message = simulated pipeline failure", stderr_output)

            # stdout should include CASE_RUN_FAIL and failure_reason
            self.assertIn("CASE_RUN_FAIL", stdout_output)
            self.assertIn("failure_reason = exception", stdout_output)

    @patch("code_engine.cli.run_case.check_case_readiness")
    @patch("subprocess.run")
    def test_audit_json_includes_exception_diagnostics(self, mock_run, mock_readiness):
        """When exception occurs, audit JSON should include exception_type/message/traceback_tail."""
        mock_run.side_effect = ValueError("bad value encountered")
        mock_readiness.return_value = {
            "schema_version": "case_readiness_report_v1",
            "case_id": "exception_test_case",
            "ready": True,
            "blocking_reasons": [],
            "llm": {"ready": True, "provider": "deepseek", "model": "m", "api_key_present": True, "missing_env": [], "blocking_reasons": []},
            "search_plan": {"ready": True, "status": "ready", "path": "plan.json", "frozen_metadata_present": True, "reason": None},
            "case_profile": {"ready": True, "path": "profile.json", "case_id": "exception_test_case", "reason": None},
            "routing": {
                "selected_validators": [],
                "executed_if_run": [],
                "recommended_but_unavailable": [],
                "blocked_required_validators": [],
                "selection_mode": "domain_aware_router",
            },
            "resources": [],
            "fulltext": {"enabled": False, "ready": True, "blocking_reasons": []},
            "warnings": [],
        }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile = _make_profile(root, case_id="exception_test_case")
            plan = _make_search_plan(root)

            audit_root = root / "audit_reports"
            # We need to run from the tmp dir context to capture the audit file
            orig_cwd = os.getcwd()
            try:
                os.chdir(root)
                with patch.dict(os.environ, {
                    "L1_PROVIDER": "deepseek", "MODEL_NAME": "test-model",
                    "DEEPSEEK_API_KEY": "sk-test"
                }, clear=True):
                    out = io.StringIO()
                    err = io.StringIO()
                    with redirect_stdout(out), redirect_stderr(err):
                        code = main([
                            "--case-profile", str(profile),
                            "--search-plan-file", str(plan),
                            "--external-data-root", str(root / "data" / "external"),
                        ])
                self.assertEqual(code, 1)

                # Check audit JSON
                audit_json = root / "audit_reports" / "exception_test_case_run_case_audit.json"
                self.assertTrue(audit_json.is_file(), f"Audit file not found at {audit_json}")
                data = json.loads(audit_json.read_text())
                self.assertEqual(data["failure_reason"], "exception")
                self.assertEqual(data["exception_type"], "ValueError")
                self.assertEqual(data["exception_message"], "bad value encountered")
                self.assertIsNotNone(data.get("traceback_tail"))
                self.assertIsInstance(data["traceback_tail"], list)
                self.assertGreater(len(data["traceback_tail"]), 0)

                # Check audit MD also includes diagnostics
                audit_md = root / "audit_reports" / "exception_test_case_run_case_audit.md"
                self.assertTrue(audit_md.is_file())
                md_text = audit_md.read_text()
                self.assertIn("Failure Diagnostics", md_text)
                self.assertIn("exception", md_text)
            finally:
                os.chdir(orig_cwd)


class FailureReasonOutputTests(unittest.TestCase):
    """Test that CASE_RUN_FAIL stdout includes failure_reason."""

    @patch("subprocess.run")
    def test_failure_reason_in_stdout(self, mock_run):
        """CASE_RUN_FAIL output must contain failure_reason."""
        mock_run.side_effect = RuntimeError("test error")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile = _make_profile(root)
            plan = _make_search_plan(root)

            with patch.dict(os.environ, {
                "L1_PROVIDER": "deepseek", "MODEL_NAME": "test-model",
                "DEEPSEEK_API_KEY": "sk-test"
            }, clear=True):
                out = io.StringIO()
                err = io.StringIO()
                with redirect_stdout(out), redirect_stderr(err):
                    code = main([
                        "--case-profile", str(profile),
                        "--search-plan-file", str(plan),
                        "--external-data-root", str(root / "data" / "external"),
                        "--no-write-audit",
                    ])
            self.assertEqual(code, 1)
            stdout_output = out.getvalue()
            self.assertIn("CASE_RUN_FAIL", stdout_output)
            self.assertIn("failure_reason = exception", stdout_output)


class AuditPayloadStructureTests(unittest.TestCase):
    """Test the _audit function directly for correct payload structure."""

    def test_audit_with_exception_fields(self):
        """_audit should include exception_type, exception_message, traceback_tail in payload."""
        profile = MagicMock()
        profile.case_id = "test"

        readiness = {
            "llm": {"ready": True},
            "search_plan": {"ready": True},
            "routing": {"blocked_required_validators": [], "recommended_but_unavailable": []},
        }

        payload, md = _audit(
            profile, "CASE_RUN_FAIL", readiness,
            failure_reason="exception",
            exception_type="ValueError",
            exception_message="test error message",
            traceback_tail=["line1", "line2", "line3"],
        )

        self.assertEqual(payload["failure_reason"], "exception")
        self.assertEqual(payload["exception_type"], "ValueError")
        self.assertEqual(payload["exception_message"], "test error message")
        self.assertEqual(payload["traceback_tail"], ["line1", "line2", "line3"])

    def test_audit_with_missing_artifacts(self):
        """_audit should include missing_final_artifacts."""
        profile = MagicMock()
        profile.case_id = "test"

        readiness = {
            "llm": {"ready": True},
            "search_plan": {"ready": True},
            "routing": {"blocked_required_validators": [], "recommended_but_unavailable": []},
        }

        payload, md = _audit(
            profile, "CASE_RUN_FAIL", readiness,
            failure_reason="missing_final_artifacts",
            missing_final_artifacts=["case_domain_profile.json", "whitebox_case_report.md"],
        )

        self.assertEqual(payload["failure_reason"], "missing_final_artifacts")
        self.assertEqual(
            payload["missing_final_artifacts"],
            ["case_domain_profile.json", "whitebox_case_report.md"]
        )

    def test_audit_with_blocked_validators(self):
        """_audit should include blocked_required_validators."""
        profile = MagicMock()
        profile.case_id = "test"

        readiness = {
            "llm": {"ready": True},
            "search_plan": {"ready": True},
            "routing": {"blocked_required_validators": ["chembl"], "recommended_but_unavailable": ["chembl"]},
        }

        payload, md = _audit(
            profile, "CASE_RUN_FAIL", readiness,
            failure_reason="blocked_required_validators",
            blocked_required_validators=["chembl"],
        )

        self.assertEqual(payload["failure_reason"], "blocked_required_validators")
        self.assertEqual(payload["blocked_required_validators"], ["chembl"])

    def test_audit_md_includes_failure_diagnostics(self):
        """Audit markdown should include Failure Diagnostics section."""
        profile = MagicMock()
        profile.case_id = "test"

        readiness = {
            "llm": {"ready": True},
            "search_plan": {"ready": True},
            "routing": {"blocked_required_validators": [], "recommended_but_unavailable": []},
        }

        payload, md = _audit(
            profile, "CASE_RUN_FAIL", readiness,
            failure_reason="exception",
            exception_type="KeyError",
            exception_message="'missing_key'",
            traceback_tail=["File ...", "KeyError: 'missing_key'"],
        )

        self.assertIn("## Failure Diagnostics", md)
        self.assertIn("failure_reason: exception", md)
        self.assertIn("exception_type: KeyError", md)
        self.assertIn("exception_message: 'missing_key'", md)


class BatchStderrDiagnosticsTests(unittest.TestCase):
    """Test that batch execution captures stderr diagnostics in log files."""

    def test_batch_stderr_log_receives_diagnostics(self):
        """When run_case fails in batch mode, stderr log should capture diagnostics."""

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile = _make_profile(root)
            plan = _make_search_plan(root)

            # Simulate what batch runner does: capture stderr
            import subprocess

            # Test with an invalid profile that would cause exception
            bad_profile = root / "bad_profile.json"
            bad_profile.write_text("not valid json")

            with patch.dict(os.environ, {
                "L1_PROVIDER": "deepseek", "MODEL_NAME": "test-model",
                "DEEPSEEK_API_KEY": "sk-test"
            }, clear=True):
                result = subprocess.run(
                    [sys.executable, "-m", "code_engine.cli.run_case",
                     "--case-profile", str(bad_profile),
                     "--search-plan-file", str(plan),
                     "--external-data-root", str(root / "data" / "external"),
                     "--no-write-audit"],
                    capture_output=True, text=True,
                )
            # Should fail
            self.assertNotEqual(result.returncode, 0)
            # stderr should contain diagnostic info, or stdout should contain CASE_RUN_FAIL
            combined = result.stdout + result.stderr
            self.assertTrue(
                "Traceback" in result.stderr
                or "failure_reason" in combined
                or "CASE_RUN_FAIL" in combined
                or "CASE_RUN_BLOCKED" in combined,
                f"Expected diagnostics in stderr or stdout, got: stderr={result.stderr[:300]}, stdout={result.stdout[:300]}"
            )


if __name__ == "__main__":
    unittest.main()
