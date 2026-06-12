from traceback import format_exc
from time import time
from urllib.parse import urlsplit

from workers import Response, WorkerEntrypoint

try:
    from .auth import auth_required, clear_auth_failures, credentials_match, is_locked, read_auth_state, record_auth_failure
    from .dav import build_prop_response, etag_from_object, http_date, multistatus
    from .paths import (
        destination_path,
        dir_marker_key,
        href_for,
        normalize_path,
        object_key,
        parent_path,
    )
    from .r2 import (
        collection_exists,
        copy_object,
        copy_prefix,
        delete_prefix,
        is_collection,
        list_children,
        object_exists,
        r2_exists,
    )
    from .responses import (
        dav_response,
        html_response,
        response,
        text_response,
    )
    from .web import directory_page, directory_row, format_modified, format_size, preview_kind, preview_page
except ImportError:
    from auth import auth_required, clear_auth_failures, credentials_match, is_locked, read_auth_state, record_auth_failure
    from dav import build_prop_response, etag_from_object, http_date, multistatus
    from paths import (
        destination_path,
        dir_marker_key,
        href_for,
        normalize_path,
        object_key,
        parent_path,
    )
    from r2 import (
        collection_exists,
        copy_object,
        copy_prefix,
        delete_prefix,
        is_collection,
        list_children,
        object_exists,
        r2_exists,
    )
    from responses import (
        dav_response,
        html_response,
        response,
        text_response,
    )
    from web import directory_page, directory_row, format_modified, format_size, preview_kind, preview_page


def requested_depth(request):
    depth = request.headers.get("depth")
    return "0" if depth == "0" else "1"


def unauthorized():
    return text_response(
        "Authentication required",
        status=401,
        extra_headers={"www-authenticate": 'Basic realm="Cloudflare R2 WebDAV"'},
    )


def auth_locked_response(state):
    return text_response(
        "Too many authentication failures",
        status=429,
        extra_headers={"retry-after": str(max(1, int(state.get("blocked_until", 0)) - int(time())))},
    )


def request_method(request):
    js_object = getattr(request, "js_object", None)
    method = getattr(js_object, "method", None)
    if method:
        return str(method).upper()
    return request.method.upper()


def accepts_html(request):
    accept = request.headers.get("accept") or ""
    return "text/html" in accept or "application/xhtml+xml" in accept


def raw_requested(request):
    return "raw=1" in (urlsplit(request.url).query or "")


def object_content_type(obj):
    metadata = getattr(obj, "httpMetadata", None)
    return getattr(metadata, "contentType", "") if metadata else ""


def decode_buffer(data):
    if isinstance(data, str):
        return data
    if isinstance(data, bytes):
        return data.decode("utf-8", errors="replace")
    if isinstance(data, bytearray):
        return bytes(data).decode("utf-8", errors="replace")
    to_py = getattr(data, "to_py", None)
    if callable(to_py):
        return bytes(to_py()).decode("utf-8", errors="replace")
    try:
        from js import Uint8Array

        view = Uint8Array.new(data)
        view_to_py = getattr(view, "to_py", None)
        if callable(view_to_py):
            return bytes(view_to_py()).decode("utf-8", errors="replace")
        return bytes(view).decode("utf-8", errors="replace")
    except Exception:
        try:
            return bytes(data).decode("utf-8", errors="replace")
        except Exception:
            return str(data)


async def object_text(obj):
    body = getattr(obj, "body", None)
    if hasattr(body, "text"):
        return await body.text()
    data = await obj.arrayBuffer()
    return decode_buffer(data)


class Default(WorkerEntrypoint):
    async def fetch(self, request):
        try:
            return await self.handle(request)
        except Exception:
            env = getattr(self, "env", None)
            if getattr(env, "DEBUG_ERRORS", ""):
                return text_response(format_exc(), status=500)
            return text_response("Internal server error", status=500)

    async def handle(self, request):
        bucket = self.env.WEBDAV_BUCKET
        method = request_method(request)
        path = normalize_path(urlsplit(request.url).path)

        if method == "OPTIONS":
            return self.options()

        auth_response = await self.authorize(bucket, request)
        if auth_response:
            return auth_response
        if method == "PROPFIND":
            return await self.propfind(bucket, request, path)
        if method in ("GET", "HEAD"):
            return await self.get(bucket, request, path, head_only=method == "HEAD")
        if method == "PUT":
            return await self.put(bucket, request, path)
        if method == "DELETE":
            return await self.delete(bucket, path)
        if method == "MKCOL":
            return await self.mkcol(bucket, path)
        if method == "MOVE":
            return await self.move_or_copy(bucket, request, path, move=True)
        if method == "COPY":
            return await self.move_or_copy(bucket, request, path, move=False)

        return text_response("Method not allowed", status=405)

    async def authorize(self, bucket, request):
        if not auth_required(self.env):
            return None
        state = await read_auth_state(bucket)
        now = int(time())
        if is_locked(state, now):
            return auth_locked_response(state)
        if credentials_match(request, self.env):
            await clear_auth_failures(bucket)
            return None
        state = await record_auth_failure(bucket)
        if is_locked(state, int(time())):
            return auth_locked_response(state)
        return unauthorized()

    def options(self):
        return response(
            "",
            status=204,
            headers={
                "allow": "OPTIONS, PROPFIND, GET, HEAD, PUT, DELETE, MKCOL, MOVE, COPY",
                "dav": "1",
                "ms-author-via": "DAV",
            },
        )

    async def propfind(self, bucket, request, path):
        depth = requested_depth(request)
        key = object_key(path)
        obj = await bucket.head(key) if key else None
        collection = await is_collection(bucket, path)

        if not r2_exists(obj) and not collection:
            return text_response("Not found", status=404)

        responses = [
            build_prop_response(
                href_for(path + ("/" if collection and not path.endswith("/") else "")),
                collection,
                size=getattr(obj, "size", 0) if r2_exists(obj) else 0,
                modified=getattr(obj, "uploaded", None) if r2_exists(obj) else None,
                etag=etag_from_object(obj) if r2_exists(obj) else None,
            )
        ]

        if collection and depth != "0":
            prefix = "" if path == "/" else key.rstrip("/") + "/"
            directories, files = await list_children(bucket, prefix)

            for _name, common_prefix in directories:
                child_path = "/" + common_prefix.rstrip("/")
                responses.append(build_prop_response(href_for(child_path + "/"), True))

            for item in files:
                child_path = "/" + item.key
                responses.append(
                    build_prop_response(
                        href_for(child_path),
                        False,
                        size=getattr(item, "size", 0),
                        modified=getattr(item, "uploaded", None),
                        etag=etag_from_object(item),
                    )
                )

        return dav_response(multistatus(responses))

    async def get(self, bucket, request, path, head_only=False):
        obj = await bucket.get(object_key(path))
        if not r2_exists(obj):
            if await collection_exists(bucket, path):
                if head_only:
                    return html_response("", extra_headers={"content-length": "0"})
                return await self.directory_listing(bucket, path)
            return text_response("Not found", status=404)

        headers = {
            "etag": etag_from_object(obj) or "",
            "last-modified": http_date(getattr(obj, "uploaded", None)),
        }
        content_type = getattr(obj, "httpMetadata", None)
        if content_type and getattr(content_type, "contentType", None):
            headers["content-type"] = content_type.contentType
        if head_only:
            headers["content-length"] = str(getattr(obj, "size", 0))
            return response("", status=200, headers=headers)
        if accepts_html(request) and not raw_requested(request):
            kind = preview_kind(path, headers.get("content-type", ""))
            if kind == "image":
                return html_response(
                    preview_page(
                        path,
                        kind,
                        "",
                        href_for(path) + "?raw=1",
                        size=format_size(getattr(obj, "size", 0)),
                        modified=format_modified(getattr(obj, "uploaded", None)),
                    )
                )
            if kind:
                return html_response(
                    preview_page(
                        path,
                        kind,
                        await object_text(obj),
                        href_for(path) + "?raw=1",
                        size=format_size(getattr(obj, "size", 0)),
                        modified=format_modified(getattr(obj, "uploaded", None)),
                    )
                )
        return Response(obj.body, status=200, headers=headers)

    async def directory_listing(self, bucket, path):
        key = object_key(path)
        prefix = "" if path == "/" else key.rstrip("/") + "/"
        directories, files = await list_children(bucket, prefix)
        rows = []

        if path != "/":
            rows.append(directory_row("..", href_for(parent_path(path) + "/"), is_dir=True))

        for name, common_prefix in directories:
            child_path = "/" + common_prefix.rstrip("/") + "/"
            rows.append(directory_row(name, href_for(child_path), is_dir=True))

        for item in files:
            name = item.key[len(prefix) :]
            rows.append(
                directory_row(
                    name,
                    href_for("/" + item.key),
                    size=format_size(getattr(item, "size", 0)),
                    modified=format_modified(getattr(item, "uploaded", None)),
                )
            )

        title = f"Index of {path if path.endswith('/') else path + '/'}"
        return html_response(directory_page(title, rows))

    async def put(self, bucket, request, path):
        if path == "/" or path.endswith("/"):
            return text_response("Use MKCOL to create collections", status=409)

        parent = parent_path(path)
        if parent != "/" and not await collection_exists(bucket, parent):
            return text_response("Parent collection does not exist", status=409)

        existed = r2_exists(await bucket.head(object_key(path)))
        await bucket.put(
            object_key(path),
            request.body,
            httpMetadata={"contentType": request.headers.get("content-type") or "application/octet-stream"},
        )
        return response("", status=204 if existed else 201)

    async def delete(self, bucket, path):
        if path == "/":
            return text_response("Refusing to delete root", status=403)

        key = object_key(path)
        if await is_collection(bucket, path):
            await delete_prefix(bucket, key.rstrip("/") + "/")
            return response("", status=204)

        if not r2_exists(await bucket.head(key)):
            return text_response("Not found", status=404)
        await bucket.delete(key)
        return response("", status=204)

    async def mkcol(self, bucket, path):
        if path == "/":
            return text_response("Root collection already exists", status=405)
        if await object_exists(bucket, path):
            return text_response("Already exists", status=405)
        parent = parent_path(path)
        if parent != "/" and not await collection_exists(bucket, parent):
            return text_response("Parent collection does not exist", status=409)
        await bucket.put(dir_marker_key(path), "")
        return response("", status=201)

    async def move_or_copy(self, bucket, request, path, move):
        destination = destination_path(request)
        if not destination:
            return text_response("Destination header required", status=400)
        if destination == path:
            return response("", status=204)
        if not await object_exists(bucket, path):
            return text_response("Not found", status=404)

        overwrite = (request.headers.get("overwrite") or "T").upper() != "F"
        if await object_exists(bucket, destination):
            if not overwrite:
                return text_response("Destination exists", status=412)
            await self.delete(bucket, destination)

        source_key = object_key(path)
        destination_key = object_key(destination)

        if await is_collection(bucket, path):
            source_prefix = source_key.rstrip("/") + "/"
            destination_prefix = destination_key.rstrip("/") + "/"
            await bucket.put(dir_marker_key(destination), "")
            await copy_prefix(bucket, source_prefix, destination_prefix)
            if move:
                await delete_prefix(bucket, source_prefix)
        else:
            if not await copy_object(bucket, source_key, destination_key):
                return text_response("Not found", status=404)
            if move:
                await bucket.delete(source_key)

        return response("", status=201)
