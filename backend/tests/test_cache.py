"""
test_cache.py — 缓存模块单元测试
测试：缓存读写、删除、模式匹配删除、降级
"""
import pytest
from backend.app.core import cache as cache_module
from backend.app.core.cache import (
    get_redis,
    cache_get,
    cache_set,
    cache_delete,
    cache_delete_pattern,
)


class TestGetRedis:
    """Redis 连接获取测试"""

    def test_returns_client(self):
        """正常场景：返回缓存客户端（fakeredis 降级）"""
        client = get_redis()
        assert client is not None

    def test_client_is_singleton(self):
        """正常场景：多次调用返回同一实例"""
        c1 = get_redis()
        c2 = get_redis()
        assert c1 is c2

    def test_real_redis_probe_uses_short_timeouts(self, monkeypatch):
        """异常场景：真实 Redis 不可用时应快速降级，不阻塞首个请求"""
        captured_url = None
        captured_kwargs = {}

        class UnavailableRedis:
            def __init__(self, url, **kwargs):
                nonlocal captured_url
                captured_url = url
                captured_kwargs.update(kwargs)

            def ping(self):
                raise TimeoutError("redis unavailable")

        monkeypatch.setattr(cache_module, "_redis_client", None)
        monkeypatch.setattr(cache_module.settings, "REDIS_URL", "redis://cache.example:6380/2")
        monkeypatch.setattr(cache_module.redis.Redis, "from_url", UnavailableRedis)

        client = cache_module.get_redis()

        assert client is not None
        assert captured_url == "redis://cache.example:6380/2"
        assert captured_kwargs["socket_connect_timeout"] <= 0.2
        assert captured_kwargs["socket_timeout"] <= 0.2
        assert getattr(captured_kwargs["retry"], "_retries") == 0


class TestCacheSetGet:
    """缓存写入和读取测试"""

    def test_set_and_get_dict(self):
        """正常场景：写入/读取字典"""
        cache_set("test:dict", {"name": "张三", "age": 30})
        result = cache_get("test:dict")
        assert result == {"name": "张三", "age": 30}

    def test_set_and_get_list(self):
        """正常场景：写入/读取列表"""
        cache_set("test:list", [1, 2, 3, 4, 5])
        result = cache_get("test:list")
        assert result == [1, 2, 3, 4, 5]

    def test_get_nonexistent_key(self):
        """异常场景：读取不存在的键"""
        result = cache_get("nonexistent:key")
        assert result is None

    def test_overwrite_existing(self):
        """正常场景：覆盖已有键"""
        cache_set("test:overwrite", {"version": 1})
        cache_set("test:overwrite", {"version": 2})
        result = cache_get("test:overwrite")
        assert result == {"version": 2}

    def test_complex_nested_data(self):
        """边界条件：嵌套复杂数据"""
        data = {
            "users": [{"id": 1, "tags": ["a", "b"]}, {"id": 2, "tags": ["c"]}],
            "metadata": {"page": 1, "total": 100},
        }
        cache_set("test:complex", data)
        result = cache_get("test:complex")
        assert result == data


class TestCacheDelete:
    """缓存删除测试"""

    def test_delete_single_key(self):
        """正常场景：删除单个键"""
        cache_set("test:single", "value")
        cache_delete("test:single")
        assert cache_get("test:single") is None

    def test_delete_multiple_keys(self):
        """正常场景：批量删除键"""
        cache_set("test:a", "a")
        cache_set("test:b", "b")
        cache_set("test:c", "c")
        cache_delete("test:a", "test:b")
        assert cache_get("test:a") is None
        assert cache_get("test:b") is None
        assert cache_get("test:c") == "c"

    def test_delete_nonexistent_key(self):
        """边界条件：删除不存在的键不报错"""
        cache_delete("no:such:key")

    def test_delete_empty(self):
        """边界条件：无参数删除不报错"""
        cache_delete()


class TestCacheDeletePattern:
    """模式删除测试"""

    def test_delete_by_pattern(self):
        """正常场景：按模式匹配删除"""
        cache_set("photographer:1:data", {"id": 1})
        cache_set("photographer:2:data", {"id": 2})
        cache_set("order:1:data", {"id": 1})

        cache_delete_pattern("photographer:*")
        assert cache_get("photographer:1:data") is None
        assert cache_get("photographer:2:data") is None
        assert cache_get("order:1:data") is not None

    def test_delete_pattern_no_match(self):
        """边界条件：无匹配键不报错"""
        cache_delete_pattern("notexists:*")


class TestTTL:
    """过期时间测试（基础）"""

    def test_set_with_ttl(self):
        """正常场景：设置带 TTL 的缓存"""
        cache_set("test:ttl", {"data": "valid"}, ttl=3600)
        result = cache_get("test:ttl")
        assert result == {"data": "valid"}

    def test_set_with_zero_ttl(self):
        """边界条件：TTL 为 0"""
        cache_set("test:ttl0", {"data": "expires"}, ttl=0)
        # fakeredis 行为：TTL=0 可能被处理为删除
        result = cache_get("test:ttl0")
        # 不强制验证过期行为（依赖于具体实现）
        assert result is None or result == {"data": "expires"}
