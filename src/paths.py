from urllib.parse import quote, unquote, urlsplit


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


def destination_path(request):
    destination = request.headers.get("destination")
    if not destination:
        return None
    return normalize_path(urlsplit(destination).path)
