# Experimental Factor, Measurement, and Result v1

`experimental_factor_record_v1` unifies interventions, exposures, genetic
manipulations, conditions, cohorts, groups, controls, comparators, and baselines
without deleting legacy `interventions`. Species, tissue, cell line, and assay
are not automatically factors.

`measurement_record_v1` preserves measured entity, endpoint/property, method,
unit, sample, localization, assay context, and evidence. Missing method is a
limitation; missing measurement blocks a formal experimental record.

`observed_result_record_v1` preserves qualitative, directional, quantitative,
statistical, uncertainty, and evidence layers separately. Every reusable result
must reference a measurement. Comparative results must reference a control,
comparator, or baseline.

All three records preserve raw, extracted, and canonical layers independently.
No canonical value overwrites its source layers.

