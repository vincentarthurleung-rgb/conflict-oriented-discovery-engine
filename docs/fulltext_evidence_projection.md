# Fulltext evidence projection architecture

## Confirmed before-state

The shared normalizer accepted `l35_fulltext_l1_claims.jsonl` records, but fulltext
reentry passed only each claim's sparse `context` into entity resolution. Existing
`fulltext_context_consolidations.jsonl`, experiment chains, Methods/Results anchors,
and figure/table context were downstream display inputs rather than authoritative L2
inputs. Reentry then classified lanes with a second lexical polarity calculation.
The formal relation resolver preferred `core_projection_relation` over
`derived_causal_sign`, allowing a downstream lexical value to overwrite intervention
algebra. Fulltext core also inherited abstract-era canonical and predicate flags,
which made all seven historical canaries fail their core gate.

## After-state

Shared provider, candidate, registry, adjudicator, relation, core, and handoff
components remain shared. Two explicit scientific profiles now select different
input contracts:

```text
abstract claim/sentence -> lightweight context -> candidate L2 -> conservative projection

fulltext observation -> experiment/context binding -> cached-candidate L2 re-adjudication
 -> reasoning chain -> authoritative causal sign -> deterministic core gate
 -> canonical evidence family -> unsigned relation bundle -> conflict eligibility
```

The offline projector is additive and content-addressed. It reads historical runs,
writes a new projection directory, records all calls as zero, and never changes an
old artifact or Atlas active pointer. Entity decisions retain previous/current IDs,
decision states, change reasons, context evidence, profile, version, and ortholog
provenance. Species-specific candidates fail closed when observation species is
unknown or incompatible. A species-neutral exact cached representation can be used
only after deterministic mention and type filtering.

Intervention direction is separated into lexical direction, observed outcome sign,
intervention sign, derived causal sign, and final formal polarity. Formal projection
now consumes the derived sign first. Canonical edge identity keeps polarity, while
conflict bundle identity deliberately omits polarity and compares it as an
observation attribute. Missing critical reasoning-chain fields, unresolved endpoints,
and species incompatibility remain reviewable rather than entering strict core.
