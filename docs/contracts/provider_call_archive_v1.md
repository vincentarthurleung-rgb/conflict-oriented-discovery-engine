# Provider Call Archive v1

The archive separates a secret-free call specification, a stable attempt state
machine, and immutable raw bytes. The dedup identity binds snapshot, rendered
prompt, model, non-secret parameters, response schema, and tool schema. Parser
version is not part of the paid-call identity unless it changes the response
contract.

The persistence order is: dedup lookup, prepared attempt, explicit call
authorization, provider call, atomic raw-byte persistence and hash, then parse.
Invalid JSON is still a valid raw archive asset. Parse/schema/normalization
failure cannot transition back to `provider_in_flight`.
