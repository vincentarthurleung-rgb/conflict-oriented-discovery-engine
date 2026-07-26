# Local source asset recovery v1

One record classifies one deduplicated Source block. It records every local
asset checked, recovered section/caption references and hashes, remaining
gaps, affected targets/observations, and immutable provenance.

`execution_authorized` and `network_authorized` are always false. A supplement
reference is recorded as reference-only and never treated as supplement
content. Recovery never changes historical Source or Provider-input authority.

