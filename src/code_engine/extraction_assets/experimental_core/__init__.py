"""Experimental factor/measurement/result sidecar assets."""

from .models import (
    ExperimentalFactorRecord, ExperimentalObservationLinkage,
    ExperimentalObservationMachineReuseReadiness,
    ExperimentalObservationStructuralIntegrity, MeasurementRecord,
    ObservedResultRecord, StructuredExperimentalObservationRevision,
)
from .type_policy import build_policy

__all__ = [
    "ExperimentalFactorRecord", "ExperimentalObservationLinkage",
    "ExperimentalObservationMachineReuseReadiness",
    "ExperimentalObservationStructuralIntegrity", "MeasurementRecord",
    "ObservedResultRecord", "StructuredExperimentalObservationRevision",
    "build_policy",
]
"""Immutable experimental-core assets and offline v2 repair projections."""

from .comparison_semantics import classify_comparison
from .projection import build_compatibility_sidecar, build_projection

__all__ = ["build_compatibility_sidecar", "build_projection", "classify_comparison"]
