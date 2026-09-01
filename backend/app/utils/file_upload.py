"""文件上传与缩略图处理工具"""

import hashlib
import os
import uuid
from io import BytesIO

from fastapi import UploadFile, HTTPException, status
from starlette.datastructures import Headers

from backend.app.core.config import settings
from backend.app.storage import get_storage_backend

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
DELIVERY_ALLOWED_EXTENSIONS = ALLOWED_EXTENSIONS | {
    ".avif", ".heic", ".heif", ".tif", ".tiff",
    ".zip", ".rar", ".7z", ".psd",
}
THUMBNAIL_MAX_SIZE = (640, 640)
THUMBNAIL_QUALITY = 75


def _image_upload_error(code: str, message: str, **details) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_413_CONTENT_TOO_LARGE if "too_large" in code else status.HTTP_400_BAD_REQUEST,
        detail={"code": code, "message": message, **details},
    )


def _encode_ai_image(image, *, mime_type: str, quality: int) -> bytes:
    output = BytesIO()
    if mime_type == "image/webp":
        image.save(output, "WEBP", quality=quality, method=6)
    else:
        image.save(output, "JPEG", quality=quality, optimize=True, progressive=True)
    return output.getvalue()


def _normalize_ai_image(content: bytes) -> tuple[bytes, dict]:
    try:
        from PIL import Image, ImageOps, UnidentifiedImageError
    except ImportError as exc:
        raise RuntimeError("Pillow is required for AI image uploads") from exc

    try:
        with Image.open(BytesIO(content)) as source:
            original_width, original_height = source.size
            max_pixels = max(1, int(settings.IMAGE_UPLOAD_MAX_PIXELS))
            if original_width * original_height > max_pixels:
                raise _image_upload_error(
                    "reference_image_dimensions_too_large",
                    "图片像素尺寸过大，请缩小分辨率后重试",
                    max_pixels=max_pixels,
                    actual_pixels=original_width * original_height,
                )
            image = ImageOps.exif_transpose(source)
            image.load()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise _image_upload_error("invalid_reference_image", "上传文件不是有效图片") from exc

    max_dimension = max(512, int(settings.IMAGE_UPLOAD_MAX_DIMENSION))
    if max(image.size) > max_dimension:
        image.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)

    has_alpha = image.mode in {"RGBA", "LA"} or (image.mode == "P" and "transparency" in image.info)
    if has_alpha:
        image = image.convert("RGBA")
        mime_type = "image/webp"
        extension = ".webp"
    else:
        image = image.convert("RGB")
        mime_type = "image/jpeg"
        extension = ".jpg"

    hard_limit = max(1, int(settings.IMAGE_MAX_UPLOAD_BYTES))
    target_bytes = min(hard_limit, max(1, int(settings.IMAGE_UPLOAD_TARGET_BYTES)))
    quality = min(95, max(55, int(settings.IMAGE_UPLOAD_JPEG_QUALITY)))
    normalized = _encode_ai_image(image, mime_type=mime_type, quality=quality)

    while len(normalized) > target_bytes and quality > 55:
        quality = max(55, quality - 5)
        normalized = _encode_ai_image(image, mime_type=mime_type, quality=quality)

    while len(normalized) > target_bytes and max(image.size) > 512:
        scale = max(0.5, min(0.9, (target_bytes / len(normalized)) ** 0.5 * 0.95))
        next_size = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
        if next_size == image.size:
            break
        image = image.resize(next_size, Image.Resampling.LANCZOS)
        normalized = _encode_ai_image(image, mime_type=mime_type, quality=quality)

    if len(normalized) > hard_limit:
        raise _image_upload_error(
            "reference_image_too_large",
            "图片压缩后仍超过图生图限制",
            max_bytes=hard_limit,
            actual_bytes=len(normalized),
        )

    return normalized, {
        "mime_type": mime_type,
        "extension": extension,
        "width": image.width,
        "height": image.height,
        "size_bytes": len(normalized),
        "sha256": hashlib.sha256(normalized).hexdigest(),
        "original_width": original_width,
        "original_height": original_height,
        "original_size_bytes": len(content),
        "normalized": normalized != content,
    }


async def save_ai_image_upload(upload_file: UploadFile, sub_dir: str) -> dict:
    """Validate and normalize an AI reference image before it reaches the worker."""
    ext = os.path.splitext(upload_file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise _image_upload_error("invalid_reference_image_format", "仅支持 JPG、PNG 和 WebP 图片")

    source_limit = max(int(settings.IMAGE_MAX_UPLOAD_BYTES), int(settings.IMAGE_MAX_SOURCE_UPLOAD_BYTES))
    content = await upload_file.read(source_limit + 1)
    if len(content) > source_limit:
        raise _image_upload_error(
            "reference_image_source_too_large",
            "原始图片过大，请选择更小的图片",
            max_bytes=source_limit,
            actual_bytes=len(content),
        )
    if not content:
        raise _image_upload_error("invalid_reference_image", "上传图片为空")

    normalized, metadata = _normalize_ai_image(content)
    filename = f"normalized{metadata['extension']}"
    normalized_upload = UploadFile(
        file=BytesIO(normalized),
        size=len(normalized),
        filename=filename,
        headers=Headers({"content-type": metadata["mime_type"]}),
    )
    url = await save_upload_file(normalized_upload, sub_dir=sub_dir)
    return {
        "url": url,
        "thumb_url": create_thumbnail_for_url(url),
        **{key: value for key, value in metadata.items() if key != "extension"},
    }

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
