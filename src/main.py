from base64 import b64decode
from email.utils import formatdate
from html import escape
from traceback import format_exc
from urllib.parse import quote, unquote, urlsplit

from workers import Response, WorkerEntrypoint


DAV_NS = "DAV:"


def normalize_path(raw_path):
    decoded = unquote(raw_path or "/")
    parts = []
    for part in decoded.split("/"):
        if not part or part == ".":
            continue
        if part == "..":
            if parts:
                parts.pop()
            continue
        parts.append(part)
    return "/" + "/".join(parts)


def object_key(path):
    path = normalize_path(path)
    if path == "/":
        return ""
    return path.strip("/")


def dir_marker_key(path):
    key = object_key(path)
    if not key:
        return ""
    return key.rstrip("/") + "/.dir"


def href_for(path):
    normalized = normalize_path(path)
    if normalized != "/" and path.endswith("/"):
        normalized += "/"
    return quote(normalized, safe="/")


def parent_path(path):
    normalized = normalize_path(path)
    if normalized == "/":
        return "/"
    parent = normalized.rsplit("/", 1)[0]
    return parent or "/"


def is_hidden_marker(key):
    return key.endswith("/.dir")


def http_date(timestamp):
    if not timestamp:
        return formatdate(usegmt=True)
    if hasattr(timestamp, "timestamp"):
        return formatdate(timestamp.timestamp(), usegmt=True)
    return formatdate(usegmt=True)


def etag_from_object(obj):
    http_etag = getattr(obj, "httpEtag", None)
    etag = getattr(obj, "etag", None)
    return http_etag or (f'"{etag}"' if etag else None)


def response(body="", status=200, headers=None):
    return Response(body, status=status, headers=headers or {})


def text_response(body, status=200, extra_headers=None):
    headers = {"content-type": "text/plain; charset=utf-8"}
    if extra_headers:
        headers.update(extra_headers)
    return response(body, status=status, headers=headers)


def dav_response(xml_body, status=207):
    return response(
        xml_body,
        status=status,
        headers={"content-type": 'application/xml; charset="utf-8"'},
    )


def html_response(html_body, status=200, extra_headers=None):
    headers = {"content-type": "text/html; charset=utf-8"}
    if extra_headers:
        headers.update(extra_headers)
    return response(html_body, status=status, headers=headers)


def format_size(size):
    value = float(size or 0)
    for unit in ("B", "KiB", "MiB", "GiB"):
        if value < 1024 or unit == "GiB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GiB"


def html_page(title, rows):
    body_rows = "\n".join(rows) or '<tr><td colspan="3" class="empty">Empty directory</td></tr>'
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <style>
    :root {{ color-scheme: light dark; }}
    body {{ font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 2rem; line-height: 1.45; }}
    main {{ max-width: 960px; margin: 0 auto; }}
    h1 {{ font-size: 1.5rem; margin: 0 0 1rem; word-break: break-word; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ border-bottom: 1px solid color-mix(in srgb, currentColor 18%, transparent); padding: .65rem .5rem; text-align: left; }}
    th.size, td.size {{ text-align: right; white-space: nowrap; }}
    td.modified {{ white-space: nowrap; opacity: .75; }}
    a {{ color: inherit; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .empty {{ opacity: .7; text-align: center; }}
  </style>
</head>
<body>
  <main>
    <h1>{escape(title)}</h1>
    <table>
      <thead><tr><th>Name</th><th class="size">Size</th><th>Modified</th></tr></thead>
      <tbody>
        {body_rows}
      </tbody>
    </table>
  </main>
</body>
</html>"""


def directory_row(name, href, size="", modified="", is_dir=False):
    label = f"{name}/" if is_dir else name
    icon = "[DIR] " if is_dir else ""
    return (
        "<tr>"
        f'<td><a href="{escape(href, quote=True)}">{escape(icon + label)}</a></td>'
        f'<td class="size">{escape(size)}</td>'
        f'<td class="modified">{escape(modified)}</td>'
        "</tr>"
    )


def xml_escape(value):
    return escape(str(value or ""), quote=True)


def build_prop_response(href, is_dir, size=0, modified=None, etag=None):
    display_name = "" if href == "/" else unquote(href.rstrip("/").rsplit("/", 1)[-1])
    resource_type = "<D:resourcetype><D:collection /></D:resourcetype>" if is_dir else "<D:resourcetype />"
    content_props = ""
    if is_dir:
        content_props = ""
    else:
        content_props = f"<D:getcontentlength>{int(size or 0)}</D:getcontentlength>"
        if etag:
            content_props += f"<D:getetag>{xml_escape(etag)}</D:getetag>"

    return f"""<D:response>
  <D:href>{xml_escape(href)}</D:href>
  <D:propstat>
    <D:prop>
      <D:displayname>{xml_escape(display_name)}</D:displayname>
      <D:creationdate>{xml_escape(http_date(modified))}</D:creationdate>
      <D:getlastmodified>{xml_escape(http_date(modified))}</D:getlastmodified>
      {resource_type}
      {content_props}
    </D:prop>
    <D:status>HTTP/1.1 200 OK</D:status>
  </D:propstat>
</D:response>"""


def multistatus(responses):
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        f'<D:multistatus xmlns:D="{DAV_NS}">'
        + "".join(responses)
        + "</D:multistatus>"
    )


def requested_depth(request):
    depth = request.headers.get("depth")
    return "0" if depth == "0" else "1"


def auth_required(env):
    return bool(getattr(env, "WEBDAV_USERNAME", None) or getattr(env, "WEBDAV_PASSWORD", None))


def authorized(request, env):
    if not auth_required(env):
        return True

    expected_user = getattr(env, "WEBDAV_USERNAME", "")
    expected_password = getattr(env, "WEBDAV_PASSWORD", "")
    value = request.headers.get("authorization") or ""
    if not value.lower().startswith("basic "):
        return False

    try:
        decoded = b64decode(value.split(" ", 1)[1]).decode("utf-8")
    except Exception:
        return False

    username, separator, password = decoded.partition(":")
    return bool(separator) and username == expected_user and password == expected_password


def unauthorized():
    return text_response(
        "Authentication required",
        status=401,
        extra_headers={"www-authenticate": 'Basic realm="Cloudflare R2 WebDAV"'},
    )


def destination_path(request):
    destination = request.headers.get("destination")
    if not destination:
        return None
    return normalize_path(urlsplit(destination).path)


async def object_exists(bucket, path):
    key = object_key(path)
    if not key:
        return True
    if await bucket.head(key):
        return True
    if await bucket.head(dir_marker_key(path)):
        return True
    listing = await bucket.list(prefix=key.rstrip("/") + "/", limit=1)
    return bool(getattr(listing, "objects", []))


async def is_collection(bucket, path):
    if normalize_path(path) == "/":
        return True
    return bool(await bucket.head(dir_marker_key(path)))


async def collection_exists(bucket, path):
    if await is_collection(bucket, path):
        return True
    key = object_key(path)
    if not key:
        return True
    listing = await bucket.list(prefix=key.rstrip("/") + "/", limit=1)
    return bool(getattr(listing, "objects", []))


async def delete_prefix(bucket, prefix):
    cursor = None
    while True:
        options = {"prefix": prefix, "limit": 1000}
        if cursor:
            options["cursor"] = cursor
        listing = await bucket.list(**options)
        keys = [item.key for item in getattr(listing, "objects", [])]
        if keys:
            await bucket.delete(keys)
        cursor = getattr(listing, "cursor", None)
        if not getattr(listing, "truncated", False):
            break


async def copy_prefix(bucket, source_prefix, destination_prefix):
    cursor = None
    while True:
        options = {"prefix": source_prefix, "limit": 1000}
        if cursor:
            options["cursor"] = cursor
        listing = await bucket.list(**options)
        for item in getattr(listing, "objects", []):
            source_key = item.key
            target_key = destination_prefix + source_key[len(source_prefix) :]
            obj = await bucket.get(source_key)
            if obj:
                await bucket.put(target_key, obj.body)
        cursor = getattr(listing, "cursor", None)
        if not getattr(listing, "truncated", False):
            break


async def list_children(bucket, prefix):
    directories = {}
    files = []
    cursor = None

    while True:
        options = {"prefix": prefix, "limit": 1000}
        if cursor:
            options["cursor"] = cursor
        listing = await bucket.list(**options)

        for item in getattr(listing, "objects", []):
            if is_hidden_marker(item.key):
                continue
            name = item.key[len(prefix) :]
            if not name:
                continue
            first, separator, _rest = name.partition("/")
            if separator:
                directories.setdefault(first, prefix + first + "/")
            else:
                files.append(item)

        cursor = getattr(listing, "cursor", None)
        if not getattr(listing, "truncated", False):
            break

    return sorted(directories.items()), sorted(files, key=lambda item: item.key)


class Default(WorkerEntrypoint):
    async def fetch(self, request):
        try:
            return await self.handle(request)
        except Exception:
            if getattr(self.env, "DEBUG_ERRORS", "") == "1":
                return text_response(format_exc(), status=500)
            return text_response("Internal server error", status=500)

    async def handle(self, request):
        bucket = self.env.WEBDAV_BUCKET
        method = request.method.upper()
        path = normalize_path(urlsplit(request.url).path)

        if method == "OPTIONS":
            return self.options()

        if not authorized(request, self.env):
            return unauthorized()
        if method == "PROPFIND":
            return await self.propfind(bucket, request, path)
        if method in ("GET", "HEAD"):
            return await self.get(bucket, path, head_only=method == "HEAD")
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
        if method in ("LOCK", "UNLOCK"):
            return response("", status=200)

        return text_response("Method not allowed", status=405)

    def options(self):
        return response(
            "",
            status=204,
            headers={
                "allow": "OPTIONS, PROPFIND, GET, HEAD, PUT, DELETE, MKCOL, MOVE, COPY, LOCK, UNLOCK",
                "dav": "1, 2",
                "ms-author-via": "DAV",
            },
        )

    async def propfind(self, bucket, request, path):
        depth = requested_depth(request)
        key = object_key(path)
        obj = await bucket.head(key) if key else None
        collection = await is_collection(bucket, path)

        if not key:
            collection = True
        elif not obj and not collection:
            listing = await bucket.list(prefix=key.rstrip("/") + "/", limit=1)
            collection = bool(getattr(listing, "objects", []))

        if not obj and not collection:
            return text_response("Not found", status=404)

        responses = [
            build_prop_response(
                href_for(path + ("/" if collection and not path.endswith("/") else "")),
                collection,
                size=getattr(obj, "size", 0) if obj else 0,
                modified=getattr(obj, "uploaded", None) if obj else None,
                etag=etag_from_object(obj) if obj else None,
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

    async def get(self, bucket, path, head_only=False):
        if await collection_exists(bucket, path):
            if head_only:
                return html_response("", extra_headers={"content-length": "0"})
            return await self.directory_listing(bucket, path)

        obj = await bucket.get(object_key(path))
        if not obj:
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
                    modified=http_date(getattr(item, "uploaded", None)),
                )
            )

        title = f"Index of {path if path.endswith('/') else path + '/'}"
        return html_response(html_page(title, rows))

    async def put(self, bucket, request, path):
        if path == "/" or path.endswith("/"):
            return text_response("Use MKCOL to create collections", status=409)

        parent = parent_path(path)
        if parent != "/" and not await is_collection(bucket, parent):
            return text_response("Parent collection does not exist", status=409)

        existed = bool(await bucket.head(object_key(path)))
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

        if not await bucket.head(key):
            return text_response("Not found", status=404)
        await bucket.delete(key)
        return response("", status=204)

    async def mkcol(self, bucket, path):
        if path == "/":
            return text_response("Root collection already exists", status=405)
        if await object_exists(bucket, path):
            return text_response("Already exists", status=405)
        parent = parent_path(path)
        if parent != "/" and not await is_collection(bucket, parent):
            return text_response("Parent collection does not exist", status=409)
        await bucket.put(dir_marker_key(path), b"")
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
            await bucket.put(dir_marker_key(destination), b"")
            await copy_prefix(bucket, source_prefix, destination_prefix)
            if move:
                await delete_prefix(bucket, source_prefix)
        else:
            obj = await bucket.get(source_key)
            if not obj:
                return text_response("Not found", status=404)
            await bucket.put(destination_key, obj.body)
            if move:
                await bucket.delete(source_key)

        return response("", status=201)
