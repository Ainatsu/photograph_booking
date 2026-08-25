"""
test_file_upload.py — 文件上传工具单元测试
测试：文件类型校验、扩展名校验、文件保存
"""
import pytest
import os
import tempfile
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi import HTTPException, UploadFile

from backend.app.storage.base import StorageResult
from backend.app.utils.file_upload import save_local_file_to_storage, save_upload_file
from backend.app.core.config import settings


class TestSaveUploadFile:
    """文件上传测试"""

    @pytest.fixture
    def mock_jpg_file(self):
        """模拟 JPG 上传文件"""
        mock = AsyncMock(spec=UploadFile)
        mock.filename = "test_photo.jpg"
        mock.read.return_value = b"fake_image_data"
        return mock

    @pytest.fixture
    def mock_png_file(self):
        """模拟 PNG 上传文件"""
        mock = AsyncMock(spec=UploadFile)
        mock.filename = "test_photo.png"
        mock.read.return_value = b"fake_png_data"
        return mock

    @pytest.fixture
    def mock_webp_file(self):
        """模拟 WebP 上传文件"""
        mock = AsyncMock(spec=UploadFile)
        mock.filename = "test_photo.webp"
        mock.read.return_value = b"fake_webp_data"
        return mock

    @pytest.fixture
    def mock_invalid_file(self):
        """模拟不支持的文件类型"""
        mock = AsyncMock(spec=UploadFile)
        mock.filename = "test_document.pdf"
        return mock

    @pytest.fixture
    def mock_no_extension_file(self):
        """模拟无扩展名文件"""
        mock = AsyncMock(spec=UploadFile)
        mock.filename = "testfile"
        return mock

    @pytest.fixture
    def temp_upload_dir(self, monkeypatch):
        """临时上传目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            monkeypatch.setattr(settings, "UPLOAD_DIR", tmpdir)
            yield tmpdir

    @pytest.mark.asyncio
    async def test_save_jpg(self, temp_upload_dir, mock_jpg_file):
        """正常场景：保存 JPG 文件"""
        url = await save_upload_file(mock_jpg_file, "portfolios")
        assert url.startswith("/static/portfolios/")
        assert url.endswith(".jpg")

        # 验证文件存在
        file_path = os.path.join(temp_upload_dir, "portfolios", os.path.basename(url))
        assert os.path.exists(file_path)

    @pytest.mark.asyncio
    async def test_save_png(self, temp_upload_dir, mock_png_file):
        """正常场景：保存 PNG 文件"""
        url = await save_upload_file(mock_png_file, "avatars")
        assert url.startswith("/static/avatars/")
        assert url.endswith(".png")

    @pytest.mark.asyncio
    async def test_save_webp(self, temp_upload_dir, mock_webp_file):
        """正常场景：保存 WebP 文件"""
        url = await save_upload_file(mock_webp_file, "deliveries")
        assert ".webp" in url

    @pytest.mark.asyncio
    async def test_unique_filename(self, temp_upload_dir, mock_jpg_file):
        """正常场景：生成的 UUID 文件名"""
        url = await save_upload_file(mock_jpg_file, "portfolios")
        filename = os.path.basename(url)
        # UUID + 扩展名：36 个字符的 UUID + ".jpg"
        assert len(filename) == 40  # 36 UUID + 4 extension
        assert filename.endswith(".jpg")

    @pytest.mark.asyncio
    async def test_reject_invalid_extension(self, temp_upload_dir, mock_invalid_file):
        """异常场景：拒绝 PDF 格式"""
        with pytest.raises(HTTPException) as exc:
            await save_upload_file(mock_invalid_file, "portfolios")
        assert exc.value.status_code == 400
        assert "不支持的文件格式" in exc.value.detail

    @pytest.mark.asyncio
    async def test_reject_no_extension(self, temp_upload_dir, mock_no_extension_file):
        """异常场景：拒绝无扩展名文件"""
        with pytest.raises(HTTPException) as exc:
            await save_upload_file(mock_no_extension_file, "portfolios")
        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_reject_no_filename(self, temp_upload_dir):
        """异常场景：无文件名"""
        mock = AsyncMock(spec=UploadFile)
        mock.filename = None
        with pytest.raises(HTTPException) as exc:
            await save_upload_file(mock, "portfolios")
        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_creates_subdir(self, temp_upload_dir, mock_jpg_file):
        """正常场景：自动创建子目录"""
        url = await save_upload_file(mock_jpg_file, "custom/subdir")
        dir_path = os.path.join(temp_upload_dir, "custom", "subdir")
        assert os.path.isdir(dir_path)
        assert os.path.exists(os.path.join(dir_path, os.path.basename(url)))

    @pytest.mark.asyncio
    async def test_uppercase_extension(self, temp_upload_dir):
        """边界条件：大写扩展名"""
        mock = AsyncMock(spec=UploadFile)
        mock.filename = "PHOTO.JPG"
        mock.read.return_value = b"data"
        url = await save_upload_file(mock, "portfolios")
        assert url.endswith(".jpg")

    @pytest.mark.asyncio
    async def test_save_uses_configured_storage_backend(self, monkeypatch, mock_jpg_file):
        """正常场景：S3 等远端存储由 storage backend 负责保存"""
        backend = MagicMock()
        backend.save_upload = AsyncMock(
            return_value=StorageResult(
                url="http://storage.test/portfolios/generated.jpg",
                key="portfolios/generated.jpg",
            )
        )

        monkeypatch.setattr(
            "backend.app.utils.file_upload.get_storage_backend",
            lambda: backend,
        )

        url = await save_upload_file(mock_jpg_file, "portfolios")

        assert url == "http://storage.test/portfolios/generated.jpg"
        backend.save_upload.assert_awaited_once()
        _, folder, filename = backend.save_upload.await_args.args
        assert folder == "portfolios"
        assert filename.endswith(".jpg")
        assert len(filename) == 40

    @pytest.mark.asyncio
    async def test_save_local_generated_file_to_storage(self, temp_upload_dir):
        """正常场景：本地生成的缩略图也可以进入当前存储后端"""
        source_path = os.path.join(temp_upload_dir, "source.jpg")
        with open(source_path, "wb") as f:
            f.write(b"thumbnail")

        url = await save_local_file_to_storage(source_path, "portfolios/thumbnails")

        assert url.startswith("/static/portfolios/thumbnails/")
        target_path = os.path.join(temp_upload_dir, "portfolios", "thumbnails", "source.jpg")
        assert os.path.exists(target_path)
