import importlib
import sys
import types
import unittest


workers = types.ModuleType("workers")
workers.Response = object
workers.WorkerEntrypoint = object
sys.modules["workers"] = workers

paths = importlib.import_module("src.paths")


class PathTests(unittest.TestCase):
    def test_normalize_path_collapses_segments(self):
        self.assertEqual(paths.normalize_path("/a/b/../c"), "/a/c")
        self.assertEqual(paths.normalize_path("/a//./b"), "/a/b")

    def test_normalize_path_prevents_escape_above_root(self):
        self.assertEqual(paths.normalize_path("/../../secret"), "/secret")

    def test_object_and_marker_keys(self):
        self.assertEqual(paths.object_key("/"), "")
        self.assertEqual(paths.object_key("/docs/file.txt"), "docs/file.txt")
        self.assertEqual(paths.dir_marker_key("/docs"), "docs/.dir")

    def test_parent_path(self):
        self.assertEqual(paths.parent_path("/"), "/")
        self.assertEqual(paths.parent_path("/file.txt"), "/")
        self.assertEqual(paths.parent_path("/a/b.txt"), "/a")

    def test_href_quotes_spaces_but_keeps_slashes(self):
        self.assertEqual(paths.href_for("/a dir/file name.txt"), "/a%20dir/file%20name.txt")


if __name__ == "__main__":
    unittest.main()
