import os
import tempfile
import unittest
from pathlib import Path

from alembic import command
from alembic.config import Config

from code_engine.cli.atlas_db_backup import main as backup_main
from code_engine.cli.atlas_db_restore import main as restore_main


def migrate(url):
    os.environ["ATLAS_DATABASE_URL"] = url
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")


class AtlasBackupRestoreTests(unittest.TestCase):
    def test_backup_and_restore_require_explicit_confirmation(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "atlas.db"
            url = f"sqlite:///{db}"
            migrate(url)
            out = Path(tmp) / "backups"
            backup_main(["--database-url", url, "--output-dir", str(out)])
            backup = next(out.glob("*.db"))
            with self.assertRaises(ValueError):
                restore_main(["--database-url", url, "--backup-file", str(backup)])
            restore_main(["--database-url", url, "--backup-file", str(backup), "--confirm-restore"])
            self.assertTrue(db.exists())


if __name__ == "__main__":
    unittest.main()
