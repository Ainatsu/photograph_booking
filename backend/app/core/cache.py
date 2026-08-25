"""
Redis 缓存模块
- 自动检测 Redis 是否可用，不可用时降级为 fakeredis（内存缓存）
- 提供缓存装饰器和手动清除函数
"""
import json
import functools
import uuid
from contextlib import contextmanager
from typing import Optional, Callable
import redis
from redis.backoff import NoBackoff
from redis.retry import Retry
from fakeredis import FakeRedis

from backend.app.core.config import settings


# ---- Redis 连接 ----
_redis_client: Optional[redis.Redis] = None
REDIS_TIMEOUT_SECONDS = 0.2


def get_redis() -> redis.Redis:
    """获取 Redis 客户端（真 Redis > fakeredis 降级）"""
    global _redis_client
    if _redis_client is not None:
        return _redis_client

    # 先尝试连接真实 Redis
    try:
        client = redis.Redis.from_url(
            settings.REDIS_URL,
            socket_connect_timeout=REDIS_TIMEOUT_SECONDS,
            socket_timeout=REDIS_TIMEOUT_SECONDS,
            retry=Retry(NoBackoff(), 0),
            decode_responses=True,
        )
        client.ping()
        _redis_client = client
        print("[Cache] 使用真实 Redis")
        return _redis_client
    except Exception:
        pass

    # 降级：使用 fakeredis（内存缓存，进程重启即失）
    _redis_client = FakeRedis(decode_responses=True)
    print("[Cache] Redis 不可用，降级为 fakeredis（内存缓存）")
    return _redis_client


# ---- 核心缓存函数 ----


def cache_get(key: str) -> Optional[dict | list]:
    """从缓存读取，返回 Python 对象或 None"""
    try:
        r = get_redis()
        data = r.get(key)
        if data:
            return json.loads(data)
    except Exception:
        pass
    return None


def cache_set(key: str, value: dict | list, ttl: int = 300):
    """写入缓存，ttl 秒后过期（默认 5 分钟）"""
    try:
        r = get_redis()
        r.set(key, json.dumps(value, default=str), ex=ttl)
    except Exception:
        pass


def cache_delete(*keys: str):
    """删除缓存"""
    try:
        r = get_redis()
        r.delete(*keys)
    except Exception:
        pass


def cache_delete_pattern(pattern: str):
    """按模式删除（如 cache_delete_pattern('photographer:*')）"""
    try:
        r = get_redis()
        keys = r.keys(pattern)
        if keys:
            r.delete(*keys)
    except Exception:
        pass


@contextmanager
def distributed_lock(key: str, ttl_seconds: int = 15):
    """Small Redis-backed critical section; yields False when already locked."""
    token = uuid.uuid4().hex
    acquired = False
    try:
        client = get_redis()
        acquired = bool(client.set(f"lock:{key}", token, nx=True, ex=max(1, ttl_seconds)))
        yield acquired
    finally:
        if acquired:
            try:
                lock_key = f"lock:{key}"
                client = get_redis()
                if client.get(lock_key) == token:
                    client.delete(lock_key)
            except Exception:
                pass


# ---- 原子操作：用于点赞等高并发计数场景 ----


def redis_sadd(key: str, *members: str) -> int:
    """向集合添加成员，返回新增数量"""
    try:
        return get_redis().sadd(key, *members)
    except Exception:
        return 0


def redis_srem(key: str, *members: str) -> int:
    """从集合删除成员，返回删除数量"""
    try:
        return get_redis().srem(key, *members)
    except Exception:
        return 0


def redis_sismember(key: str, member: str) -> bool:
    """检查成员是否在集合中"""
    try:
        return bool(get_redis().sismember(key, member))
    except Exception:
        return False


def redis_scard(key: str) -> int:
    """返回集合成员数量"""
    try:
        return int(get_redis().scard(key))
    except Exception:
        return 0


def redis_smembers(key: str) -> set:
    """返回集合所有成员"""
    try:
        return get_redis().smembers(key)
    except Exception:
        return set()


def redis_incr(key: str, amount: int = 1) -> int:
    """原子递增，返回新值"""
    try:
        return int(get_redis().incrby(key, amount))
    except Exception:
        return 0


def redis_decr(key: str, amount: int = 1) -> int:
    """原子递减，返回新值"""
    try:
        return int(get_redis().decrby(key, amount))
    except Exception:
        return 0


def redis_exists(*keys: str) -> bool:
    """检查所有 key 是否都存在"""
    try:
        return bool(get_redis().exists(*keys))
    except Exception:
        return False


def redis_delete(*keys: str):
    """删除 key"""
    try:
        get_redis().delete(*keys)
    except Exception:
        pass


# ---- 装饰器：自动缓存 API 结果 ----


def cached(ttl: int = 300, key_prefix: str = ""):
    """
    装饰器：自动缓存函数返回值
    用法：
        @cached(ttl=600, key_prefix="photos")
        def get_photos():
            return [...]
    """

    def decorator(func: Callable):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            return await _cached_async(func, ttl, key_prefix, *args, **kwargs)

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            return _cached_sync(func, ttl, key_prefix, *args, **kwargs)

        if functools.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def _build_key(prefix: str, *args, **kwargs) -> str:
    """根据前缀与参数构建缓存键"""
    parts = [prefix] if prefix else ["cache"]
    # 关键参数加入 key
    for a in args:
        parts.append(str(a))
    for k in sorted(kwargs.keys()):
        parts.append(f"{k}={kwargs[k]}")
    return ":".join(parts)


def _cached_sync(func, ttl, prefix, *args, **kwargs):
    """同步函数的缓存包装：命中缓存则直接返回，否则执行并写入缓存"""
    key = _build_key(prefix or func.__name__, *args, **kwargs)
    cached_data = cache_get(key)
    if cached_data is not None:
        return cached_data
    result = func(*args, **kwargs)
    if result is not None:
        cache_set(key, result, ttl)
    return result


async def _cached_async(func, ttl, prefix, *args, **kwargs):
    """异步函数的缓存包装：命中缓存则直接返回，否则执行并写入缓存"""
    import inspect

    key = _build_key(prefix or func.__name__, *args, **kwargs)
    cached_data = cache_get(key)
    if cached_data is not None:
        return cached_data
    result = await func(*args, **kwargs)
    if result is not None:
        cache_set(key, result, ttl)
    return result
