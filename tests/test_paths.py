import importlib
import sys
import types
import unittest


workers = types.ModuleType("workers")
workers.Response = object
workers.WorkerEntrypoint = object
sys.modules.setdefault("workers", workers)

main = importlib.import_module("src.main")


class PathTests(unittest.TestCase):
    def test_normalize_path_collapses_segments(self):
        self.assertEqual(main.normalize_path("/a/b/../c"), "/a/c")
        self.assertEqual(main.normalize_path("/a//./b"), "/a/b")

    def test_normalize_path_prevents_escape_above_root(self):
        self.assertEqual(main.normalize_path("/../../secret"), "/secret")

    def test_object_and_marker_keys(self):
        self.assertEqual(main.object_key("/"), "")
        self.assertEqual(main.object_key("/docs/file.txt"), "docs/file.txt")
        self.assertEqual(main.dir_marker_key("/docs"), "docs/.dir")

    def test_parent_path(self):
        self.assertEqual(main.parent_path("/"), "/")
        self.assertEqual(main.parent_path("/file.txt"), "/")
        self.assertEqual(main.parent_path("/a/b.txt"), "/a")

    def test_href_quotes_spaces_but_keeps_slashes(self):
        self.assertEqual(main.href_for("/a dir/file name.txt"), "/a%20dir/file%20name.txt")


if __name__ == "__main__":
    unittest.main()
