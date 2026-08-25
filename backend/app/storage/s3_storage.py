"""S3 存储后端：使用 boto3 将文件保存到 AWS S3。"""

from __future__ import annotations

import asyncio
import mimetypes
import os

from fastapi import UploadFile

from backend.app.core.config import settings
from backend.app.storage.base import StorageResult, build_storage_key


class S3StorageBackend:
    """S3 存储后端实现，负责文件上传与公开 URL 生成。"""

    def __init__(self) -> None:
        """初始化 S3 客户端并校验必要配置。"""
        try:
            import boto3
        except ImportError as exc:
            raise RuntimeError("boto3 is required when UPLOAD_STORAGE=s3") from exc

        if not settings.S3_BUCKET:
            raise RuntimeError("S3_BUCKET is required when UPLOAD_STORAGE=s3")

        self.bucket = settings.S3_BUCKET
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT_URL,
            aws_access_key_id=settings.S3_ACCESS_KEY_ID,
            aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
        )

    async def save_upload(self, upload_file: UploadFile, folder: str, filename: str) -> StorageResult:
        """保存上传文件到 S3 并返回访问结果。"""
        key = build_storage_key(folder, filename)
        content = await upload_file.read()
        content_type = upload_file.content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"

        await asyncio.to_thread(
            self.client.put_object,
            Bucket=self.bucket,
            Key=key,
            Body=content,
            ContentType=content_type,
        )
        return StorageResult(url=self._public_url(key), key=key)

    async def save_local_file(
        self,
        source_path: str,
        folder: str,
        filename: str | None = None,
        content_type: str | None = None,
    ) -> StorageResult:
        """将本地文件上传到 S3 并返回访问结果。"""
        target_filename = filename or os.path.basename(source_path)
        key = build_storage_key(folder, target_filename)
        upload_content_type = content_type or mimetypes.guess_type(target_filename)[0] or "application/octet-stream"

        with open(source_path, "rb") as f:
            content = await asyncio.to_thread(f.read)

        await asyncio.to_thread(
            self.client.put_object,
            Bucket=self.bucket,
            Key=key,
            Body=content,
            ContentType=upload_content_type,
        )
        return StorageResult(url=self._public_url(key), key=key)

    def _public_url(self, key: str) -> str:
        """根据配置生成对象的公开访问 URL。"""
        if settings.S3_PUBLIC_BASE_URL:
            return f"{settings.S3_PUBLIC_BASE_URL.rstrip('/')}/{key}"

        if settings.S3_ENDPOINT_URL:
            return f"{settings.S3_ENDPOINT_URL.rstrip('/')}/{self.bucket}/{key}"

        return f"https://{self.bucket}.s3.amazonaws.com/{key}"
