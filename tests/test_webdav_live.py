import base64
import os
import ssl
import unittest
from urllib.error import HTTPError
from urllib.parse import urljoin
from urllib.request import Request, urlopen


def env(name):
    return os.environ.get(name, "").strip()


class LiveWebDAVTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base_url = env("WEBDAV_TEST_URL").rstrip("/") + "/"
        cls.username = env("WEBDAV_USERNAME")
        cls.password = env("WEBDAV_PASSWORD")
        cls.prefix = env("WEBDAV_TEST_PREFIX") or f"codex-live-test-{os.getpid()}"
        cls.ssl_context = ssl._create_unverified_context() if env("WEBDAV_TEST_INSECURE") == "1" else None
        if not env("WEBDAV_TEST_URL"):
            raise unittest.SkipTest("WEBDAV_TEST_URL is not set")

    def request(self, method, path="/", body=None, headers=None, ok=(200, 201, 204, 207, 404)):
        url = urljoin(self.base_url, path.lstrip("/"))
        request_headers = {"User-Agent": "curl/8.0 webdav-live-test"}
        request_headers.update(headers or {})
        if self.username or self.password:
            token = base64.b64encode(f"{self.username}:{self.password}".encode()).decode()
            request_headers["Authorization"] = f"Basic {token}"

        req = Request(url, data=body, headers=request_headers, method=method)
        try:
            with urlopen(req, timeout=30, context=self.ssl_context) as res:
                data = res.read()
                status = res.status
                response_headers = dict(res.headers)
        except HTTPError as err:
            data = err.read()
            status = err.code
            response_headers = dict(err.headers)

        if status not in ok:
            self.fail(f"{method} {url} returned {status}: {data[:500]!r}")
        return status, response_headers, data

    def test_common_file_operations(self):
        directory = f"{self.prefix}/"
        hello = f"{directory}hello.txt"
        copy = f"{directory}copy.txt"
        moved = f"{directory}moved.txt"
        body = b"codex-live-upload"

        self.request("DELETE", directory, ok=(204, 404))
        self.request("OPTIONS", "/")
        self.request("PROPFIND", "/", headers={"Depth": "0"})
        self.request("MKCOL", directory)

        self.request("PROPFIND", directory, headers={"Depth": "0"})
        self.request("PUT", hello, body=body, headers={"Content-Type": "text/plain"})

        _status, _headers, downloaded = self.request("GET", hello)
        self.assertEqual(downloaded, body)
        self.request("HEAD", hello)

        self.request(
            "COPY",
            hello,
            headers={"Destination": urljoin(self.base_url, copy)},
        )
        _status, _headers, copied = self.request("GET", copy)
        self.assertEqual(copied, body)

        self.request(
            "MOVE",
            copy,
            headers={"Destination": urljoin(self.base_url, moved)},
        )
        self.request("GET", copy, ok=(404,))
        _status, _headers, moved_body = self.request("GET", moved)
        self.assertEqual(moved_body, body)

        self.request("DELETE", hello)
        self.request("DELETE", moved)
        self.request("DELETE", directory)


if __name__ == "__main__":
    unittest.main()
