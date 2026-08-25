"""本地存储后端：将文件保存到服务器本地目录。"""

from __future__ import annotations

import os
import shutil

import aiofiles
from fastapi import UploadFile

from backend.app.core.config import settings
from backend.app.storage.base import StorageResult, build_storage_key, normalize_folder


class LocalStorageBackend:
    """本地存储后端实现，文件保存至 UPLOAD_DIR 目录。"""

    async def save_upload(self, upload_file: UploadFile, folder: str, filename: str) -> StorageResult:
        """保存上传文件到本地目录并返回访问结果。"""
        key = build_storage_key(folder, filename)
        target_path = os.path.join(settings.UPLOAD_DIR, *key.split("/"))
        os.makedirs(os.path.dirname(target_path), exist_ok=True)

        async with aiofiles.open(target_path, "wb") as f:
            content = await upload_file.read()
            await f.write(content)

        return StorageResult(url=f"/static/{key}", key=key, local_path=target_path)

    async def save_local_file(
        self,
        source_path: str,
        folder: str,
        filename: str | None = None,
        content_type: str | None = None,
    ) -> StorageResult:
        """将本地文件复制到存储目录并返回访问结果。"""
        safe_folder = normalize_folder(folder)
        target_filename = filename or os.path.basename(source_path)
        key = build_storage_key(safe_folder, target_filename)
        target_path = os.path.join(settings.UPLOAD_DIR, *key.split("/"))
        os.makedirs(os.path.dirname(target_path), exist_ok=True)

        if os.path.abspath(source_path) != os.path.abspath(target_path):
            shutil.copyfile(source_path, target_path)

        return StorageResult(url=f"/static/{key}", key=key, local_path=target_path)
