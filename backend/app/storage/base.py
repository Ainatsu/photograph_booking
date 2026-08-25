"""存储抽象层：定义存储后端协议与存储键工具函数。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol

from fastapi import UploadFile


@dataclass(frozen=True)
class StorageResult:
    """存储结果，包含访问 URL 与存储键。"""
    url: str
    key: str
    local_path: str | None = None


class StorageBackend(Protocol):
    """存储后端协议，定义统一的文件保存接口。"""

    async def save_upload(self, upload_file: UploadFile, folder: str, filename: str) -> StorageResult:
        """保存上传文件到存储后端。"""
        ...

    async def save_local_file(
        self,
        source_path: str,
        folder: str,
        filename: str | None = None,
        content_type: str | None = None,
    ) -> StorageResult:
        """保存本地文件到存储后端。"""
        ...


def normalize_folder(folder: str) -> str:
    """规范化存储文件夹路径并校验合法性。"""
    normalized = (folder or "").replace("\\", "/").strip("/")
    parts = [part for part in normalized.split("/") if part]
    if not parts or any(part in {".", ".."} for part in parts):
        raise ValueError("Invalid storage folder")
    return "/".join(parts)


def build_storage_key(folder: str, filename: str) -> str:
    """根据文件夹与文件名生成存储键。"""
    safe_folder = normalize_folder(folder)
    safe_filename = os.path.basename(filename)
    if not safe_filename:
        raise ValueError("Invalid storage filename")
    return f"{safe_folder}/{safe_filename}"
