import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock


render = importlib.import_module("scripts.render_wrangler_config")


class WranglerConfigTests(unittest.TestCase):
    def test_render_does_not_write_password_var(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "wrangler.toml"
            env = {
                "WORKER_NAME": "webdav-test",
                "R2_BUCKET_NAME": "bucket",
                "WEBDAV_USERNAME": "admin",
                "WEBDAV_PASSWORD": "super-private-token",
            }

            with mock.patch.object(render, "OUTPUT", output):
                with mock.patch.dict(os.environ, env, clear=True):
                    render.main()

            rendered = output.read_text(encoding="utf-8")
            self.assertIn('WEBDAV_USERNAME = "admin"', rendered)
            self.assertNotIn("WEBDAV_PASSWORD", rendered)
            self.assertNotIn("super-private-token", rendered)


if __name__ == "__main__":
    unittest.main()
