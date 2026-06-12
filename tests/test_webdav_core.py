import base64
import asyncio
import importlib
import json
import sys
import types
import unittest


class FakeResponse:
    def __init__(self, body="", status=200, headers=None):
        self.body = body
        self.status = status
        self.headers = headers or {}


workers = types.ModuleType("workers")
workers.Response = FakeResponse
workers.WorkerEntrypoint = object
sys.modules["workers"] = workers

main = importlib.import_module("src.main")
storage = importlib.import_module("src.r2")
responses = importlib.import_module("src.responses")
auth = importlib.import_module("src.auth")
main.Response = FakeResponse
responses.Response = FakeResponse


class Headers(dict):
    def get(self, key, default=None):
        return super().get(key.lower(), default)


class FakeRequest:
    def __init__(self, method="GET", path="/", headers=None, body=b""):
        self.method = method
        self.url = "https://example.test" + path
        self.headers = Headers({key.lower(): value for key, value in (headers or {}).items()})
        self.body = body


class FakeMetadata:
    def __init__(self, content_type=None):
        self.contentType = content_type


class FakeObject:
    def __init__(self, key, body=b"", content_type=None):
        self.key = key
        self.body = body
        self.size = len(body)
        self.etag = "etag-" + key
        self.httpEtag = '"' + self.etag + '"'
        self.uploaded = None
        self.httpMetadata = FakeMetadata(content_type) if content_type else None

    async def arrayBuffer(self):
        return self.body


class FakeArrayBuffer:
    def __init__(self, body):
        self.body = body

    def to_py(self):
        return self.body

    def __str__(self):
        return "[object ArrayBuffer]"


class FakeArrayBufferObject(FakeObject):
    async def arrayBuffer(self):
        return FakeArrayBuffer(self.body)


class FakeListing:
    def __init__(self, objects):
        self.objects = objects
        self.truncated = False
        self.cursor = None


class FakeBucket:
    def __init__(self):
        self.objects = {}

    async def head(self, key):
        return self.objects.get(key)

    async def get(self, key):
        return self.objects.get(key)

    async def put(self, key, body, **options):
        if isinstance(body, str):
            body = body.encode()
        content_type = (options.get("httpMetadata") or {}).get("contentType")
        self.objects[key] = FakeObject(key, body, content_type=content_type)

    async def delete(self, key_or_keys):
        keys = key_or_keys if isinstance(key_or_keys, list) else [key_or_keys]
        for key in keys:
            self.objects.pop(key, None)

    async def list(self, prefix="", limit=1000, cursor=None):
        matches = [obj for key, obj in sorted(self.objects.items()) if key.startswith(prefix)]
        return FakeListing(matches[:limit])


class WebDAVCoreTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.bucket = FakeBucket()
        self.worker = main.Default()
        self.worker.env = types.SimpleNamespace(WEBDAV_BUCKET=self.bucket)

    def auth_request(self, username="admin", password="secret"):
        token = base64.b64encode(f"{username}:{password}".encode()).decode()
        return FakeRequest("GET", "/", headers={"Authorization": f"Basic {token}"})

    async def auth_state(self):
        obj = self.bucket.objects.get(auth.AUTH_STATE_KEY)
        self.assertIsNotNone(obj)
        return json.loads(obj.body.decode())

    async def test_implicit_directory_is_collection(self):
        await self.bucket.put("docs/file.txt", b"hello")

        self.assertTrue(await storage.is_collection(self.bucket, "/docs"))
        response = await self.worker.delete(self.bucket, "/docs")

        self.assertEqual(response.status, 204)
        self.assertEqual(self.bucket.objects, {})

    async def test_mkcol_allows_implicit_parent(self):
        await self.bucket.put("docs/file.txt", b"hello")

        response = await self.worker.mkcol(self.bucket, "/docs/child")

        self.assertEqual(response.status, 201)
        self.assertIn("docs/child/.dir", self.bucket.objects)

    async def test_dir_marker_is_listed_as_directory(self):
        await self.bucket.put("empty/.dir", b"")
        await self.bucket.put("nested/child/.dir", b"")

        directories, files = await storage.list_children(self.bucket, "")

        self.assertIn(("empty", "empty/"), directories)
        self.assertIn(("nested", "nested/"), directories)
        self.assertEqual(files, [])

    async def test_current_dir_marker_is_hidden_inside_directory(self):
        await self.bucket.put("empty/.dir", b"")

        directories, files = await storage.list_children(self.bucket, "empty/")

        self.assertEqual(directories, [])
        self.assertEqual(files, [])

    async def test_copy_file_uses_r2_object_and_preserves_content_type(self):
        await self.bucket.put("src.txt", b"hello", httpMetadata={"contentType": "text/plain"})
        request = FakeRequest(
            "COPY",
            "/src.txt",
            headers={"Destination": "https://example.test/dst.txt"},
        )

        response = await self.worker.move_or_copy(self.bucket, request, "/src.txt", move=False)

        self.assertEqual(response.status, 201)
        copied = self.bucket.objects["dst.txt"]
        self.assertEqual(copied.body, b"hello")
        self.assertEqual(copied.httpMetadata.contentType, "text/plain")

    async def test_move_implicit_directory_copies_children_and_deletes_source(self):
        await self.bucket.put("src/a.txt", b"a")
        await self.bucket.put("src/nested/b.txt", b"b")
        request = FakeRequest(
            "MOVE",
            "/src/",
            headers={"Destination": "https://example.test/dst/"},
        )

        response = await self.worker.move_or_copy(self.bucket, request, "/src", move=True)

        self.assertEqual(response.status, 201)
        self.assertNotIn("src/a.txt", self.bucket.objects)
        self.assertEqual(self.bucket.objects["dst/a.txt"].body, b"a")
        self.assertEqual(self.bucket.objects["dst/nested/b.txt"].body, b"b")
        self.assertIn("dst/.dir", self.bucket.objects)

    async def test_copy_respects_overwrite_false(self):
        await self.bucket.put("src.txt", b"src")
        await self.bucket.put("dst.txt", b"dst")
        request = FakeRequest(
            "COPY",
            "/src.txt",
            headers={"Destination": "https://example.test/dst.txt", "Overwrite": "F"},
        )

        response = await self.worker.move_or_copy(self.bucket, request, "/src.txt", move=False)

        self.assertEqual(response.status, 412)
        self.assertEqual(self.bucket.objects["dst.txt"].body, b"dst")

    async def test_browser_get_markdown_returns_preview(self):
        await self.bucket.put("readme.md", b"# Title\n\n```py\nprint('hi')\n```", httpMetadata={"contentType": "text/markdown"})
        request = FakeRequest("GET", "/readme.md", headers={"Accept": "text/html"})

        response = await self.worker.get(self.bucket, request, "/readme.md")

        self.assertEqual(response.status, 200)
        self.assertIn("<article", response.body)
        self.assertIn("<h1>Title</h1>", response.body)
        self.assertIn("?raw=1", response.body)

    async def test_markdown_preview_decodes_array_buffer(self):
        self.bucket.objects["readme.md"] = FakeArrayBufferObject("readme.md", b"# Title")
        request = FakeRequest("GET", "/readme.md", headers={"Accept": "text/html"})

        response = await self.worker.get(self.bucket, request, "/readme.md")

        self.assertIn("<h1>Title</h1>", response.body)
        self.assertNotIn("[object ArrayBuffer]", response.body)

    async def test_browser_get_image_returns_preview(self):
        await self.bucket.put("image.png", b"png", httpMetadata={"contentType": "image/png"})
        request = FakeRequest("GET", "/image.png", headers={"Accept": "text/html"})

        response = await self.worker.get(self.bucket, request, "/image.png")

        self.assertEqual(response.status, 200)
        self.assertIn('<img class="image-preview"', response.body)
        self.assertIn("/image.png?raw=1", response.body)

    async def test_raw_query_returns_original_body(self):
        await self.bucket.put("readme.md", b"# Title", httpMetadata={"contentType": "text/markdown"})
        request = FakeRequest("GET", "/readme.md?raw=1", headers={"Accept": "text/html"})

        response = await self.worker.get(self.bucket, request, "/readme.md")

        self.assertEqual(response.status, 200)
        self.assertEqual(response.body, b"# Title")

    async def test_auth_failures_lock_after_three_attempts(self):
        self.worker.env.WEBDAV_USERNAME = "admin"
        self.worker.env.WEBDAV_PASSWORD = "secret"

        self.assertEqual((await self.worker.authorize(self.bucket, self.auth_request(password="bad"))).status, 401)
        self.assertEqual((await self.worker.authorize(self.bucket, self.auth_request(password="bad"))).status, 401)
        response = await self.worker.authorize(self.bucket, self.auth_request(password="bad"))
        state = await self.auth_state()

        self.assertEqual(response.status, 429)
        self.assertEqual(state["count"], 3)
        self.assertGreater(state["blocked_until"], 0)

    async def test_auth_lock_blocks_correct_password(self):
        self.worker.env.WEBDAV_USERNAME = "admin"
        self.worker.env.WEBDAV_PASSWORD = "secret"
        await self.bucket.put(
            auth.AUTH_STATE_KEY,
            json.dumps({"count": 3, "first_failed_at": 1, "blocked_until": 9999999999}),
            httpMetadata={"contentType": "application/json"},
        )

        response = await self.worker.authorize(self.bucket, self.auth_request())

        self.assertEqual(response.status, 429)

    async def test_successful_auth_clears_failure_count(self):
        self.worker.env.WEBDAV_USERNAME = "admin"
        self.worker.env.WEBDAV_PASSWORD = "secret"
        await self.bucket.put(
            auth.AUTH_STATE_KEY,
            json.dumps({"count": 2, "first_failed_at": 1, "blocked_until": 0}),
            httpMetadata={"contentType": "application/json"},
        )

        response = await self.worker.authorize(self.bucket, self.auth_request())
        state = await self.auth_state()

        self.assertIsNone(response)
        self.assertEqual(state["count"], 0)
        self.assertEqual(state["first_failed_at"], 0)

    async def test_debug_errors_returns_traceback(self):
        self.worker.env.DEBUG_ERRORS = "1"
        delattr(self.worker.env, "WEBDAV_BUCKET")

        response = await self.worker.fetch(FakeRequest("GET", "/"))

        self.assertEqual(response.status, 500)
        self.assertIn("Traceback", response.body)


if __name__ == "__main__":
    unittest.main()
