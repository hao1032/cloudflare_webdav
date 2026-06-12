import importlib
import sys
import types
import unittest
from datetime import datetime, timezone


workers = types.ModuleType("workers")
workers.Response = object
workers.WorkerEntrypoint = object
sys.modules["workers"] = workers

web = importlib.import_module("src.web")


class ResponseFormattingTests(unittest.TestCase):
    def test_format_modified_uses_beijing_time(self):
        timestamp = datetime(2026, 6, 12, 4, 40, 31, tzinfo=timezone.utc)

        self.assertEqual(web.format_modified(timestamp), "2026-06-12 12:40")

    def test_format_modified_handles_js_date(self):
        class JsDate:
            def getTime(self):
                return 1781239216000

        self.assertEqual(web.format_modified(JsDate()), "2026-06-12 12:40")

    def test_directory_row_uses_svg_icon(self):
        row = web.directory_row("app", "/app/", is_dir=True)

        self.assertIn('<svg class="icon dir"', row)
        self.assertNotIn('<span class="icon', row)

    def test_preview_kind_detects_common_files(self):
        self.assertEqual(web.preview_kind("/a/readme.md"), "markdown")
        self.assertEqual(web.preview_kind("/a/app.py"), "code")
        self.assertEqual(web.preview_kind("/a/photo.jpg"), "image")
        self.assertEqual(web.preview_kind("/a/file.bin"), None)


if __name__ == "__main__":
    unittest.main()
