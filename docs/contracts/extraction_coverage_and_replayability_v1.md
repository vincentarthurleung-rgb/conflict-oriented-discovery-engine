# Extraction Coverage and Replayability v1

The coverage ledger is one row per parsed/legacy candidate and capture-profile
field. It distinguishes prompt request, schema representability, provider
return, raw/parsed preservation, evidence, anchor precision, value state,
validation, normalization, and source presence. Provider omission defaults
source presence to `unknown`.

Replay status distinguishes fully zero-API replay, replay from raw response,
parsed-only replay, partial replay, provider re-extraction, source reingestion,
and invalid assets. Parsed-only never claims recovery of a field the provider
output did not preserve.
