# Experimental Core Projection v2

`experimental_core_projection_v2` is immutable and `lossless_by_reference=true`. It must reference its structured Observation revision and all Factor, Measurement, Result, and Linkage records. A denormalized summary, if present, is non-authoritative. Historical Evidence Projection content remains unchanged; compatibility is supplied by `experimental_core_projection_compatibility_sidecar_v1`.

Readiness can reach `ready_for_offline_consumer_validation`; production activation is outside this contract.
