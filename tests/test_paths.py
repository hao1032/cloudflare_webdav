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

    def test_normalize_path_decodes_utf8_chinese(self):
        self.assertEqual(paths.normalize_path("/%E4%B8%AD%E6%96%87"), "/中文")

    def test_normalize_path_decodes_gb18030_chinese(self):
        self.assertEqual(paths.normalize_path("/%D6%D0%CE%C4"), "/中文")

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

    def test_href_quotes_chinese_as_utf8(self):
        self.assertEqual(paths.href_for("/中文/文件.txt"), "/%E4%B8%AD%E6%96%87/%E6%96%87%E4%BB%B6.txt")


if __name__ == "__main__":
    unittest.main()
