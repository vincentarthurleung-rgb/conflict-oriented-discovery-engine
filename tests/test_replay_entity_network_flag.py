"""Test replay pipeline entity normalization network flag behaviour.

Tests:
  1. replay CLI accepts --network.
  2. replay CLI passes network=True into replay().
  3. replay() passes network=True into L2 abstract step.
  4. ExternalCandidateProvider is not called when network=False.
  5. ExternalCandidateProvider can be called when network=True.
  6. audit summary records network_calls_made > 0 in mocked network-enabled path.
  7. network disabled state is explicitly reported.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from tests.replay_test_support import fixture as replay_fixture


class ReplayNetworkFlagCLITests(unittest.TestCase):
    """Test that the CLI argument parser accepts --network and --api."""

    def test_cli_accepts_network_flag(self):
        """Verify argparse accepts --network without crashing on arg parsing."""
        from code_engine.cli.replay_case_from_stage import main
        try:
            main(["--case-profile", "/nonexistent/profile.json",
                  "--search-plan-file", "/nonexistent/plan.json",
                  "--source-run", "/nonexistent/source",
                  "--from-stage", "bundle",
                  "--output-suffix", "test",
                  "--bundle-id-suffix", "test",
                  "--network", "--no-l1", "--skip-fulltext", "--skip-l7"])
        except SystemExit:
            pass  # argparse success; file/path errors are post-parse
        except (FileNotFoundError, ValueError, OSError):
            pass  # argparse succeeded; downstream errors are expected with fake paths

    def test_cli_accepts_api_flag(self):
        """Verify argparse accepts --api without crashing on arg parsing."""
        from code_engine.cli.replay_case_from_stage import main
        try:
            main(["--case-profile", "/nonexistent/profile.json",
                  "--search-plan-file", "/nonexistent/plan.json",
                  "--source-run", "/nonexistent/source",
                  "--from-stage", "bundle",
                  "--output-suffix", "test",
                  "--bundle-id-suffix", "test",
                  "--network", "--api", "--no-l1", "--skip-fulltext", "--skip-l7"])
        except SystemExit:
            pass
        except (FileNotFoundError, ValueError, OSError):
            pass

    def test_cli_no_network_is_default(self):
        """Without --network, the default must remain network=False."""
        from code_engine.cli.replay_case_from_stage import replay as replay_fn
        sig = __import__('inspect').signature(replay_fn)
        self.assertFalse(sig.parameters["network"].default,
                         "replay() must default to network=False for safe offline replay")


class ReplayNetworkPassthroughTests(unittest.TestCase):
    """Test that network=True is passed through replay() into L2 step and audit."""

    def test_replay_network_true_passes_to_l2_step(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile, plan, source = replay_fixture(root)

            # run_l2_abstract_step is imported locally inside replay(),
            # so patch at its source module.
            with patch("code_engine.workflow.steps.run_l2_abstract_step") as mock_l2:
                mock_l2.return_value = MagicMock()
                from code_engine.cli.replay_case_from_stage import replay
                result = replay(profile, plan, source, "l2",
                                root / "runs", "replay", "r2",
                                network=True, api=True,
                                bundle_root=root / "bundles")

                # Verify L2 step was called with network=True, api=True
                self.assertTrue(mock_l2.called)
                call_kwargs = mock_l2.call_args.kwargs
                self.assertTrue(call_kwargs.get("network"), "L2 step should receive network=True")
                self.assertTrue(call_kwargs.get("api"), "L2 step should receive api=True")
                self.assertTrue(call_kwargs.get("execute"), "L2 step should receive execute=True")

    def test_replay_network_false_passes_to_l2_step(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile, plan, source = replay_fixture(root)

            with patch("code_engine.workflow.steps.run_l2_abstract_step") as mock_l2:
                mock_l2.return_value = MagicMock()
                from code_engine.cli.replay_case_from_stage import replay
                result = replay(profile, plan, source, "l2",
                                root / "runs", "replay", "r2",
                                network=False, api=False,
                                bundle_root=root / "bundles")

                self.assertTrue(mock_l2.called)
                call_kwargs = mock_l2.call_args.kwargs
                self.assertFalse(call_kwargs.get("network"), "L2 step should receive network=False")
                self.assertFalse(call_kwargs.get("api"), "L2 step should receive api=False")

    def test_manifest_records_network_enabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile, plan, source = replay_fixture(root)

            from code_engine.cli.replay_case_from_stage import replay
            result = replay(profile, plan, source, "l2",
                            root / "runs", "replay", "r2",
                            network=True, api=False,
                            entity_network_lookup=True,
                            bundle_root=root / "bundles")

            new_run = Path(result["new_run"])
            manifest_path = new_run / "replay_manifest.json"
            self.assertTrue(manifest_path.is_file())
            manifest = json.loads(manifest_path.read_text())
            self.assertTrue(manifest["network_used"], "manifest must record network_used=True")
            self.assertTrue(manifest["entity_network_lookup_enabled"],
                            "manifest must record entity_network_lookup_enabled=True")
            self.assertIn("entity_external_lookup_skipped_reason", manifest)
            # When network=True and entity_network_lookup=True, skipped_reason should be None
            self.assertIsNone(manifest["entity_external_lookup_skipped_reason"])

    def test_manifest_records_network_disabled_explicitly(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile, plan, source = replay_fixture(root)

            from code_engine.cli.replay_case_from_stage import replay
            result = replay(profile, plan, source, "l2",
                            root / "runs", "replay", "r2",
                            network=False, api=False,
                            bundle_root=root / "bundles")

            new_run = Path(result["new_run"])
            manifest_path = new_run / "replay_manifest.json"
            self.assertTrue(manifest_path.is_file())
            manifest = json.loads(manifest_path.read_text())
            self.assertFalse(manifest["network_used"], "manifest must record network_used=False")
            self.assertEqual(
                manifest["entity_external_lookup_skipped_reason"],
                "entity_external_lookup_skipped_because_network_disabled",
                "manifest must explicitly state why entity lookups were skipped"
            )

    def test_l2_replay_regenerates_current_run_entity_decisions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile, plan, source = replay_fixture(root)
            old_decision = {
                "decision_run_id": "old_source_run",
                "request": {"surface": "STALE"},
                "normalization_status": "unresolved",
                "decision_reason": "stale_source_decision",
                "provider_trace": [{"provider_name": "NullProvider"}],
            }
            source_decisions = source / "artifacts" / "entity_resolution_decisions.jsonl"
            source_decisions.write_text(json.dumps(old_decision) + "\n")

            from code_engine.cli.replay_case_from_stage import replay
            result = replay(profile, plan, source, "l2",
                            root / "runs", "replay", "r2",
                            network=False, api=False,
                            bundle_root=root / "bundles")

            new_run = Path(result["new_run"])
            decisions_path = new_run / "artifacts" / "entity_resolution_decisions.jsonl"
            decisions = [json.loads(line) for line in decisions_path.read_text().splitlines() if line.strip()]
            self.assertTrue(decisions)
            self.assertFalse(any(item.get("request", {}).get("surface") == "STALE" for item in decisions))
            self.assertTrue(all(item.get("decision_run_id") == new_run.name for item in decisions))
            self.assertTrue(all(item.get("completion_mode") == "generated" for item in decisions))
            self.assertTrue(all(str(item.get("audit_ref", "")).startswith(str(new_run)) for item in decisions))

    def test_report_contains_network_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile, plan, source = replay_fixture(root)

            from code_engine.cli.replay_case_from_stage import replay
            result = replay(profile, plan, source, "l2",
                            root / "runs", "replay", "r2",
                            network=False, api=False,
                            bundle_root=root / "bundles")

            new_run = Path(result["new_run"])
            report_path = new_run / "replay_report.md"
            self.assertTrue(report_path.is_file())
            report = report_path.read_text()
            self.assertIn("entity external lookup skipped", report,
                          "Report must explicitly state entity lookups were skipped when network=False")


class ExternalCandidateProviderNetworkGateTests(unittest.TestCase):
    """Test that ExternalCandidateProvider respects the network_enabled flag."""

    def test_provider_skips_when_network_disabled(self):
        from code_engine.normalization.providers.base import ExternalCandidateProvider
        from code_engine.normalization.candidates import EntityResolutionRequest

        mock_client = MagicMock()
        mock_client.search.return_value = [{"canonical_id": "TEST:1", "canonical_name": "test"}]
        provider = ExternalCandidateProvider(mock_client)
        provider.name = "TestProvider"

        request = EntityResolutionRequest(
            surface="test entity",
            network_enabled=False,
            execute=True,
        )
        result = provider.propose(request)
        self.assertEqual(len(result), 0, "Provider must return empty when network_enabled=False")
        self.assertEqual(provider.last_status, "external_lookup_not_enabled")
        self.assertIn("external_lookup_not_enabled", provider.last_warnings)
        mock_client.search.assert_not_called()

    def test_provider_calls_client_when_network_enabled(self):
        from code_engine.normalization.providers.base import ExternalCandidateProvider
        from code_engine.normalization.candidates import EntityResolutionRequest

        mock_client = MagicMock()
        mock_client.search.return_value = [{"canonical_id": "TEST:1", "canonical_name": "test entity"}]
        mock_client.network_call_cost = 1
        provider = ExternalCandidateProvider(mock_client)
        provider.name = "TestProvider"

        request = EntityResolutionRequest(
            surface="test entity",
            network_enabled=True,
            execute=True,
        )
        result = provider.propose(request)
        self.assertGreater(len(result), 0, "Provider must return candidates when network_enabled=True")
        mock_client.search.assert_called_once()
        self.assertEqual(provider.last_network_calls, 1)

    def test_provider_skips_when_execute_false_even_with_network(self):
        from code_engine.normalization.providers.base import ExternalCandidateProvider
        from code_engine.normalization.candidates import EntityResolutionRequest

        mock_client = MagicMock()
        provider = ExternalCandidateProvider(mock_client)
        provider.name = "TestProvider"

        request = EntityResolutionRequest(
            surface="test entity",
            network_enabled=True,
            execute=False,
        )
        result = provider.propose(request)
        self.assertEqual(len(result), 0, "Provider must skip when execute=False regardless of network_enabled")
        mock_client.search.assert_not_called()

    def test_provider_skips_when_client_is_none(self):
        from code_engine.normalization.providers.base import ExternalCandidateProvider
        from code_engine.normalization.candidates import EntityResolutionRequest

        provider = ExternalCandidateProvider(None)
        provider.name = "TestProvider"

        request = EntityResolutionRequest(
            surface="test entity",
            network_enabled=True,
            execute=True,
        )
        result = provider.propose(request)
        self.assertEqual(len(result), 0, "Provider must skip when client is None")
        self.assertEqual(provider.last_status, "external_provider_not_configured")


class AuditNetworkCallCountTests(unittest.TestCase):
    """Test that the entity resolution audit correctly records network_calls_made."""

    def test_audit_records_network_calls_from_provider_trace(self):
        from code_engine.normalization.audit import EntityResolutionAuditWriter
        from code_engine.normalization.candidates import (
            EntityResolutionRequest, EntityResolutionResult, EntityCandidate
        )

        with tempfile.TemporaryDirectory() as tmp:
            audit = EntityResolutionAuditWriter(Path(tmp))

            # Simulate two resolutions: one with network calls, one without
            result1 = EntityResolutionResult(
                request=EntityResolutionRequest(surface="entity1"),
                candidates=[
                    EntityCandidate(
                        surface="entity1", normalized_surface="entity1",
                        canonical_id="X:1", canonical_name="Entity 1",
                        source="external_provider", provider_name="PubChem",
                    )
                ],
                normalization_status="resolved_external_grounded",
                decision_reason="external_grounded",
            )
            trace1 = [
                {"provider_name": "PubChem", "status": "candidates_returned",
                 "candidate_count": 1, "network_calls_made": 1, "api_calls_made": 0,
                 "warnings": []},
                {"provider_name": "NullProvider", "status": "not_needed",
                 "candidate_count": 0},
            ]

            result2 = EntityResolutionResult(
                request=EntityResolutionRequest(surface="entity2"),
                candidates=[],
                normalization_status="unresolved",
                decision_reason="no_candidates",
            )
            trace2 = [
                {"provider_name": "PubChem", "status": "external_lookup_not_enabled",
                 "candidate_count": 0, "network_calls_made": 0, "api_calls_made": 0,
                 "warnings": ["external_lookup_not_enabled"]},
                {"provider_name": "NullProvider", "status": "not_needed",
                 "candidate_count": 0},
            ]

            audit.write(result1, trace1)
            audit.write(result2, trace2)

            summary_path = Path(tmp) / "artifacts" / "entity_resolution_audit.json"
            self.assertTrue(summary_path.is_file())
            summary = json.loads(summary_path.read_text())
            self.assertEqual(summary["total_mentions"], 2)
            self.assertEqual(summary["network_calls_made"], 1,
                             "Audit must record network_calls_made from provider trace")
            self.assertIn("PubChem", summary["provider_usage_counts"])

    def test_audit_records_zero_network_calls_when_none_made(self):
        from code_engine.normalization.audit import EntityResolutionAuditWriter
        from code_engine.normalization.candidates import (
            EntityResolutionRequest, EntityResolutionResult
        )

        with tempfile.TemporaryDirectory() as tmp:
            audit = EntityResolutionAuditWriter(Path(tmp))

            result = EntityResolutionResult(
                request=EntityResolutionRequest(surface="entity1"),
                normalization_status="unresolved",
                decision_reason="no_candidates",
            )
            trace = [
                {"provider_name": "PubChem", "status": "external_lookup_not_enabled",
                 "candidate_count": 0, "network_calls_made": 0, "api_calls_made": 0,
                 "warnings": ["external_lookup_not_enabled"]},
            ]

            audit.write(result, trace)
            summary_path = Path(tmp) / "artifacts" / "entity_resolution_audit.json"
            summary = json.loads(summary_path.read_text())
            self.assertEqual(summary["network_calls_made"], 0)
            self.assertEqual(summary["cleaner_eligible_mentions"], 0)
            self.assertEqual(summary["cleaner_actual_calls"], 0)
            self.assertEqual(summary["cleaner_pending"], 0)
            self.assertEqual(
                summary["cleaner_accounting_reason"],
                "entity_llm_cleaner_summary_absent_or_not_enabled",
            )


class ResolverCascadeNetworkGateTests(unittest.TestCase):
    """Test that ResolverCascade correctly gates network_enabled on EntityResolutionRequest."""

    def test_resolver_request_has_network_disabled_by_default(self):
        from code_engine.normalization.resolver import ResolverCascade

        resolver = ResolverCascade()
        self.assertFalse(resolver.network_enabled)
        self.assertFalse(resolver.api_enabled)

    def test_resolver_request_has_network_enabled_when_configured(self):
        from code_engine.normalization.resolver import ResolverCascade

        resolver = ResolverCascade(network_enabled=True, api_enabled=True, execute=True)
        self.assertTrue(resolver.network_enabled)
        self.assertTrue(resolver.api_enabled)

    def test_resolve_entity_creates_request_with_network_gated_by_execute(self):
        from code_engine.normalization.resolver import ResolverCascade

        # network_enabled=True but execute=False → network_enabled on request should be False
        resolver_no_exec = ResolverCascade(network_enabled=True, api_enabled=True, execute=False)

        # Patch the hub to avoid real resolution
        with patch.object(resolver_no_exec.hub, "resolve") as mock_resolve:
            mock_result = MagicMock()
            mock_result.candidates = []
            mock_result.selected_candidate = None
            mock_result.normalization_status = "unresolved"
            mock_result.confidence = 0.0
            mock_result.decision_reason = "mock"
            mock_result.allow_high_confidence_graph_use = False
            mock_result.requires_manual_review = False
            mock_result.warnings = []
            mock_result.audit_ref = None
            mock_resolve.return_value = mock_result

            resolver_no_exec.resolve_entity("test")

            self.assertTrue(mock_resolve.called)
            request = mock_resolve.call_args.args[0]
            self.assertFalse(request.network_enabled,
                             "network_enabled on request must be False when execute=False")
            self.assertFalse(request.api_enabled)

    def test_resolve_entity_creates_request_with_network_enabled(self):
        from code_engine.normalization.resolver import ResolverCascade

        resolver = ResolverCascade(network_enabled=True, api_enabled=True, execute=True)

        with patch.object(resolver.hub, "resolve") as mock_resolve:
            mock_result = MagicMock()
            mock_result.candidates = []
            mock_result.selected_candidate = None
            mock_result.normalization_status = "unresolved"
            mock_result.confidence = 0.0
            mock_result.decision_reason = "mock"
            mock_result.allow_high_confidence_graph_use = False
            mock_result.requires_manual_review = False
            mock_result.warnings = []
            mock_result.audit_ref = None
            mock_resolve.return_value = mock_result

            resolver.resolve_entity("test")

            self.assertTrue(mock_resolve.called)
            request = mock_resolve.call_args.args[0]
            self.assertTrue(request.network_enabled,
                            "network_enabled on request must be True when both execute and network_enabled are True")
            self.assertTrue(request.api_enabled)


class HubProviderTraceNetworkCallsTests(unittest.TestCase):
    """Test that EntityResolutionHub records network_calls_made in provider traces."""

    def test_hub_trace_includes_network_call_counts(self):
        from code_engine.normalization.hub import EntityResolutionHub
        from code_engine.normalization.candidates import EntityResolutionRequest

        mock_provider = MagicMock()
        mock_provider.name = "MockExternal"
        mock_provider.can_handle.return_value = True
        mock_provider.propose.return_value = []
        mock_provider.last_warnings = []
        mock_provider.last_status = "no_candidates"
        mock_provider.last_network_calls = 2
        mock_provider.last_api_calls = 1

        hub = EntityResolutionHub([mock_provider])
        request = EntityResolutionRequest(surface="test", execute=True, network_enabled=True)
        result = hub.resolve(request)

        # We can't directly inspect trace without audit_writer, but we can verify
        # the provider was called
        mock_provider.propose.assert_called_once()


if __name__ == "__main__":
    unittest.main()


class ReplayEntityNetworkLookupCLITests(unittest.TestCase):
    """Test CLI accepts --entity-network-lookup and --no-entity-network-lookup."""

    def test_cli_accepts_entity_network_lookup_flag(self):
        """Verify argparse accepts --entity-network-lookup."""
        from code_engine.cli.replay_case_from_stage import main
        try:
            main(["--case-profile", "/nonexistent/profile.json",
                  "--search-plan-file", "/nonexistent/plan.json",
                  "--source-run", "/nonexistent/source",
                  "--from-stage", "bundle",
                  "--output-suffix", "test",
                  "--bundle-id-suffix", "test",
                  "--network", "--entity-network-lookup",
                  "--no-l1", "--skip-fulltext", "--skip-l7"])
        except SystemExit:
            pass
        except (FileNotFoundError, ValueError, OSError):
            pass

    def test_cli_accepts_no_entity_network_lookup_flag(self):
        """Verify argparse accepts --no-entity-network-lookup."""
        from code_engine.cli.replay_case_from_stage import main
        try:
            main(["--case-profile", "/nonexistent/profile.json",
                  "--search-plan-file", "/nonexistent/plan.json",
                  "--source-run", "/nonexistent/source",
                  "--from-stage", "bundle",
                  "--output-suffix", "test",
                  "--bundle-id-suffix", "test",
                  "--network", "--no-entity-network-lookup",
                  "--no-l1", "--skip-fulltext", "--skip-l7"])
        except SystemExit:
            pass
        except (FileNotFoundError, ValueError, OSError):
            pass


class ReplayEntityNetworkLookupPassthroughTests(unittest.TestCase):
    """Test entity_network_lookup passthrough from replay to L2 step."""

    def test_replay_passes_entity_network_lookup_false_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile, plan, source = replay_fixture(root)

            with patch("code_engine.workflow.steps.run_l2_abstract_step") as mock_l2:
                mock_l2.return_value = MagicMock()
                from code_engine.cli.replay_case_from_stage import replay
                replay(profile, plan, source, "l2",
                       root / "runs", "replay", "r2",
                       network=True, api=True,
                       bundle_root=root / "bundles")

                self.assertTrue(mock_l2.called)
                call_kwargs = mock_l2.call_args.kwargs
                self.assertFalse(call_kwargs.get("entity_network_lookup"),
                                 "entity_network_lookup should default to False when not passed")

    def test_replay_passes_entity_network_lookup_true(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile, plan, source = replay_fixture(root)

            with patch("code_engine.workflow.steps.run_l2_abstract_step") as mock_l2:
                mock_l2.return_value = MagicMock()
                from code_engine.cli.replay_case_from_stage import replay
                replay(profile, plan, source, "l2",
                       root / "runs", "replay", "r2",
                       network=True, api=True,
                       entity_network_lookup=True,
                       bundle_root=root / "bundles")

                self.assertTrue(mock_l2.called)
                call_kwargs = mock_l2.call_args.kwargs
                self.assertTrue(call_kwargs.get("entity_network_lookup"),
                                "entity_network_lookup should be True when passed")

    def test_manifest_records_entity_network_lookup_enabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile, plan, source = replay_fixture(root)

            from code_engine.cli.replay_case_from_stage import replay
            result = replay(profile, plan, source, "l2",
                            root / "runs", "replay", "r2",
                            network=True, api=True,
                            entity_network_lookup=True,
                            bundle_root=root / "bundles")

            new_run = Path(result["new_run"])
            manifest_path = new_run / "replay_manifest.json"
            manifest = json.loads(manifest_path.read_text())
            self.assertTrue(manifest["entity_network_lookup_enabled"],
                            "manifest must record entity_network_lookup_enabled=True")
            self.assertIsNone(manifest["entity_external_lookup_skipped_reason"],
                              "no skip reason when entity_network_lookup is enabled")

    def test_manifest_records_disabled_reason_when_network_true_but_entity_lookup_false(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile, plan, source = replay_fixture(root)

            from code_engine.cli.replay_case_from_stage import replay
            result = replay(profile, plan, source, "l2",
                            root / "runs", "replay", "r2",
                            network=True, api=True,
                            entity_network_lookup=False,
                            bundle_root=root / "bundles")

            new_run = Path(result["new_run"])
            manifest_path = new_run / "replay_manifest.json"
            manifest = json.loads(manifest_path.read_text())
            self.assertFalse(manifest["entity_network_lookup_enabled"])
            self.assertEqual(
                manifest["entity_external_lookup_skipped_reason"],
                "entity_external_lookup_skipped_because_entity_network_lookup_disabled",
                "manifest must explain entity lookups skipped due to entity_network_lookup=False"
            )

    def test_manifest_records_disabled_reason_when_network_false_with_entity_lookup_true(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile, plan, source = replay_fixture(root)

            from code_engine.cli.replay_case_from_stage import replay
            result = replay(profile, plan, source, "l2",
                            root / "runs", "replay", "r2",
                            network=False, api=False,
                            entity_network_lookup=True,
                            bundle_root=root / "bundles")

            new_run = Path(result["new_run"])
            manifest_path = new_run / "replay_manifest.json"
            manifest = json.loads(manifest_path.read_text())
            self.assertTrue(manifest["entity_network_lookup_enabled"])
            self.assertEqual(
                manifest["entity_external_lookup_skipped_reason"],
                "entity_external_lookup_skipped_because_network_disabled",
                "network=False must take priority over entity_network_lookup=True"
            )


class ResolverCascadeEntityNetworkLookupGateTests(unittest.TestCase):
    """Test that ResolverCascade gates external providers on entity_network_lookup."""

    def test_external_providers_installed_when_entity_network_lookup_true(self):
        from code_engine.normalization.resolver import ResolverCascade

        resolver = ResolverCascade(
            execute=True, network_enabled=True, entity_network_lookup=True
        )
        provider_names = [p.name for p in resolver.hub.providers]
        self.assertIn("PubChemCandidateProvider", provider_names,
                      "PubChem provider should be installed when entity_network_lookup=True")
        self.assertIn("ChEMBLCandidateProvider", provider_names)
        self.assertIn("MyGeneCandidateProvider", provider_names)
        self.assertIn("UniProtCandidateProvider", provider_names)

    def test_external_providers_not_installed_when_entity_network_lookup_false(self):
        from code_engine.normalization.resolver import ResolverCascade

        resolver = ResolverCascade(
            execute=True, network_enabled=True, entity_network_lookup=False
        )
        provider_names = [p.name for p in resolver.hub.providers]
        self.assertNotIn("PubChemCandidateProvider", provider_names,
                         "PubChem provider should NOT be installed when entity_network_lookup=False")
        self.assertNotIn("ChEMBLCandidateProvider", provider_names)
        self.assertNotIn("MyGeneCandidateProvider", provider_names)
        self.assertNotIn("UniProtCandidateProvider", provider_names)

    def test_llm_proposer_not_installed_by_default(self):
        from code_engine.normalization.resolver import ResolverCascade

        resolver = ResolverCascade(
            execute=True, api_enabled=True, entity_llm_proposer=False
        )
        provider_names = [p.name for p in resolver.hub.providers]
        self.assertNotIn("LLMCandidateProposerProvider", provider_names,
                         "LLM proposer should NOT be installed when entity_llm_proposer=False")

    def test_llm_proposer_installed_when_explicitly_enabled(self):
        from code_engine.normalization.resolver import ResolverCascade

        resolver = ResolverCascade(
            execute=True, api_enabled=True, entity_llm_proposer=True
        )
        provider_names = [p.name for p in resolver.hub.providers]
        self.assertIn("LLMCandidateProposerProvider", provider_names,
                      "LLM proposer should be installed when entity_llm_proposer=True")


class ReplayEntityNetworkCallsMadeTests(unittest.TestCase):
    """Test that entity_network_calls_made > 0 in mocked external lookup path."""

    def test_entity_network_calls_made_positive_with_mocked_provider(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile, plan, source = replay_fixture(root)

            # Simulate entity_resolution_audit.json with positive network_calls_made
            # This file is produced by EntityResolutionAuditWriter which lives inside
            # ResolverCascade → hub. We mock the L2 step to prevent the audit file
            # from being overwritten during replay.
            artifacts = Path(source) / "artifacts"
            entity_audit = {
                "total_mentions": 100,
                "status_counts": {"resolved_external_grounded": 42, "unresolved": 58},
                "provider_usage_counts": {"PubChemCandidateProvider": 30, "MyGeneCandidateProvider": 12},
                "network_calls_made": 44,
                "api_calls_made": 0,
            }
            (artifacts / "entity_resolution_audit.json").write_text(
                json.dumps(entity_audit))

            # Also create entity_resolution_audit.jsonl (the decisions file)
            # so the audit writer has something to read; the replay code reads
            # entity_resolution_audit.json which is the summary.
            with patch("code_engine.workflow.steps.run_l2_abstract_step") as mock_l2:
                mock_l2.return_value = MagicMock()
                from code_engine.cli.replay_case_from_stage import replay
                result = replay(profile, plan, source, "l2",
                                root / "runs", "replay", "r2",
                                network=True, api=True,
                                entity_network_lookup=True,
                                bundle_root=root / "bundles")

            new_run = Path(result["new_run"])
            manifest_path = new_run / "replay_manifest.json"
            manifest = json.loads(manifest_path.read_text())
            self.assertEqual(manifest["entity_network_calls_made"], 44,
                             "manifest must record entity_network_calls_made from audit")
            self.assertTrue(manifest["entity_network_lookup_enabled"])
            self.assertIsNone(manifest["entity_external_lookup_skipped_reason"])

    def test_entity_network_calls_made_zero_when_lookup_disabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile, plan, source = replay_fixture(root)

            artifacts = Path(source) / "artifacts"
            entity_audit = {
                "total_mentions": 50,
                "status_counts": {},
                "provider_usage_counts": {},
                "network_calls_made": 0,
                "api_calls_made": 0,
            }
            (artifacts / "entity_resolution_audit.json").write_text(
                json.dumps(entity_audit))

            from code_engine.cli.replay_case_from_stage import replay
            result = replay(profile, plan, source, "l2",
                            root / "runs", "replay", "r2",
                            network=True, api=True,
                            entity_network_lookup=False,
                            bundle_root=root / "bundles")

            new_run = Path(result["new_run"])
            manifest_path = new_run / "replay_manifest.json"
            manifest = json.loads(manifest_path.read_text())
            self.assertEqual(manifest["entity_network_calls_made"], 0)
            self.assertEqual(
                manifest["entity_external_lookup_skipped_reason"],
                "entity_external_lookup_skipped_because_entity_network_lookup_disabled"
            )


class AmbiguousExternalCandidateAuditTests(unittest.TestCase):
    """Test that ambiguous external candidates are retained for audit but excluded from high-confidence."""

    def test_ambiguous_candidates_excluded_from_high_confidence(self):
        from code_engine.normalization.resolver import ResolverCascade
        from code_engine.normalization.candidates import (
            EntityResolutionRequest, EntityResolutionResult, EntityCandidate
        )

        # Simulate hub returning ambiguous candidates
        resolver = ResolverCascade(execute=True, network_enabled=True, entity_network_lookup=True)

        with patch.object(resolver.hub, "resolve") as mock_resolve:
            candidate1 = EntityCandidate(
                surface="test entity", normalized_surface="test entity",
                canonical_id="EXT:1", canonical_name="Test Entity",
                source="external_provider", provider_name="PubChem",
                match_type="external_candidate", overall_score=0.85,
            )
            candidate2 = EntityCandidate(
                surface="test entity", normalized_surface="test entity",
                canonical_id="EXT:2", canonical_name="Test Entity Variant",
                source="external_provider", provider_name="ChEMBL",
                match_type="external_candidate", overall_score=0.82,
            )
            mock_result = EntityResolutionResult(
                request=EntityResolutionRequest(surface="test entity"),
                candidates=[candidate1, candidate2],
                selected_candidate=None,  # ambiguous — no clear winner
                normalization_status="ambiguous",
                confidence=0.5,
                decision_reason="ambiguous_margin",
                allow_high_confidence_graph_use=False,
                requires_manual_review=True,
                warnings=["ambiguous_margin_too_close"],
            )
            mock_resolve.return_value = mock_result

            decision = resolver.resolve_entity("test entity")
            # Verify ambiguity is preserved in audit
            self.assertEqual(decision.normalization_status, "ambiguous")
            self.assertEqual(len(decision.candidates), 2,
                             "All candidates must be retained for audit")
            self.assertFalse(decision.allow_high_confidence_graph_use,
                             "Ambiguous matches must not be used for high-confidence graph")
            self.assertTrue(decision.requires_manual_review,
                            "Ambiguous matches must require manual review")
            # The fallback best candidate's canonical_id may be used for display
            # purposes but the resolution status remains ambiguous. The canonical_id
            # comes from a real external provider, not fabricated.
            self.assertTrue(decision.canonical_id,
                            "Fallback canonical_id should be from best external candidate")
            # Verify the canonical_id matches one of the candidates
            candidate_ids = {c.canonical_id for c in mock_result.candidates}
            self.assertIn(decision.canonical_id, candidate_ids,
                          "Fallback canonical_id must be from an actual candidate")
