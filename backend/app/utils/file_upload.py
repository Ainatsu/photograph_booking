"""文件上传与缩略图处理工具"""

import os
import uuid
from fastapi import UploadFile, HTTPException, status
from backend.app.core.config import settings
from backend.app.storage import get_storage_backend

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
DELIVERY_ALLOWED_EXTENSIONS = ALLOWED_EXTENSIONS | {
    ".avif", ".heic", ".heif", ".tif", ".tiff",
    ".zip", ".rar", ".7z", ".psd",
}
THUMBNAIL_MAX_SIZE = (640, 640)
THUMBNAIL_QUALITY = 75

async def save_upload_file(
    upload_file: UploadFile,
    sub_dir: str = "portfolios",
    allowed_extensions: set[str] | None = None,
) -> str:
    """保存上传的文件，返回访问 URL"""
    
    # 检查文件扩展名
    ext = os.path.splitext(upload_file.filename or "")[1].lower()
    accepted_extensions = allowed_extensions or ALLOWED_EXTENSIONS
    if ext not in accepted_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的文件格式，仅允许: {', '.join(sorted(accepted_extensions))}"
        )
    
    filename = f"{uuid.uuid4()}{ext}"

    try:
        result = await get_storage_backend().save_upload(upload_file, sub_dir, filename)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    return result.url


async def save_local_file_to_storage(
    source_path: str,
    sub_dir: str,
    filename: str | None = None,
    content_type: str | None = None,
) -> str:
    """保存本地生成文件到当前存储后端，返回访问 URL。"""
    try:
        result = await get_storage_backend().save_local_file(source_path, sub_dir, filename, content_type)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    return result.url


def create_thumbnail_for_url(url: str, max_size: tuple[int, int] = THUMBNAIL_MAX_SIZE) -> str | None:
    """Create a small preview image for an uploaded static file."""
    if not url or not url.startswith("/static/"):
        return None

    try:
        from PIL import Image, ImageOps
    except ImportError:
        return None

    relative_path = url.removeprefix("/static/").replace("/", os.sep)
    source_path = os.path.join(settings.UPLOAD_DIR, relative_path)
    if not os.path.isfile(source_path):
        return None

    source_dir = os.path.dirname(source_path)
    thumb_dir = os.path.join(source_dir, "thumbnails")
    os.makedirs(thumb_dir, exist_ok=True)

    stem = os.path.splitext(os.path.basename(source_path))[0]
    thumb_filename = f"{stem}_thumb.jpg"
    thumb_path = os.path.join(thumb_dir, thumb_filename)

    try:
        with Image.open(source_path) as image:
            image = ImageOps.exif_transpose(image)
            image.thumbnail(max_size, Image.Resampling.LANCZOS)

            if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
                image = image.convert("RGBA")
                background = Image.new("RGB", image.size, (255, 255, 255))
                background.paste(image, mask=image.getchannel("A"))
                image = background
            else:
                image = image.convert("RGB")

            image.save(thumb_path, "JPEG", quality=THUMBNAIL_QUALITY, optimize=True)
    except Exception:
        return None

    thumb_relative = os.path.relpath(thumb_path, settings.UPLOAD_DIR).replace(os.sep, "/")
    return f"/static/{thumb_relative}"
