# metformin_ampk_cancer Run Case Audit

## Executive Decision

CASE_RUN_PASS_WITH_WARNINGS

## Runs

- source run: runs/20260703_134819_metformin_ampk_cancer
- final run: /home/vincent/project/conflict-oriented-discovery-engine/runs/20260703_134819_metformin_ampk_cancer_rebuilt_metformin_ampk_cancer_clean_domain_routed_lincs_v1

## Readiness

- LLM ready: True
- search plan ready: True
- validator routing ready: True

## Stage Completeness

- final artifacts present: True

## Key Metrics

- executed validators: ['lincs_l1000']
- unavailable validators: ['chembl', 'reactome', 'enrichr', 'pubmed_post_cutoff', 'opentargets']
- true graph conflicts: 0
- external validation: partially_completed

## Case Bundle

- path: case_bundles/metformin_ampk_cancer
- ready_for_system_b: True

## Warnings

- validator unavailable: chembl
- validator unavailable: reactome
- validator unavailable: enrichr
- validator unavailable: pubmed_post_cutoff
- validator unavailable: opentargets

## Final Recommendation

Configure missing resources or proceed with the exported bundle according to the decision above.
