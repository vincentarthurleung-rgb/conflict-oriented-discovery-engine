# C.O.D.E. Atlas Deployment

Initialize:

```bash
python -m code_engine.cli.atlas_db_init --database-url sqlite:///data/code_atlas.db
```

Migrate:

```bash
alembic upgrade head
alembic current
```

Create the only enabled owner:

```bash
ATLAS_OWNER_PASSWORD='change-this' \
python -m code_engine.cli.atlas_user_admin create-owner \
  --database-url sqlite:///data/code_atlas.db \
  --username vincent \
  --display-name "Vincent" \
  --password-env ATLAS_OWNER_PASSWORD
```

Start with the database required:

```bash
python -m code_engine.cli.system_b_serve_knowledge_explorer \
  --display-kg-root system_b_outputs/three_case_clean_kg_v3 \
  --review-root system_b_outputs/three_case_review \
  --database-url sqlite:///data/code_atlas.db \
  --require-database \
  --require-auth \
  --users-file configs/atlas_users.json
```

Do not place the SQLite file under `static/`. Do not expose the database URL to the browser.

