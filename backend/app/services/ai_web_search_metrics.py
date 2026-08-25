"""Low-cardinality Redis counters for web-search observability."""

from backend.app.core.cache import get_redis


def increment(name: str, amount: int = 1, ttl: int = 86400) -> None:
    try:
        client = get_redis()
        key = f"agent:metrics:web_search:{name}"
        client.incrby(key, amount)
        client.expire(key, ttl)
    except Exception:
        pass
