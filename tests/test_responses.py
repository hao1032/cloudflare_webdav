import importlib
import sys
import types
import unittest
from datetime import datetime, timezone


workers = types.ModuleType("workers")
workers.Response = object
workers.WorkerEntrypoint = object
sys.modules["workers"] = workers

responses = importlib.import_module("src.responses")


class ResponseFormattingTests(unittest.TestCase):
    def test_format_modified_uses_beijing_time(self):
        timestamp = datetime(2026, 6, 12, 4, 40, 31, tzinfo=timezone.utc)

        self.assertEqual(responses.format_modified(timestamp), "2026-06-12 12:40 CST")

    def test_format_modified_handles_js_date(self):
        class JsDate:
            def getTime(self):
                return 1781239216000

        self.assertEqual(responses.format_modified(JsDate()), "2026-06-12 12:40")

    def test_directory_row_uses_svg_icon(self):
        row = responses.directory_row("app", "/app/", is_dir=True)

        self.assertIn('<svg class="icon dir"', row)
        self.assertNotIn('<span class="icon', row)


if __name__ == "__main__":
    unittest.main()
