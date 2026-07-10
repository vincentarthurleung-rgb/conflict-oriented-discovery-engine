# C.O.D.E. Atlas Backup And Recovery

Create an online SQLite backup:

```bash
python -m code_engine.cli.atlas_db_backup --database-url sqlite:///data/code_atlas.db
```

Restore requires explicit confirmation:

```bash
python -m code_engine.cli.atlas_db_restore \
  --database-url sqlite:///data/code_atlas.db \
  --backup-file data/backups/code_atlas_YYYYMMDDTHHMMSSZ.db \
  --confirm-restore
```

Restore first backs up the current database when it exists. Backup manifests include SHA-256. Daily backups are recommended for single-server production use.

