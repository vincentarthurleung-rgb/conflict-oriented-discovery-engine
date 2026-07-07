"""Tests for run_case child process failure diagnostics."""
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch, MagicMock

from code_engine.cli.run_case import main, _audit


def _make_profile(root: Path, case_id: str = "test_case") -> Path:
    data = {
        "schema_version": "case_domain_profile_v1",
        "case_id": case_id, "case_version": "v1",
        "query": "test drug target pathway",
        "case_type": "drug_target_binding",
        "domain_tags": ["drug_target_binding"],
        "validation_needs": [],
        "expected_validators": [],
        "optional_validators": [],
        "excluded_validators": [],
        "validator_policy": {},
        "fulltext_policy": {},
        "profile_version": "1.0",
    }
    p = root / "case_profile.json"
    p.write_text(json.dumps(data))
    return p


def _make_search_plan(root: Path) -> Path:
    p = root / "search_plan.frozen.json"
    p.write_text(json.dumps({"frozen": True, "plan_status": "ready", "executable": True}))
    return p


def _make_called_process_error(returncode=1, cmd=None, stdout="", stderr="",
                                phase="source_run"):
    """Create a realistic CalledProcessError simulating a child process failure."""
    cmd = cmd or ["python", "-m", "code_engine.cli.run", "--query", "test", "--until", "report"]
    return subprocess.CalledProcessError(returncode, cmd, stdout, stderr)


class ChildProcessFailureDiagnosticsTests(unittest.TestCase):
    """Test that child process failures produce detailed diagnostics."""

    def _setup_mocks(self, mock_run, mock_readiness):
        """Set up common mocks for all child process tests."""
        mock_readiness.return_value = {
            "schema_version": "case_readiness_report_v1",
            "case_id": "test_case",
            "ready": True,
            "blocking_reasons": [],
            "llm": {"ready": True, "provider": "deepseek", "model": "m",
                    "api_key_present": True, "missing_env": [], "blocking_reasons": []},
            "search_plan": {"ready": True, "status": "ready", "path": "plan.json",
                           "frozen_metadata_present": True, "reason": None},
            "case_profile": {"ready": True, "path": "profile.json",
                            "case_id": "test_case", "reason": None},
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

    @patch("code_engine.cli.run_case.check_case_readiness")
    @patch("subprocess.run")
    def test_source_run_failure_includes_child_phase_source_run(
        self, mock_run, mock_readiness
    ):
        """source_run child process failure should report child_phase=source_run."""
        self._setup_mocks(mock_run, mock_readiness)
        child_stderr = "Error: API key invalid\nTraceback: ...\n"
        mock_run.side_effect = _make_called_process_error(
            returncode=1, stderr=child_stderr, phase="source_run")

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
            stderr_output = err.getvalue()

            # Verify failure_reason
            self.assertIn("failure_reason = child_process_failed", stdout_output)
            # Verify child_phase
            self.assertIn("child_phase = source_run", stdout_output)
            # Verify child stderr is preserved
            self.assertIn("API key invalid", stderr_output)
            # Verify it's NOT generic exception
            self.assertNotIn("failure_reason = exception", stdout_output)

    @patch("code_engine.cli.run_case.check_case_readiness")
    @patch("subprocess.run")
    def test_final_run_failure_includes_child_phase_final_run(
        self, mock_run, mock_readiness
    ):
        """final_run child process failure should report child_phase=final_run."""
        self._setup_mocks(mock_run, mock_readiness)
        # First call succeeds (source_run), second fails (final_run)
        mock_run.side_effect = [
            MagicMock(stdout='{"run_dir": "/tmp/run1"}\n', stderr="", returncode=0),
            _make_called_process_error(
                returncode=2, stderr="rebuild stage l7 failed\n", phase="final_run"),
        ]

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

            self.assertIn("failure_reason = child_process_failed", stdout_output)
            self.assertIn("child_phase = final_run", stdout_output)

    @patch("code_engine.cli.run_case.check_case_readiness")
    @patch("subprocess.run")
    def test_child_stderr_tail_preserved(self, mock_run, mock_readiness):
        """Child process stderr should be preserved and printed."""
        self._setup_mocks(mock_run, mock_readiness)
        child_stderr = "\n".join(f"error line {i}" for i in range(10))
        mock_run.side_effect = _make_called_process_error(
            returncode=1, stderr=child_stderr)

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
            # Child stderr should appear in parent stderr
            self.assertIn("error line 0", stderr_output)
            self.assertIn("error line 9", stderr_output)

    @patch("code_engine.cli.run_case.check_case_readiness")
    @patch("subprocess.run")
    def test_child_stdout_tail_preserved(self, mock_run, mock_readiness):
        """Child process stdout should be preserved in audit payload."""
        self._setup_mocks(mock_run, mock_readiness)
        child_stdout = "\n".join(f"output line {i}" for i in range(5))
        child_stderr = "some error"
        mock_run.side_effect = _make_called_process_error(
            returncode=1, stdout=child_stdout, stderr=child_stderr)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile = _make_profile(root, case_id="child_stdout_test")
            plan = _make_search_plan(root)
            audit_root = root / "audit_reports"
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

                audit_json = root / "audit_reports" / "child_stdout_test_run_case_audit.json"
                self.assertTrue(audit_json.is_file(), f"Audit file not found at {audit_json}")
                data = json.loads(audit_json.read_text())

                self.assertEqual(data["failure_reason"], "child_process_failed")
                self.assertEqual(data["child_phase"], "source_run")
                self.assertEqual(data["child_return_code"], 1)
                self.assertIsNotNone(data.get("child_stdout_tail"))
                self.assertIsNotNone(data.get("child_stderr_tail"))
                # Child stdout tail should contain our output
                stdout_tail = data["child_stdout_tail"]
                self.assertTrue(any("output line" in line for line in stdout_tail),
                                f"child_stdout_tail missing expected content: {stdout_tail}")
                # Child stderr tail should contain our error
                stderr_tail = data["child_stderr_tail"]
                self.assertTrue(any("some error" in line for line in stderr_tail),
                                f"child_stderr_tail missing expected content: {stderr_tail}")
            finally:
                os.chdir(orig_cwd)

    @patch("code_engine.cli.run_case.check_case_readiness")
    @patch("subprocess.run")
    def test_failure_reason_is_child_process_failed_not_generic_exception(
        self, mock_run, mock_readiness
    ):
        """failure_reason should be child_process_failed, not generic 'exception'."""
        self._setup_mocks(mock_run, mock_readiness)
        mock_run.side_effect = _make_called_process_error(returncode=1)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile = _make_profile(root, case_id="reason_test")
            plan = _make_search_plan(root)
            audit_root = root / "audit_reports"
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
                stdout_output = out.getvalue()
                stderr_output = err.getvalue()

                # failure_reason must be child_process_failed
                self.assertIn("failure_reason = child_process_failed", stdout_output)
                # Must NOT be generic exception
                self.assertNotIn("failure_reason = exception", stdout_output)

                audit_json = root / "audit_reports" / "reason_test_run_case_audit.json"
                data = json.loads(audit_json.read_text())
                self.assertEqual(data["failure_reason"], "child_process_failed")
                self.assertEqual(data["exception_type"], "CalledProcessError")
            finally:
                os.chdir(orig_cwd)

    @patch("code_engine.cli.run_case.check_case_readiness")
    @patch("subprocess.run")
    def test_audit_json_includes_child_return_code(self, mock_run, mock_readiness):
        """Audit JSON should include child_return_code from the failed process."""
        self._setup_mocks(mock_run, mock_readiness)
        mock_run.side_effect = _make_called_process_error(returncode=42)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile = _make_profile(root, case_id="returncode_test")
            plan = _make_search_plan(root)
            orig_cwd = os.getcwd()
            try:
                os.chdir(root)
                with patch.dict(os.environ, {
                    "L1_PROVIDER": "deepseek", "MODEL_NAME": "test-model",
                    "DEEPSEEK_API_KEY": "sk-test"
                }, clear=True):
                    out = io.StringIO()
                    with redirect_stdout(out):
                        code = main([
                            "--case-profile", str(profile),
                            "--search-plan-file", str(plan),
                            "--external-data-root", str(root / "data" / "external"),
                        ])
                self.assertEqual(code, 1)
                audit_json = root / "audit_reports" / "returncode_test_run_case_audit.json"
                data = json.loads(audit_json.read_text())
                self.assertEqual(data["child_return_code"], 42)
            finally:
                os.chdir(orig_cwd)

    @patch("code_engine.cli.run_case.check_case_readiness")
    @patch("subprocess.run")
    def test_audit_md_includes_child_diagnostics(self, mock_run, mock_readiness):
        """Audit markdown should include child process diagnostics."""
        self._setup_mocks(mock_run, mock_readiness)
        mock_run.side_effect = _make_called_process_error(
            returncode=3, stderr="fatal: config missing")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile = _make_profile(root, case_id="md_test")
            plan = _make_search_plan(root)
            orig_cwd = os.getcwd()
            try:
                os.chdir(root)
                with patch.dict(os.environ, {
                    "L1_PROVIDER": "deepseek", "MODEL_NAME": "test-model",
                    "DEEPSEEK_API_KEY": "sk-test"
                }, clear=True):
                    out = io.StringIO()
                    with redirect_stdout(out):
                        code = main([
                            "--case-profile", str(profile),
                            "--search-plan-file", str(plan),
                            "--external-data-root", str(root / "data" / "external"),
                        ])
                self.assertEqual(code, 1)
                audit_md = root / "audit_reports" / "md_test_run_case_audit.md"
                md_text = audit_md.read_text()
                self.assertIn("child_phase:", md_text)
                self.assertIn("child_return_code:", md_text)
            finally:
                os.chdir(orig_cwd)


class AuditChildDiagnosticsStructureTests(unittest.TestCase):
    """Test _audit function directly with child process diagnostics."""

    def test_audit_payload_includes_child_fields(self):
        profile = MagicMock()
        profile.case_id = "test"
        readiness = {
            "llm": {"ready": True},
            "search_plan": {"ready": True},
            "routing": {"blocked_required_validators": [], "recommended_but_unavailable": []},
        }
        payload, md = _audit(
            profile, "CASE_RUN_FAIL", readiness,
            failure_reason="child_process_failed",
            exception_type="CalledProcessError",
            exception_message="Command returned non-zero exit status 1",
            traceback_tail=["line1", "line2"],
            child_phase="source_run",
            child_return_code=1,
            child_command=["python", "-m", "code_engine.cli.run"],
            child_stdout_tail=["output line"],
            child_stderr_tail=["error line"],
        )
        self.assertEqual(payload["failure_reason"], "child_process_failed")
        self.assertEqual(payload["child_phase"], "source_run")
        self.assertEqual(payload["child_return_code"], 1)
        self.assertEqual(payload["child_command"], ["python", "-m", "code_engine.cli.run"])
        self.assertEqual(payload["child_stdout_tail"], ["output line"])
        self.assertEqual(payload["child_stderr_tail"], ["error line"])

    def test_audit_md_includes_child_diagnostics_section(self):
        profile = MagicMock()
        profile.case_id = "test"
        readiness = {
            "llm": {"ready": True},
            "search_plan": {"ready": True},
            "routing": {"blocked_required_validators": [], "recommended_but_unavailable": []},
        }
        payload, md = _audit(
            profile, "CASE_RUN_FAIL", readiness,
            failure_reason="child_process_failed",
            child_phase="final_run",
            child_return_code=2,
        )
        self.assertIn("## Failure Diagnostics", md)
        self.assertIn("failure_reason: child_process_failed", md)
        self.assertIn("child_phase: final_run", md)
        self.assertIn("child_return_code: 2", md)


if __name__ == "__main__":
    unittest.main()
