"""Stable schema exports grouped by scientific responsibility."""

from code_engine.schemas.conflicts import ConflictEdge
from code_engine.schemas.contexts import ContextAttribution, ContextMention
from code_engine.schemas.documents import ManifestAudit, ManifestPaperEntry, PaperDocument, PayloadAudit
from code_engine.schemas.entities import NormalizedEntity
from code_engine.schemas.evidence import EvidenceRecord, build_minimal_evidence_record
from code_engine.schemas.evidence_chain import (
    ClaimEvidenceLink,
    ConsolidatedContextValue,
    ExperimentalEvidenceChain,
    validate_claim_evidence_references,
)
from code_engine.schemas.hypotheses import CandidateHypothesis
from code_engine.schemas.l1_extraction import L1ExtractedClaim
from code_engine.schemas.hypothesis_hyperedge import HypothesisHyperedge
from code_engine.schemas.mechanism_edge import MechanismEdge
from code_engine.schemas.reasoning_record import ReasoningRecord
from code_engine.schemas.triples import ScientificTriple
from code_engine.schemas.validation import (
    AggregatedValidationResult, ExternalEvidenceRecord, FinalReportItem,
    ValidationAnchor, ValidationExecutionContext, ValidationExecutionResult,
    ValidationPlan, ValidationQueryPlan, ValidationQuestion, ValidationResourcePolicy,
    ValidationResult, ValidationSignal, ValidatorCapability, ValidatorRoute,
    validate_json_list,
)

__all__ = [
    "PaperDocument", "ManifestAudit", "ManifestPaperEntry", "PayloadAudit",
    "ScientificTriple", "NormalizedEntity", "ConflictEdge", "ContextMention",
    "ContextAttribution", "CandidateHypothesis", "ValidationResult",
    "FinalReportItem", "ValidationQuestion", "ValidationPlan", "validate_json_list",
    "ValidationAnchor", "ValidationQueryPlan", "ExternalEvidenceRecord",
    "ValidationSignal", "ValidationExecutionContext", "ValidationResourcePolicy",
    "ValidationExecutionResult", "AggregatedValidationResult", "ValidatorCapability", "ValidatorRoute",
    "EvidenceRecord", "build_minimal_evidence_record", "MechanismEdge",
    "HypothesisHyperedge", "ReasoningRecord", "L1ExtractedClaim",
    "ExperimentalEvidenceChain", "ClaimEvidenceLink", "ConsolidatedContextValue",
    "validate_claim_evidence_references",
]
