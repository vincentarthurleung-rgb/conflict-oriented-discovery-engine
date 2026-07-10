import unittest
from pathlib import Path

STATIC=Path("src/code_engine/system_b/explorer/static")


class AtlasLibraryStaticTests(unittest.TestCase):
    def test_library_uses_local_storage_namespace_and_discloses_browser_storage(self):
        js=(STATIC/"app.js").read_text(encoding="utf-8")
        self.assertIn("function libraryKey",js)
        self.assertIn("atlasSession.username",js)
        self.assertIn("localStorage.setItem(libraryKey",js)
        self.assertIn("保存在当前浏览器",js)
        self.assertNotIn("csrf_token",js.split("function saveLibraryItem",1)[1].split("function deleteLibraryItem",1)[0])


if __name__=="__main__":
    unittest.main()
