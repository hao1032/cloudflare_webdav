from base64 import b64decode
from email.utils import formatdate
from urllib.parse import quote, unquote, urlsplit
from xml.etree import ElementTree

from workers import Response, WorkerEntrypoint


DAV_NS = "DAV:"
ElementTree.register_namespace("D", DAV_NS)


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


def build_prop_response(href, is_dir, size=0, modified=None, etag=None):
    response_el = ElementTree.Element(f"{{{DAV_NS}}}response")
    ElementTree.SubElement(response_el, f"{{{DAV_NS}}}href").text = href

    propstat = ElementTree.SubElement(response_el, f"{{{DAV_NS}}}propstat")
    prop = ElementTree.SubElement(propstat, f"{{{DAV_NS}}}prop")
    ElementTree.SubElement(prop, f"{{{DAV_NS}}}displayname").text = (
        "" if href == "/" else unquote(href.rstrip("/").rsplit("/", 1)[-1])
    )
    ElementTree.SubElement(prop, f"{{{DAV_NS}}}creationdate").text = http_date(modified)
    ElementTree.SubElement(prop, f"{{{DAV_NS}}}getlastmodified").text = http_date(modified)

    resource_type = ElementTree.SubElement(prop, f"{{{DAV_NS}}}resourcetype")
    if is_dir:
        ElementTree.SubElement(resource_type, f"{{{DAV_NS}}}collection")
    else:
        ElementTree.SubElement(prop, f"{{{DAV_NS}}}getcontentlength").text = str(size)
        if etag:
            ElementTree.SubElement(prop, f"{{{DAV_NS}}}getetag").text = etag

    ElementTree.SubElement(propstat, f"{{{DAV_NS}}}status").text = "HTTP/1.1 200 OK"
    return response_el


def multistatus(responses):
    root = ElementTree.Element(f"{{{DAV_NS}}}multistatus")
    for item in responses:
        root.append(item)
    return ElementTree.tostring(root, encoding="utf-8", xml_declaration=True).decode()


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


class Default(WorkerEntrypoint):
    async def fetch(self, request):
        if not authorized(request, self.env):
            return unauthorized()

        bucket = self.env.WEBDAV_BUCKET
        method = request.method.upper()
        path = normalize_path(urlsplit(request.url).path)

        if method == "OPTIONS":
            return self.options()
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
            listing = await bucket.list(prefix=prefix, delimiter="/")

            for common_prefix in getattr(listing, "delimitedPrefixes", []):
                child_path = "/" + common_prefix.rstrip("/")
                responses.append(build_prop_response(href_for(child_path + "/"), True))

            for item in getattr(listing, "objects", []):
                if is_hidden_marker(item.key):
                    continue
                name = item.key[len(prefix) :]
                if not name or "/" in name:
                    continue
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
        if await is_collection(bucket, path):
            return text_response("Cannot GET a collection", status=409)

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
