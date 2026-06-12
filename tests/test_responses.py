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


if __name__ == "__main__":
    unittest.main()
