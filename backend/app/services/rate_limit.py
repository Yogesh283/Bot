from __future__ import annotations

import logging

from redis import Redis
from redis.exceptions import RedisError

logger = logging.getLogger("app.ratelimit")

_client: Redis | None = None


def get_redis() -> Redis | None:
    global _client
    if _client is None:
        from app.config import get_settings

        _client = Redis.from_url(
            get_settings().redis_url,
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
    try:
        _client.ping()
    except RedisError:
        logger.warning("Redis is not reachable. Login rate limiting is inactive.")
        return None
    return _client


def close_redis() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None


def is_rate_limited(redis: Redis | None, key: str, limit: int, window_seconds: int) -> bool:
    if redis is None:
        return False
    try:
        current = int(redis.incr(key))
        if current == 1:
            redis.expire(key, window_seconds)
        return current > limit
    except RedisError:
        logger.warning("Rate limit check failed. The attempt was allowed.")
        return False
