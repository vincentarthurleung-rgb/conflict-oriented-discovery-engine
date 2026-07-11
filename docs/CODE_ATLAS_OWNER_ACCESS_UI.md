# C.O.D.E. Atlas Owner Access UI

Owner Control Center keeps account management separate from contribution tracking:

- `/owner/people` and `/owner/users`: account list, responsibility chain, temporary passwords, reset links, disable/enable, role changes, session revocation.
- `/owner/invites`: invite creation, disable/enable, usage status.
- `/owner/security`: security rules and non-deletion policy.
- `/owner/projects`: Pilot setup and namespace correction.

Dangerous operations require confirmation in the browser and are enforced again by Owner-only API checks. Admin, developer, reviewer, and pharma users receive `403` from `/owner` and `/api/owner/*`.
