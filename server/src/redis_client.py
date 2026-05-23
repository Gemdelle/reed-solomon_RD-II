from redis.asyncio import ConnectionPool, Redis

from config import get_settings

_pool: ConnectionPool | None = None


def _get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool.from_url(
            get_settings().REDIS_URL, decode_responses=True
        )
    return _pool


def get_redis() -> Redis:
    return Redis(connection_pool=_get_pool())
