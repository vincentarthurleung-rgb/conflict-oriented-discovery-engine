# Paper Registry and bibliographic provenance

Identity matching is conservative: exact normalized DOI, PMID, PMCID, then normalized title plus year and first author. Title-only equality is recorded as a possible duplicate and is not automatically merged. SHA-256 is used for every identity hash.

`run_paper_manifest.jsonl` maps legacy `paper_id` values to `canonical_paper_id`. Single-paper artifacts contain compact DOI/title/journal/year fields. Multi-paper conflicts, mechanisms, hypotheses, reasoning records, and validation anchors contain linked canonical IDs, DOIs, titles, journals, journal distribution, and publication-year range. Full metadata remains in the registry and is not copied wholesale.
