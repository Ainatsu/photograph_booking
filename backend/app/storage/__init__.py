"""存储模块：提供存储后端获取与缓存管理。"""

from __future__ import annotations

from functools import lru_cache

from backend.app.core.config import settings
from backend.app.storage.base import StorageBackend, StorageResult
from backend.app.storage.local_storage import LocalStorageBackend
from backend.app.storage.s3_storage import S3StorageBackend


@lru_cache(maxsize=1)
def get_storage_backend() -> StorageBackend:
    """根据配置获取对应的存储后端单例。"""
    storage = (settings.UPLOAD_STORAGE or "local").lower()
    if storage == "local":
        return LocalStorageBackend()
    if storage == "s3":
        return S3StorageBackend()
    raise RuntimeError(f"Unsupported UPLOAD_STORAGE: {settings.UPLOAD_STORAGE}")


def reset_storage_backend_cache() -> None:
    """清空存储后端缓存。"""
    get_storage_backend.cache_clear()


__all__ = ["StorageBackend", "StorageResult", "get_storage_backend", "reset_storage_backend_cache"]
