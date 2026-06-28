# External Validation Anchors

Layer 6 remains the existing `code_engine.validation` subsystem. It has not
been replaced by a parallel hypothesis package. `ValidationAnchor` generalizes
the input boundary beyond triples:

- entity, triple, hypothesis, and phenotype anchors
- confirmed or context-resolved conflict anchors
- mechanism path and missing-link anchors
- pathway and gene-set anchors
- clinical-context anchors

A triple is one anchor type, not the validation architecture. Anchor builders
preserve hypothesis, conflict, evidence, mechanism-edge, and mechanism-path
identifiers. Entities without L2 canonical IDs remain exploratory, receive
lower confidence, and carry a warning; they cannot justify high-confidence
validation by themselves.

The question builder translates anchors into semantic validation intents such
as expression direction, binding activity, pathway membership, protein
interaction, clinical context, cancer dependency, identity lookup, or dataset
discovery. Questions do not contain SQL/API calls and do not execute providers.
