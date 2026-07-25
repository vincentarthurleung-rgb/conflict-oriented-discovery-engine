# Extraction Asset Preservation v1

Status: Internal architecture

This layer preserves the paid-extraction boundary without changing C.O.D.E.'s
scientific method. Its order is:

`SourceSnapshot → ProviderCallSpecification → ProviderCallAttempt →
RawProviderResponse → ParsedExtractionCandidateRevision →
FieldEvidenceAndValueState → ValidationRevision → NormalizationRevision →
CoverageLedger → ReplayabilityAssessment → SelectiveReextractionRequirement`.

Raw provider bytes are archived atomically before parsing. Parser, schema,
validation, normalization, and derived-reasoning failures are offline failures;
they do not authorize a paid retry. A parser upgrade creates a new immutable
revision that references the same raw response.

The layer is deliberately upstream of L2/L3/L4. It does not import conflict
logic, decide alignment, contradiction, comparability, conflict, or hypothesis
validity, and it never writes back to historical payloads.

The HIF1A offline audit is at
`runs/20260725_hif1a_extraction_asset_preservation_v1_offline`. Historical
missing input text and raw-response bindings are reported as missing rather
than reconstructed.
# Historical forensic v2 note

Historical lineage forensics v1 consumes these immutable v1 assets without
modifying them. Its replayability v2 distinguishes direct and deterministic
unique bindings from probable/unbound candidates. The 81 selective
re-extraction records emitted here are the pre-forensic upper bound.
