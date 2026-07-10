# C.O.D.E. Atlas Database Architecture

System A artifacts remain JSON/JSONL and read-only. The Atlas SQLite database stores System B interaction state: users, invites, projects, review item indexes, assignments, annotations, audit events, adjudication, Gold records, metric runs, and export provenance.

Default database URL:

```bash
sqlite:///data/code_atlas.db
```

Override with `ATLAS_DATABASE_URL` or `--database-url`.

SQLite is configured with:

```text
foreign_keys=ON
journal_mode=WAL
busy_timeout=10000
synchronous=NORMAL
```

All schema changes go through Alembic. The current migration head is `0005_metrics_and_audit`.

