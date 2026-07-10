# C.O.D.E. Atlas Owner Control Center

Owner routes:

```text
/owner
/api/owner/*
```

All owner APIs require server-side `role == owner`. Admin, developer, reviewer, pharma, and anonymous users receive `403`.

The initial overview reports user counts, reviewer counts, annotation namespace distribution, assignment count, review item count, frozen Gold count, audit event count, and deterministic data-quality warnings. It does not expose owner-only people analytics to non-owner roles.

Only one enabled owner is valid. The owner can be recorded in `system_settings.owner_user_id`.

