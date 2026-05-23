"""
Per-device token store backed by Redis.

Redis key layout:
  device_token:{value}            hash  → metadata for auth lookup
  device_token_rev:{org}:{id}     str   → token value (for revoke-by-id)
  device_tokens_idx:{org}         set   → all token IDs for the org (for listing)

Tokens with TTL expire automatically in Redis; listing cleans up stale index
entries on the fly.
"""
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from redis_client import get_redis

_TOKEN_PREFIX = "rd_"
_TOKEN_BYTES = 32   # → ~43-char base64url, 256 bits entropy


def _gen_token() -> str:
    return _TOKEN_PREFIX + secrets.token_urlsafe(_TOKEN_BYTES)


def _key(value: str) -> str:
    return f"device_token:{value}"


def _rev_key(org_id: str, token_id: str) -> str:
    return f"device_token_rev:{org_id}:{token_id}"


def _idx_key(org_id: str) -> str:
    return f"device_tokens_idx:{org_id}"


async def create(
    org_id: str,
    label: str,
    created_by: str,
    peer_id: str | None = None,
    ttl_seconds: int | None = None,
) -> tuple[str, dict]:
    """
    Generate a new device token.
    Returns (raw_token, metadata_dict).
    raw_token is only returned here — never stored in plaintext anywhere else.
    """
    token = _gen_token()
    token_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    expires_at = (now + timedelta(seconds=ttl_seconds)).isoformat() if ttl_seconds else ""

    meta = {
        "id": token_id,
        "org_id": org_id,
        "label": label,
        "peer_id": peer_id or "",
        "created_by": created_by,
        "created_at": now.isoformat(),
        "expires_at": expires_at,
    }

    r = get_redis()
    pipe = r.pipeline()
    pipe.hset(_key(token), mapping=meta)
    pipe.set(_rev_key(org_id, token_id), token)
    pipe.sadd(_idx_key(org_id), token_id)
    if ttl_seconds:
        pipe.expire(_key(token), ttl_seconds)
        pipe.expire(_rev_key(org_id, token_id), ttl_seconds)
    await pipe.execute()

    return token, meta


async def validate(token: str) -> dict | None:
    """
    Return metadata if the token exists and is not expired; None otherwise.
    Redis TTL handles expiry automatically.
    """
    r = get_redis()
    data = await r.hgetall(_key(token))
    return data or None


async def list_for_org(org_id: str) -> list[dict]:
    """
    List all live tokens for the org, cleaning up stale index entries as we go.
    The full token value is never returned — only token_preview.
    """
    r = get_redis()
    ids = await r.smembers(_idx_key(org_id))
    result = []
    stale: list[str] = []

    for token_id in ids:
        value = await r.get(_rev_key(org_id, token_id))
        if not value:
            stale.append(token_id)
            continue
        data = await r.hgetall(_key(value))
        if not data:
            stale.append(token_id)
            await r.delete(_rev_key(org_id, token_id))
            continue
        data["token_preview"] = value[:12] + "..."
        result.append(data)

    if stale:
        await r.srem(_idx_key(org_id), *stale)

    result.sort(key=lambda d: d.get("created_at", ""), reverse=True)
    return result


async def revoke(org_id: str, token_id: str) -> bool:
    """
    Atomically revoke a token by ID. Returns False if not found.
    """
    r = get_redis()
    value = await r.get(_rev_key(org_id, token_id))
    if not value:
        return False

    pipe = r.pipeline()
    pipe.delete(_key(value))
    pipe.delete(_rev_key(org_id, token_id))
    pipe.srem(_idx_key(org_id), token_id)
    await pipe.execute()
    return True
