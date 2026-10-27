# Domain and source-design routing for experimental extraction v1

The six existing `DomainProfile`s remain unchanged. They describe research
domains and context slots, not experiment types. The original L1 registry's
actual templates are version 2.1 and emit the legacy `claims` schema. Those
templates cannot be substituted into V3 or linkage-candidate requests.

`domain.extraction_routing` reuses those profiles and `DOMAIN_INSTRUCTIONS`.
It adds two versioned adapters, `domain_design_experimental_v3_v1` and
`domain_design_linkage_candidate_v1`, without creating a parallel domain
registry. Each preserves the frozen base prompt/schema and appends explicitly
non-authoritative domain/design guidance. Existing low-level `build_prompt`
and `render_candidate_prompt` remain fixed base renderers. Their historical
request files are not rewritten or silently described as routed requests.

Four levels are recorded separately:

1. Question intake profile and its original semantic/degraded/uncertain state.
2. Paper design inventory over the currently supplied source ArticleJSON,
   including the raw JATS article type when available. This is not a complete
   semantic classifier of individual papers' scientific domains.
3. Window design cues or exact native-observation evidence scope. Cell,
   animal, observational clinical, interventional clinical, omics and
   computational cues may coexist; no supported cue means `unknown`.
4. The actual compiled prompt/profile/schema/hash used by execution.

Design cues use a small bounded set of explicit source phrases, anchored with
the existing evidence-anchor generator or validated native V3 spans. No gene,
cell-line-name dictionary, disease label, pathway similarity, fuzzy match or
external lookup establishes a design. Hypothetical/prior/negated cues remain
uncertain. Coverage and precision are limited; novel wording and languages may
fall back to unknown. A positive cue is a routing candidate, not scientific
verification. Co-located cue types do not bind methods or define an experiment.
Omics/computational modalities can coexist with biological systems.

Pure supported clinical design cues select the existing clinical domain
instructions; otherwise the question domain is retained as context or the
general biomedical profile is used. This is never a verified paper-domain
assignment. Question/profile metadata is preserved separately from source
design. Native V3 normalization continues to use the existing
`generic_experimental` semantics registry; routing tags do not authorize new
ontology or design mappings, formal causal signs, Strict Core or Human Gold.

`ExistingStagesBackend` binds intake, records paper inventory, prepares V3,
and uses the same exact provider body for input reservation and dispatch.
Builder V4 and Quality V2 remain fixed frozen prompts. Domain metadata for
their trace/cache is not injected into their model-visible input. Historical
pinned native annotations are explicitly reuse without a new extraction request.
The unified executor retains routing sidecars before cache lookup. Its cache
identity binds domain state, study-design decision, prompt and schema versions,
input hashes, compiled prompt/body hash, model configuration and routing
implementation identity.

The current pilot intake still calls the existing deterministic degraded
intake without a model. No unbudgeted semantic-classification call is introduced.
Frozen retrieval plans and search membership are unchanged. The legacy workflow
can still use its existing explicitly authorized semantic-intake mechanism.
This restoration is therefore `PARTIALLY_CONNECTED`, not a claim of complete
automatic semantic paper/experiment classification.

Routed window planning adds the estimated guidance overhead to the unchanged
V3 preflight and obeys its 6000 estimated input/context/output and figure-unit
limits. All source intervals remain accounted. Additional splitting changes
derived windows and request hashes, not frozen source assets or scientific
inclusion policies. Use `routing_domain` for the routed planning version;
the no-routing argument retains the legacy bounded-planning path.

`prepare_v3_component_request` is the current non-sending probe preparation
interface. `conditional_linkage_request` applies the new linkage adapter only
after existing source/observation binding checks. The linkage step remains a
separate conditional component helper; it is not a new automatically dispatched
pilot stage. Owner authorization is still required for any paid execution.
Old fixed-prompt paid proposals retain their historical meaning and must not
be used as the price/hash reservation for changed routed requests. Freeze and
price the actual new bodies before execution. No financial or scientific
authorization follows from successful offline routing tests.
