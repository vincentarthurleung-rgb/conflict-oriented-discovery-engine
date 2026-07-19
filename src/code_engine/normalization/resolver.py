"""ResolverCascade compatibility facade over EntityResolutionHub."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from code_engine.normalization.adjudicator import adjudicate_entity_candidates
from code_engine.normalization.audit import EntityResolutionAuditWriter
from code_engine.normalization.cache import EntityCache
from code_engine.normalization.candidates import EntityCandidate, EntityResolutionRequest
from code_engine.normalization.hub import EntityResolutionHub
from code_engine.normalization.lexical import normalize_lexical_surface
from code_engine.normalization.models import EntityRelation, NormalizationCandidate, NormalizationDecision
from code_engine.normalization.providers.chembl import ChEMBLCandidateProvider
from code_engine.normalization.providers.llm_proposer import LLMCandidateProposerProvider
from code_engine.normalization.providers.local_cache import LocalCacheProvider
from code_engine.normalization.providers.local_curated import LocalCuratedProvider
from code_engine.normalization.providers.mygene import MyGeneCandidateProvider
from code_engine.normalization.providers.null import NullProvider
from code_engine.normalization.providers.ontology import OLSOntologyCandidateProvider
from code_engine.normalization.providers.patient_execution import L2ProviderExecutionManager
from code_engine.normalization.providers.pubchem import PubChemCandidateProvider
from code_engine.normalization.providers.uniprot import UniProtCandidateProvider
from code_engine.normalization.registry import DEFAULT_REGISTRY_PATH, LocalBiomedicalRegistry
from code_engine.normalization.entity_type import canonical_entity_type, refine_type_for_cleaned_mention

import re


DANGEROUS_WARNINGS = {"receptor_complex_to_gene_merge", "metabolite_to_parent_merge", "phenotype_to_gene_merge", "assay_to_phenotype_merge_without_relation"}


NON_ENTITY_PARAMETER_RE = re.compile(
    r"^\s*(?:"
    r"(?:p\s*[<=>]\s*\d+(?:\.\d+)?)|"
    r"(?:OD\s*\d{3,4})|"
    r"(?:\d+(?:\.\d+)?\s*(?:mg\s*/\s*kg|ug\s*/\s*kg|µg\s*/\s*kg|μg\s*/\s*kg|mg|ug|µg|μg|"
    r"nM|uM|µM|μM|mM|M|mg\s*/\s*mL|ng\s*/\s*mL|ug\s*/\s*mL|µg\s*/\s*mL|μg\s*/\s*mL|"
    r"s|sec|secs|min|mins|h|hr|hrs|hour|hours|day|days|week|weeks|"
    r"nm|°C|C|K|rpm|x\s*g|×\s*g|g-force|mL|uL|µL|μL|L|Hz|kHz|%))|"
    r"(?:Fig\.?|Figure|Table)\s*\d+[A-Za-z]?"
    r")\s*$",
    re.I,
)


def _looks_like_non_entity(raw_text: str) -> str | None:
    text = " ".join(str(raw_text or "").split())
    if not text:
        return "empty_surface"
    if NON_ENTITY_PARAMETER_RE.match(text):
        return "structured_experimental_parameter"
    if len(text.split()) > 18 and re.search(r"\b(?:showed|demonstrated|measured|treated|induced|resulted|significantly)\b", text, re.I):
        return "sentence_or_experimental_description"
    return None


def _species_context(context: dict[str, Any]) -> tuple[str | None, str]:
    candidates = [
        context.get("species"),
        (context.get("context_slots") or {}).get("species") if isinstance(context.get("context_slots"), dict) else None,
        (context.get("context_mentions") or {}).get("species") if isinstance(context.get("context_mentions"), dict) else None,
        (context.get("experimental_context") or {}).get("species") if isinstance(context.get("experimental_context"), dict) else None,
    ]
    text = " ".join(str(item or "") for item in candidates).strip()
    if text:
        return text, "explicit"
    context_text = str(context.get("context_text") or "")
    lowered = context_text.casefold()
    for label in ("human", "mouse", "murine", "rat", "bovine", "homo sapiens", "mus musculus"):
        if label in lowered:
            return label, "inferred"
    return None, "unknown"


def _mention_granularity(surface: str, entity_type: str | None) -> str:
    text = str(surface or "").casefold().strip()
    etype = canonical_entity_type(entity_type)
    if etype == "gene_or_protein":
        return "gene_or_protein"
    if etype in {"pathway", "biological_process", "phenotype", "protein_complex", "protein_family", "receptor"}:
        return etype
    if text in {"tgf-β", "tgf-beta", "tgfb", "transforming growth factor beta"}:
        return "protein_family"
    if etype in {"gene", "protein"}:
        return etype
    return "unknown"


def _legacy_candidate(candidate: EntityCandidate) -> NormalizationCandidate | None:
    if not candidate.canonical_id or not candidate.canonical_name:
        return None
    return NormalizationCandidate(canonical_id=candidate.canonical_id, canonical_name=candidate.canonical_name, entity_type=candidate.entity_type or "unknown", semantic_level=candidate.semantic_level or "unknown", aliases=candidate.aliases, external_ids=candidate.external_ids, relations=[EntityRelation.model_validate(item) for item in candidate.supporting_context.get("relations", [])], score=candidate.overall_score, source=candidate.source, match_type=candidate.match_type, warnings=candidate.warnings)


class ResolverCascade:
    def __init__(self, registry: LocalBiomedicalRegistry | None = None, *, registry_path: str | Path | None = None, allow_fallback: bool = False, domain_id: str = "general_biomedical", entity_registry_profile: str = "general_entity_resolution_hub", resolver_policy_id: str = "conservative_resolver_v2", hub: EntityResolutionHub | None = None, run_dir: str | Path | None = None, execute: bool = False, network_enabled: bool = False, api_enabled: bool = False, entity_network_lookup: bool = False, entity_llm_proposer: bool = False, entity_llm_cleaner: bool = False, external_clients: dict[str, Any] | None = None, llm_client: Any | None = None, adjudicator_policy: dict | None = None):
        self.domain_id = domain_id
        self.entity_registry_profile = entity_registry_profile
        self.resolver_policy_id = resolver_policy_id
        self.domain_specific_resolution_used = False
        self.domain_resolution_warnings: list[str] = []
        self.execute, self.network_enabled, self.api_enabled = execute, network_enabled, api_enabled
        self.entity_network_lookup, self.entity_llm_proposer = entity_network_lookup, entity_llm_proposer
        self.entity_llm_cleaner_enabled = entity_llm_cleaner
        self._llm_client = llm_client
        self._run_dir = Path(run_dir) if run_dir else None
        self._provider_execution_manager: L2ProviderExecutionManager | None = None
        # LLM cleaner (lazy init)
        self._llm_cleaner: Any = None
        if hub is not None:
            self.hub = hub
            self.registry = registry
            return
        if external_clients is None:
            from code_engine.normalization.clients import create_default_clients
            external_clients = create_default_clients()
        clients = external_clients or {}
        execution_manager = L2ProviderExecutionManager(run_dir) if run_dir and execute and network_enabled and entity_network_lookup else None
        self._provider_execution_manager = execution_manager
        providers = []
        if registry is not None:
            providers.append(LocalCuratedProvider(registry=registry))
        elif registry_path is not None and Path(registry_path) != DEFAULT_REGISTRY_PATH:
            providers.append(LocalCuratedProvider(registry_path=registry_path))
        # An explicitly selected curated registry is authoritative for a bounded
        # pilot and must not become ambiguous with stale cache namespaces.
        if registry is None and registry_path is None:
            providers.append(LocalCacheProvider(EntityCache()))
        # External entity database providers (PubChem, ChEMBL, MyGene, UniProt)
        # are only installed when entity_network_lookup is explicitly enabled.
        # This ensures audit visibility: when entity_network_lookup=False,
        # the provider trace will not show these providers at all, and the
        # caller's manifest/report can record the skip reason.
        if entity_network_lookup:
            providers.extend([
                PubChemCandidateProvider(clients.get("pubchem"), execution_manager=execution_manager),
                ChEMBLCandidateProvider(clients.get("chembl"), execution_manager=execution_manager),
                MyGeneCandidateProvider(clients.get("mygene"), execution_manager=execution_manager),
                UniProtCandidateProvider(clients.get("uniprot"), execution_manager=execution_manager),
                OLSOntologyCandidateProvider(clients.get("ols"), execution_manager=execution_manager),
            ])
        if entity_llm_proposer:
            providers.append(LLMCandidateProposerProvider(llm_client))
        providers.append(NullProvider())
        audit = EntityResolutionAuditWriter(run_dir) if run_dir else None
        cache = EntityCache(accepted_writes_enabled=True) if execute and registry is None and registry_path is None else None
        self.hub = EntityResolutionHub(providers, adjudicator_policy, audit, entity_cache=cache)
        self.registry = registry

    def _domain_metadata(self) -> dict[str, Any]:
        return {"domain_id": self.domain_id, "entity_registry_profile": self.entity_registry_profile, "resolver_policy_id": self.resolver_policy_id, "domain_specific_resolution_used": self.domain_specific_resolution_used, "domain_resolution_warnings": list(self.domain_resolution_warnings)}

    def _get_llm_cleaner(self):
        """Lazy-init the LLM entity cleaner."""
        if self._llm_cleaner is None and self.entity_llm_cleaner_enabled:
            from code_engine.normalization.llm_entity_cleaner import LLMEntityCleaner
            audit_dir = self._run_dir / "artifacts" if self._run_dir else None
            self._llm_cleaner = LLMEntityCleaner(
                llm_client=self._llm_client,
                enabled=self.entity_llm_cleaner_enabled,
                audit_dir=audit_dir,
            )
        return self._llm_cleaner

    def resolve_entity(self, raw_text: str, context: dict[str, Any] | None = None, allow_fallback: bool = False) -> NormalizationDecision:
        lexical = normalize_lexical_surface(raw_text)
        if lexical.invalid:
            return NormalizationDecision(raw_text=lexical.raw_text, normalized_surface=lexical.normalized_surface, normalization_status="empty_or_invalid", confidence=0.0, decision_reason="empty_invalid_or_placeholder_input", warnings=lexical.warnings, entity_resolution_status="unresolved", requires_manual_review=True, **self._domain_metadata())
        non_entity_reason = _looks_like_non_entity(lexical.raw_text)
        if non_entity_reason:
            return NormalizationDecision(raw_text=lexical.raw_text, normalized_surface=lexical.normalized_surface, normalization_status="rejected", confidence=0.0, decision_reason=f"not_entity:{non_entity_reason}", warnings=lexical.warnings + ["entity_resolver_skipped_non_entity_input"], entity_resolution_status="not_entity", requires_manual_review=False, **self._domain_metadata())
        context = context or {}
        expected_type = canonical_entity_type(context.get("expected_entity_type") or context.get("l1_entity_type_hint"))
        species_value, species_status = _species_context(context)
        measurement_dimension = None
        request = EntityResolutionRequest(surface=lexical.raw_text, context_text=context.get("context_text"), domain_id=self.domain_id, entity_registry_profile=self.entity_registry_profile, resolver_policy_id=self.resolver_policy_id, allowed_entity_types=list(context.get("allowed_entity_types") or []), l1_entity_type_hint=context.get("expected_entity_type") or context.get("l1_entity_type_hint"), paper_id=context.get("paper_id"), claim_id=context.get("claim_id"), observation_id=context.get("observation_id"), endpoint_role=context.get("mention_role"), relation=context.get("relation") or context.get("relation_raw") or context.get("predicate"), species_context=species_value, species_context_status=species_status, mention_granularity=_mention_granularity(lexical.raw_text, expected_type), assay_context=context.get("assay_context"), measurement_dimension=measurement_dimension, network_enabled=bool(self.execute and self.network_enabled), api_enabled=bool(self.execute and self.api_enabled), execute=self.execute)
        request.l1_entity_type_hint = expected_type
        result = self.hub.resolve(request)
        selected = result.selected_candidate
        legacy_candidates = [item for item in (_legacy_candidate(candidate) for candidate in result.candidates) if item]

        # --- LLM-assisted entity cleaning (only when unresolved/ambiguous) ---
        llm_cleaner_result = None
        if self.entity_llm_cleaner_enabled and result.normalization_status not in {
            "accepted_external_grounded", "resolved_curated", "resolved_external_grounded", "resolved_cache",
        }:
            cleaner = self._get_llm_cleaner()
            if cleaner is not None:
                llm_cleaner_result = cleaner.clean(
                    mention=lexical.raw_text,
                    claim_context=context.get("context_text", ""),
                    mention_role=context.get("mention_role", "subject"),
                    l1_type_hint=context.get("expected_entity_type") or context.get("l1_entity_type_hint"),
                    claim_id=context.get("claim_id"),
                    observation_id=context.get("observation_id"),
                )
                # If cleaner produced better surfaces, attempt external lookup for each
                if llm_cleaner_result.cleaned_head_entities and llm_cleaner_result.llm_cleaner_status in {"cleaned", "cleaned_with_warnings"}:
                    verified_candidates: list[EntityCandidate] = []
                    cleaner_type_traces: list[dict[str, Any]] = []
                    for head in llm_cleaner_result.cleaned_head_entities:
                        type_trace = refine_type_for_cleaned_mention(
                            lexical.raw_text,
                            head.surface,
                            original_entity_type=context.get("expected_entity_type") or context.get("l1_entity_type_hint"),
                            cleaner_suggested_type=head.entity_type,
                            context_text=context.get("context_text"),
                        )
                        cleaner_type_traces.append(type_trace)
                        final_type = canonical_entity_type(type_trace["final_expected_entity_type"])
                        from code_engine.normalization.llm_entity_cleaner import DEFAULT_ONTOLOGY_ROUTES
                        routes = DEFAULT_ONTOLOGY_ROUTES.get(final_type, []) or head.ontology_routes
                        head.entity_type = final_type
                        head.ontology_routes = list(dict.fromkeys(routes))
                        for route in head.ontology_routes:
                            # Only attempt external lookups if network is enabled
                            if not (self.execute and self.network_enabled and self.entity_network_lookup):
                                break
                            # Find the matching provider
                            provider = self._find_provider_by_name(route)
                            if provider is None:
                                continue
                            # Build a cleaned request for this head
                            cleaned_request = EntityResolutionRequest(
                                surface=head.surface,
                                context_text=context.get("context_text"),
                                domain_id=self.domain_id,
                                entity_registry_profile=self.entity_registry_profile,
                                resolver_policy_id=self.resolver_policy_id,
                                l1_entity_type_hint=final_type,
                                paper_id=context.get("paper_id"),
                                claim_id=context.get("claim_id"),
                                observation_id=context.get("observation_id"),
                                endpoint_role=context.get("mention_role"),
                                relation=context.get("relation") or context.get("relation_raw") or context.get("predicate"),
                                species_context=species_value,
                                species_context_status=species_status,
                                mention_granularity=_mention_granularity(head.surface, final_type),
                                assay_context=context.get("assay_context"),
                                measurement_dimension=type_trace.get("measurement_dimension"),
                                network_enabled=bool(self.execute and self.network_enabled),
                                api_enabled=bool(self.execute and self.api_enabled),
                                execute=self.execute,
                            )
                            try:
                                proposed = provider.propose(cleaned_request)
                                for c in proposed:
                                    # Mark as post-cleaner verified candidate
                                    c.supporting_context["llm_cleaned_surface"] = head.surface
                                    c.supporting_context["llm_cleaner_confidence"] = head.confidence
                                    c.supporting_context["original_mention"] = lexical.raw_text
                                    c.overall_score = min(1.0, c.overall_score + 0.05)  # small boost for cleaner routing
                                verified_candidates.extend(proposed)
                                if cleaner:
                                    cleaner.external_lookup_after_cleaning_calls += 1
                            except Exception:
                                continue

                    if verified_candidates:
                        # Merge with existing candidates and re-adjudicate
                        all_candidates = list(result.candidates) + verified_candidates
                        re_result = adjudicate_entity_candidates(request, all_candidates, self.hub.adjudicator_policy)
                        # If re-adjudication produced a verified result, use it
                        if re_result.normalization_status in {"accepted_external_grounded", "resolved_external_grounded", "resolved_curated", "resolved_cache"}:
                            result = re_result
                            if cleaner:
                                cleaner.update_verification_status(
                                    original_mention=lexical.raw_text,
                                    verification_result="verified",
                                    final_decision="accepted_after_llm_cleaning_and_external_verification",
                                    high_confidence_allowed=True,
                                )
                        elif re_result.normalization_status == "ambiguous":
                            # Keep original result, but note that cleaner helped find candidates
                            result = re_result
                            if cleaner:
                                cleaner.update_verification_status(
                                    original_mention=lexical.raw_text,
                                    verification_result="ambiguous",
                                    final_decision="ambiguous_after_llm_cleaning",
                                    high_confidence_allowed=False,
                                    rejection_reason="ambiguous_external_result_after_cleaning",
                                )
                        else:
                            # External lookup after cleaning still failed
                            if cleaner:
                                cleaner.update_verification_status(
                                    original_mention=lexical.raw_text,
                                    verification_result="provider_no_result",
                                    final_decision="llm_cleaned_but_no_provider_match",
                                    high_confidence_allowed=False,
                                    rejection_reason="no_external_verification_after_llm_cleaning",
                                )
                    else:
                        # Cleaner extracted heads but no external provider had results
                        if cleaner:
                            cleaner.update_verification_status(
                                original_mention=lexical.raw_text,
                                verification_result="unverified",
                                final_decision="llm_suggested_unverified",
                                high_confidence_allowed=False,
                                rejection_reason="llm_cleaned_entity_not_verified_by_any_provider",
                            )

        # --- Build legacy decision ---
        if result.normalization_status in {"accepted_external_grounded", "resolved_curated", "resolved_external_grounded", "resolved_cache"} and result.selected_candidate:
            legacy_status = "resolved"
        elif result.normalization_status in {"ambiguous", "ambiguous_external_candidate"} or (result.normalization_status == "manual_review_required" and result.candidates):
            legacy_status = "ambiguous"
        elif result.normalization_status == "llm_suggestion_ungrounded":
            legacy_status = "unresolved_fallback"
        else:
            legacy_status = "unresolved_fallback"
        selected = None if result.normalization_status == "rejected_external_candidate" else result.selected_candidate
        canonical_name = str(selected.canonical_name or "") if selected else (lexical.normalized_surface.upper() if legacy_status == "unresolved_fallback" else "")
        selected_legacy = _legacy_candidate(selected) if selected else None
        # Fall back to best candidate when adjudicator cannot decide (ambiguous margin).
        # Ambiguous external matches are retained for audit traceability but
        # must never be treated as high-confidence grounded results.
        if selected is None and result.candidates:
            best = max(result.candidates, key=lambda c: c.overall_score)
            selected = best
        # Build llm_cleaner context if available
        llm_cleaner_context: dict[str, Any] = {}
        if llm_cleaner_result is not None:
            llm_cleaner_context = {
                "llm_cleaner_status": llm_cleaner_result.llm_cleaner_status,
                "llm_cleaned_entities": [
                    {"surface": h.surface, "entity_type": h.entity_type, "ontology_routes": h.ontology_routes}
                    for h in llm_cleaner_result.cleaned_head_entities
                ],
                "llm_cleaner_warnings": llm_cleaner_result.warnings,
            }

        # --- Determine cleaner-integration fields ---
        selected_source = ""
        selected_cleaned_surface = ""
        external_verification_provider = ""
        rejection_reason = ""
        cleaner_trace = None

        if llm_cleaner_result is not None and llm_cleaner_result.cleaned_head_entities:
            cleaner_trace = {
                "original_mention": lexical.raw_text,
                "cleaned_head_entities": [
                    {"surface": h.surface, "entity_type": h.entity_type, "ontology_routes": h.ontology_routes,
                     "confidence": h.confidence}
                    for h in llm_cleaner_result.cleaned_head_entities
                ],
                "type_traces": locals().get("cleaner_type_traces", []),
                "external_verification_result": llm_cleaner_result.external_verification_result,
                "final_decision": llm_cleaner_result.final_decision,
                "high_confidence_graph_allowed": llm_cleaner_result.high_confidence_graph_allowed,
                "rejection_reason": llm_cleaner_result.rejection_reason,
            }

            # Determine selected_source based on how we got here
            if llm_cleaner_result.external_verification_result == "verified":
                if llm_cleaner_result.high_confidence_graph_allowed:
                    selected_source = "external_after_cleaning"
                else:
                    selected_source = "external_after_cleaning_rejected"
                # Find which provider verified
                if selected and selected.provider_name:
                    external_verification_provider = selected.provider_name
                # Find cleaned surface
                if llm_cleaner_result.cleaned_head_entities:
                    selected_cleaned_surface = llm_cleaner_result.cleaned_head_entities[0].surface
            elif llm_cleaner_result.external_verification_result == "ambiguous":
                selected_source = "external_after_cleaning_ambiguous"
            elif llm_cleaner_result.external_verification_result == "provider_no_result":
                selected_source = "cleaned_but_no_provider_match"
            elif llm_cleaner_result.external_verification_result == "unverified":
                selected_source = "llm_cleaned_unverified"
            rejection_reason = llm_cleaner_result.rejection_reason or ""
        elif result.normalization_status == "resolved_curated":
            selected_source = "curated"
        elif result.normalization_status in {"accepted_external_grounded", "resolved_external_grounded"}:
            selected_source = "external_direct"
        elif result.normalization_status == "resolved_cache":
            selected_source = "cache"

        return NormalizationDecision(
            raw_text=lexical.raw_text,
            normalized_surface=lexical.normalized_surface,
            canonical_id=str(selected.canonical_id or "") if selected else "",
            canonical_name=canonical_name,
            entity_type=str(selected.entity_type or expected_type or "unknown") if selected else str(expected_type or "unknown"),
            semantic_level=str(selected.semantic_level or "unknown") if selected else "unresolved",
            external_ids=dict(selected.external_ids) if selected else {},
            relations=selected_legacy.relations if selected_legacy else [],
            normalization_status=legacy_status,
            confidence=result.confidence,
            resolver="entity_resolution_hub_v1",
            match_type=selected.match_type if selected else "unresolved",
            candidates=legacy_candidates,
            decision_reason=result.decision_reason,
            allow_high_confidence_graph_use=result.allow_high_confidence_graph_use,
            warnings=list(dict.fromkeys(lexical.warnings + result.warnings + (
                ["uppercase_fallback_low_confidence"] if legacy_status == "unresolved_fallback" else []
            ))),
            candidate_count=len(result.candidates),
            candidate_provider_names=list(dict.fromkeys(item.provider_name for item in result.candidates)),
            selected_candidate_id=selected.candidate_id if selected else None,
            entity_resolution_status=result.normalization_status,
            requires_manual_review=result.requires_manual_review,
            audit_ref=result.audit_ref,
            # --- Cleaner integration fields ---
            selected_source=selected_source,
            selected_cleaned_surface=selected_cleaned_surface,
            original_surface=lexical.raw_text,
            external_verification_provider=external_verification_provider,
            rejection_reason=rejection_reason,
            cleaner_trace=cleaner_trace,
            **self._domain_metadata(),
        )

    def _find_provider_by_name(self, route: str):
        """Find a provider by its short name (pubchem, chembl, mygene, uniprot)."""
        route_map = {
            "pubchem": "PubChemCandidateProvider",
            "chembl": "ChEMBLCandidateProvider",
            "mygene": "MyGeneCandidateProvider",
            "uniprot": "UniProtCandidateProvider",
            "ols": "OLSOntologyCandidateProvider",
        }
        target_name = route_map.get(route.casefold())
        if not target_name:
            return None
        for provider in self.hub.providers:
            if provider.name == target_name:
                return provider
        return None


def resolve_entity(raw_text: str, context: dict[str, Any] | None = None, allow_fallback: bool = False, **resolver_kwargs: Any) -> NormalizationDecision:
    return ResolverCascade(allow_fallback=allow_fallback, **resolver_kwargs).resolve_entity(raw_text, context=context, allow_fallback=allow_fallback)


def write_llm_cleaner_audit(run_dir: str | Path, cleaner: Any) -> dict[str, str]:
    """Write LLM cleaner audit files at the end of a run."""
    from pathlib import Path as _Path
    artifacts = _Path(run_dir) / "artifacts"
    return cleaner.write_audit_files(artifacts) if cleaner else {}
