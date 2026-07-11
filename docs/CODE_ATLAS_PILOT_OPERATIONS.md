# C.O.D.E. Atlas Pilot Operations

Pilot setup is handled from `/owner/projects`.

Pilot projects use `namespace=pilot`; the wizard must not create production projects. Pilot metrics and exports are operational readiness artifacts and are not paper-ready production metrics. Production projects should be created only after Pilot completion and frozen protocol/schema review.

The current persistent database was corrected from an empty production-namespaced Pilot Readiness project to `namespace=pilot` through an audited service because it had no annotations.
