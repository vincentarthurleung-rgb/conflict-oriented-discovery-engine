# Fulltext Re-entry v5 Mapping

All four evidence lanes enter the Dossier evidence index with source record hashes and exact paper/claim/section/chunk provenance. Dossier IDs use the existing `dossier_projection.dossier_id_for` rule.

- `core_seed_relation`: core mechanism evidence; eligible for exploratory display when structurally usable.
- `seed_neighborhood_mechanism`: seed-neighborhood mechanism evidence; eligible for exploratory display when structurally usable.
- `reviewable_context_relation`: Dossier, Context Matrix, and review staging only unless its explicit exploratory flag and all display gates allow it.
- `off_seed_relation`: provenance/Dossier/context/review only; never the main KG.

Context fields are deterministic aliases for species, cell type/line, tissue, disease subtype, treatment, dose, duration, genotype, localization, assay method, outcome definition, measured endpoint, intervention type/target, control group, model system, validation design, reasoning trace status, and disease stage. A missing source value remains `null` and is displayed as “未报告”; no value is inferred.

Optional fulltext reasoning artifacts are joined by `claim_id`. The adapter attaches the trace to Dossier evidence and projects consolidated experimental context into Context Matrix rows. Reasoning steps are not projected into Display KG triples, Clean KG nodes, or formal conflict predictions.

Display KG rejects expression-state, association, comparison, no-effect, polarity-mismatch, composite, malformed, or endpoint-missing records. Evidence, papers, claims, and validators are provenance/annotations, never KG nodes. Generic entities retain the existing Atlas display behavior.

Formal conflict output has one gate only: `conflict_eligible is true`. Exploratory eligibility never promotes a record into formal conflict. Duplicate flags, polarity mismatch, core-gate failures, and dedup actions remain audit fields.
