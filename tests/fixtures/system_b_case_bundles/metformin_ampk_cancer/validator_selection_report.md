# Validator Selection Report

Selection mode: `domain_aware_router`

## Decisions

- `lincs_l1000`: **selected_for_execution** — case tags and validation needs matched; required local resources are available
- `chembl`: **recommended_but_unavailable** — ChEMBL requires a configured schema-bound production index or provider
- `reactome`: **recommended_but_unavailable** — Reactome adapter exists but no configured production local index or real HTTP transport
- `enrichr`: **recommended_but_unavailable** — Enrichr has only an API adapter/cache skeleton
- `pubmed_post_cutoff`: **recommended_but_unavailable** — The post-cutoff literature validator has no query/execution implementation
- `opentargets`: **recommended_but_unavailable** — Open Targets has no configured production index or real HTTP transport
