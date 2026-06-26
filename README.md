# C.O.D.E. v4.0 MVP

C.O.D.E. is an agent-assisted, conflict-oriented scientific discovery system for the current ketamine antidepressant-response corpus. It is designed as:

- Agentic Control Plane: generates configs, validation plans, and critic reports.
- Deterministic Pipeline Core: performs extraction post-processing, ontology alignment, conflict discovery, context attribution, graph search, validation state assignment, and ranking.
- Evaluation Framework: provides a historical replay benchmark skeleton.
- Extension Modules: validators and agents can be expanded without changing the deterministic core.

## Layers

- Layer 0: Literature Acquisition via `scripts/stage0_fetch_pmc.py` and `scripts/stage0_5_fetch_abstracts.py`.
- Layer 1: Scientific Fact Extraction via `scripts/stage2_l1_extract.py`.
- Layer 2: Ontology Alignment via `src/pipelines/ontology_alignment.py`.
- Layer 3: Conflict Discovery via `src/pipelines/conflict_discovery.py`.
- Layer 4: Context Mining via `python -m src.pipelines.context_mining`.
- Layer 5: Context Attribution via `src/pipelines/context_attribution.py`.
- Layer 6: Mechanism Graph Search via `scripts/stage6_l4_infer.py`.
- Layer 7: External Validation via `scripts/stage7_l5_verify.py`.
- Layer 8: Scientific Report Generation via `scripts/stage8_l6_results.py`.

## Important Limits

- The current omics registry is curated/demo scale and is not full LINCS validation.
- Ontology alignment is a conservative MVP: alias map plus uppercase fallback.
- LLM extraction still requires `DEEPSEEK_API_KEY` unless cached L1/L1.5 outputs are reused.
- Agents generate configuration and critique only; they are not scientific judges.
- Hypotheses with no validator coverage are `Unresolved_No_Coverage` and are not treated as passed.

## Current Clean Architecture Boundary

- `scripts/` contains CLI wrappers and legacy compatibility entrypoints.
- `src/pipelines/` contains core pipeline orchestration and deterministic processing.
- `src/reporting/` contains report-export ranking, blueprint construction, and markdown rendering.
- `src/validators/` contains validation plugins and validator skeletons.
- `src/agents/` is a config-generation/control plane; agents are not scientific judges and do not change final scores.
- `src/evaluation/` contains benchmark scaffolding.
- Legacy stage names remain for compatibility. New documentation explains the system as Layer 0-8 in `docs/STAGE_LAYER_MAPPING.md`.

See also:

- `docs/STAGE_LAYER_MAPPING.md`
- `docs/ARTIFACT_POLICY.md`
- `docs/CODE_REVIEW_GUIDE.md`

## Review-Readiness Audits

The repository includes non-blocking validators for cached manifest and Stage1
payload artifacts. These do not rewrite Stage0/Stage1 outputs.

```bash
python -m src.pipelines.manifest_validation
```

Use `--strict` when review requires critical manifest/payload errors to fail the
command.

## Common Commands

Use cached data and rerun deterministic L2/L3:

```bash
python scripts/stage4_l2_normalize.py --strict-config
```

Allow demo fallback explicitly:

```bash
python scripts/stage4_l2_normalize.py --config-path missing.json --allow-fallback --no-strict-config
```

Mine span-grounded context mentions:

```bash
python -m src.pipelines.context_mining
```

Run L4 graph search:

```bash
python scripts/stage6_l4_infer.py
```

Run L5 validator orchestrator:

```bash
python scripts/stage7_l5_verify.py
```

Run L6 report export:

```bash
python scripts/stage8_l6_results.py
```

Generate agentic support artifacts:

```bash
python -m src.agents.domain_bootstrap_agent "Ketamine antidepressant response"
python -m src.agents.context_axis_agent
python -m src.agents.validation_planner_agent
python -m src.agents.hypothesis_critic_agent
```

Run historical replay skeleton:

```bash
python -m src.evaluation.historical_replay --cutoff-year 2010 --future-start 2011 --future-end 2015
```
