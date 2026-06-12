from base64 import b64decode
from json import dumps, loads
from time import time


AUTH_STATE_KEY = ".webdav-auth.json"
DEFAULT_AUTH_STATE = {
    "enabled": True,
    "failure_limit": 3,
    "window_seconds": 600,
    "lock_seconds": 900,
    "count": 0,
    "first_failed_at": 0,
    "blocked_until": 0,
}


def auth_required(env):
    return bool(getattr(env, "WEBDAV_USERNAME", None) or getattr(env, "WEBDAV_PASSWORD", None))


def decode_basic_auth(request):
    value = request.headers.get("authorization") or ""
    if not value.lower().startswith("basic "):
        return None, None
    try:
        decoded = b64decode(value.split(" ", 1)[1]).decode("utf-8")
    except Exception:
        return None, None
    username, separator, password = decoded.partition(":")
    if not separator:
        return None, None
    return username, password


def credentials_match(request, env):
    username, password = decode_basic_auth(request)
    return username == getattr(env, "WEBDAV_USERNAME", "") and password == getattr(env, "WEBDAV_PASSWORD", "")


def normalize_auth_state(value):
    state = dict(DEFAULT_AUTH_STATE)
    if isinstance(value, dict):
        for key in DEFAULT_AUTH_STATE:
            if key in value:
                state[key] = value[key]
    try:
        state["failure_limit"] = max(1, int(state["failure_limit"]))
        state["window_seconds"] = max(1, int(state["window_seconds"]))
        state["lock_seconds"] = max(1, int(state["lock_seconds"]))
        state["count"] = max(0, int(state["count"]))
        state["first_failed_at"] = max(0, int(state["first_failed_at"]))
        state["blocked_until"] = max(0, int(state["blocked_until"]))
    except Exception:
        state = dict(DEFAULT_AUTH_STATE)
    state["enabled"] = bool(state.get("enabled", True))
    return state


async def read_auth_state(bucket):
    try:
        obj = await bucket.get(AUTH_STATE_KEY)
        if obj is None or getattr(obj, "key", None) is None:
            return dict(DEFAULT_AUTH_STATE)
        if hasattr(obj, "text"):
            text = await obj.text()
        else:
            data = await obj.arrayBuffer()
            text = data.decode("utf-8", errors="replace") if isinstance(data, bytes) else str(data)
        return normalize_auth_state(loads(text))
    except Exception:
        return dict(DEFAULT_AUTH_STATE)


async def write_auth_state(bucket, state):
    try:
        await bucket.put(
            AUTH_STATE_KEY,
            dumps(normalize_auth_state(state), ensure_ascii=False, indent=2),
            httpMetadata={"contentType": "application/json"},
        )
    except Exception:
        return False
    return True


def is_locked(state, now):
    return bool(state.get("enabled", True)) and int(state.get("blocked_until", 0)) > now


async def record_auth_failure(bucket, now=None):
    now = int(time() if now is None else now)
    state = await read_auth_state(bucket)
    if not state.get("enabled", True):
        return state

    first_failed_at = int(state.get("first_failed_at", 0))
    if not first_failed_at or now - first_failed_at > int(state["window_seconds"]):
        state["count"] = 1
        state["first_failed_at"] = now
        state["blocked_until"] = 0
    else:
        state["count"] = int(state.get("count", 0)) + 1

    if int(state["count"]) >= int(state["failure_limit"]):
        state["blocked_until"] = now + int(state["lock_seconds"])

    await write_auth_state(bucket, state)
    return state


async def clear_auth_failures(bucket):
    state = await read_auth_state(bucket)
    if int(state.get("count", 0)) or int(state.get("first_failed_at", 0)) or int(state.get("blocked_until", 0)):
        state["count"] = 0
        state["first_failed_at"] = 0
        state["blocked_until"] = 0
        await write_auth_state(bucket, state)
    return state
