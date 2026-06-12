try:
    from .paths import dir_marker_key, is_hidden_marker, object_key
except ImportError:
    from paths import dir_marker_key, is_hidden_marker, object_key


def r2_exists(obj):
    return obj is not None and getattr(obj, "key", None) is not None


async def r2_copy_payload(obj):
    data = await obj.arrayBuffer()
    try:
        from js import Uint8Array

        return Uint8Array.new(data)
    except ImportError:
        return data


def r2_http_metadata(obj):
    metadata = getattr(obj, "httpMetadata", None)
    if not metadata:
        return None
    content_type = getattr(metadata, "contentType", None)
    if not content_type:
        return None
    return {"contentType": content_type}


async def object_exists(bucket, path):
    key = object_key(path)
    if not key:
        return True
    if r2_exists(await bucket.head(key)):
        return True
    return await is_collection(bucket, path)


async def is_collection(bucket, path):
    key = object_key(path)
    if not key:
        return True
    if r2_exists(await bucket.head(dir_marker_key(path))):
        return True
    listing = await bucket.list(prefix=key.rstrip("/") + "/", limit=1)
    return bool(getattr(listing, "objects", []))


collection_exists = is_collection


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


async def copy_object(bucket, source_key, destination_key):
    obj = await bucket.get(source_key)
    if not r2_exists(obj):
        return False
    options = {}
    metadata = r2_http_metadata(obj)
    if metadata:
        options["httpMetadata"] = metadata
    await bucket.put(destination_key, await r2_copy_payload(obj), **options)
    return True


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
            await copy_object(bucket, source_key, target_key)
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
            name = item.key[len(prefix) :]
            if not name:
                continue
            if is_hidden_marker(item.key):
                marker_parent = name.rsplit("/", 1)[0]
                if marker_parent:
                    first, separator, _rest = marker_parent.partition("/")
                    directories.setdefault(first, prefix + first + "/")
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
