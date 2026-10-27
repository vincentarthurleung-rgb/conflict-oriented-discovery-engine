# Pilot case execution boundary V1

`PilotCaseExecutor.run(request)` owns one case, a frozen request fingerprint, thirteen chained stage states and one terminal package. It uses existing Builder/Quality validators, experimental V3/Core gates, normalization, Evidence Projection and Shadow comparison. `pilot_delivery` extends the existing Atlas review infrastructure to whole attempts, including empty and unsuccessful attempts. It does not confer scientific authority.

The executable provided by this change is **offline only**:

```
python tools/replay_pilot_release_candidate.py --manifest <frozen-offline-manifest.json> --output <new-development-output>
```

The manifest pins authentic source packets, native Core revisions, historical AI reviews, source articles and frozen Builder/Quality request contracts. Builder/Quality responses are explicitly labeled deterministic engineering stubs. Replayed scientific reviews are not newly independent reviews. No fictional positive contradiction is accepted as scientific evidence.

## Backend boundary and current limitation

The executor takes a backend with `fingerprint`, `fixture`, `select_sources(request)`, `acquire(spec)`, `builder_request(bundle)`, `quality_request(bundle, builder_manifest, response)` and `complete(stage, source_key, payload, provider, model, max_output_tokens)` interfaces. The only concrete backend supplied here is `FrozenReplayBackend`. It reads pinned local assets and never invokes a provider or acquisition client.

A non-fixture backend binding the existing prospective-acquisition controller and actual configured model/extraction clients is **not supplied**. In particular, replaying a pre-existing native Core envelope is not implementation or validation of unattended new-source Core reconstruction. No live ten-case launch readiness is claimed.

Every paid backend completion must pass the executor's shared reservation, dispatch and settlement controller; neither request preparation nor source selection may make hidden model calls. Experimental draft output must contain actual source-bound packet/Core bytes, or report no complete record. Native source hashes and references are checked before projection. Missing native records remain insufficient evidence. No science is synthesized to fill them.

## Historical exclusions

`freeze_pilot_historical_seen.py` scans available historical roots, including archives, retained case bundles, structured captures and read-only copies of SQLite databases with WAL. All bytes are inventoried. Parseable identities in engineering trees are conservatively included too; malformed declared engineering fixtures receive explicit hashed dispositions. Malformed real ledgers and unresolved nonempty response captures prevent certification.

The current development directory is explicitly outside historical scope. A registry certifies its named available snapshot, never unavailable external histories or undisclosed identities. Exact textual PMC identifiers and untyped NCBI UID captures are conservative exclusions, not assertions of equivalence or bibliographic mappings. Candidate identity tracking remains separate from source-level exclusion.

For new attempts, source identity is checked before acquisition and registered persistently before any source dispatch. The acquired ArticleJSON hash and every required identifier are checked again before handoff. Unknown or incomplete required bindings fail closed. A separate persistent prospective-exposure ledger retains failed/partial attempts; another case cannot reuse them as new. Offline replay intentionally uses historical sources and cannot switch into new-pilot execution with fixture configuration.

## Budget boundary

The SQLite budget ledger serializes reservations across cases/processes, binds configuration, reserves conservative complete token limits before dispatch, retains uncertain reservations, accounts retries, blocks duplicate dispatch and freezes on unverifiable usage. Cost uses verified fixture rates in offline acceptance. Financial caps round down and charges round up at nanodollar precision.

Offline fixture values are not market prices or spending approval. Live mode requires an owner-supplied, hash-bound budget configuration approval, explicit model/provider/prices and nonzero verified rates. No such live artifact is created by these tools. Work usage is separate from this controller. The previous US$100 proposal remains unapproved.

## Delivery and authority

Cases retain executed/skipped/blocked/failed stages and their reasons. Interrupted dispatch recovers as a failed attempt with outstanding reservations; it never implicitly reruns a paid request. Same-case execution is serialized and completed attempts are reused only for the exact input/backend/budget/implementation fingerprint.

Atlas case packages bind their artifacts, stage chain, source selection, pair packages and costs. A provisional contradiction requires a valid existing source-reviewed Shadow pair. Empty cases cannot acquire fabricated pair evidence. Existing scientific authorization, Human Gold and Strict Core gates remain unchanged; all development authority flags remain false. Production import is disabled.
