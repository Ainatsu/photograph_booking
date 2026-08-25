"""
视频处理工具模块
提供视频格式验证、上传保存、压缩处理、流式播放功能
"""
import os
import subprocess
import uuid
from dataclasses import dataclass

import aiofiles
from fastapi import HTTPException, UploadFile, status

from backend.app.core.config import settings
from backend.app.storage import get_storage_backend

# 支持的视频格式
VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".wmv", ".webm", ".mkv", ".flv"}

# 默认压缩参数
DEFAULT_VIDEO_MAX_SIZE = 200 * 1024 * 1024  # 200MB 上传限制


@dataclass
class VideoCompressionConfig:
    """视频压缩配置"""
    max_width: int = 1280
    max_height: int = 720
    video_bitrate: str = "1000k"
    audio_bitrate: str = "128k"
    fps: int = 30
    codec: str = "libx264"
    audio_codec: str = "aac"
    crf: int = 23  # 质量因子，18-28 之间，越小质量越好


def get_default_compression_config() -> VideoCompressionConfig:
    """获取默认压缩配置，可通过环境变量覆盖"""
    return VideoCompressionConfig(
        max_width=int(os.getenv("VIDEO_MAX_WIDTH", "1280")),
        max_height=int(os.getenv("VIDEO_MAX_HEIGHT", "720")),
        video_bitrate=os.getenv("VIDEO_BITRATE", "1000k"),
        audio_bitrate=os.getenv("VIDEO_AUDIO_BITRATE", "128k"),
        fps=int(os.getenv("VIDEO_FPS", "30")),
        codec=os.getenv("VIDEO_CODEC", "libx264"),
        audio_codec=os.getenv("VIDEO_AUDIO_CODEC", "aac"),
        crf=int(os.getenv("VIDEO_CRF", "23")),
    )


def validate_video_extension(filename: str) -> str:
    """验证视频文件扩展名，返回小写扩展名"""
    ext = os.path.splitext(filename or "")[1].lower()
    if ext not in VIDEO_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的视频格式 ({ext})，仅允许: {', '.join(sorted(VIDEO_EXTENSIONS))}",
        )
    return ext


def check_ffmpeg_available() -> bool:
    """检查 FFmpeg 是否可用"""
    try:
        subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            timeout=5,
        )
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


async def save_video_file(upload_file: UploadFile, sub_dir: str = "videos") -> tuple[str, str]:
    """
    保存上传的视频文件
    返回 (相对静态URL, 完整文件路径)
    """
    ext = validate_video_extension(upload_file.filename or "video.mp4")
    filename = f"{uuid.uuid4()}{ext}"

    target_dir = os.path.join(settings.UPLOAD_DIR, sub_dir)
    os.makedirs(target_dir, exist_ok=True)

    file_path = os.path.join(target_dir, filename)

    async with aiofiles.open(file_path, "wb") as f:
        content = await upload_file.read()
        await f.write(content)

    if (settings.UPLOAD_STORAGE or "local").lower() == "local":
        url = f"/static/{sub_dir}/{filename}"
    else:
        try:
            result = await get_storage_backend().save_local_file(
                file_path,
                sub_dir,
                filename,
                upload_file.content_type,
            )
        except RuntimeError as exc:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
        url = result.url

    return url, file_path


def get_video_duration_seconds(file_path: str) -> float | None:
    """使用 ffprobe 获取视频时长（秒）"""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                file_path,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        duration_str = result.stdout.strip()
        if duration_str:
            return float(duration_str)
    except Exception:
        pass
    return None


def compress_video(
    input_path: str,
    output_dir: str,
    config: VideoCompressionConfig | None = None,
) -> str | None:
    """
    压缩视频文件
    返回压缩后文件路径，失败返回 None
    """
    if not check_ffmpeg_available():
        return None

    cfg = config or get_default_compression_config()

    stem = os.path.splitext(os.path.basename(input_path))[0]
    output_filename = f"{stem}_compressed.mp4"
    output_path = os.path.join(output_dir, output_filename)

    cmd = [
        "ffmpeg",
        "-i", input_path,
        "-vf", f"scale='min({cfg.max_width},iw)':'min({cfg.max_height},ih)':force_original_aspect_ratio=decrease",
        "-c:v", cfg.codec,
        "-b:v", cfg.video_bitrate,
        "-c:a", cfg.audio_codec,
        "-b:a", cfg.audio_bitrate,
        "-r", str(cfg.fps),
        "-crf", str(cfg.crf),
        "-preset", "medium",
        "-movflags", "+faststart",
        "-y",
        output_path,
    ]

    try:
        subprocess.run(cmd, capture_output=True, timeout=600, check=True)
        if os.path.isfile(output_path) and os.path.getsize(output_path) > 0:
            return output_path
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        pass

    return None


def generate_video_thumbnail(input_path: str, output_dir: str, frame_number: int = 30) -> str | None:
    """生成视频缩略图（默认第 30 帧）"""
    if not check_ffmpeg_available():
        return None

    os.makedirs(output_dir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(input_path))[0]
    thumb_filename = f"{stem}_thumb.jpg"
    thumb_path = os.path.join(output_dir, thumb_filename)
    frame_index = max(frame_number - 1, 0)

    cmd = [
        "ffmpeg",
        "-i", input_path,
        "-vf", f"select=eq(n\\,{frame_index})",
        "-frames:v", "1",
        "-q:v", "3",
        "-y",
        thumb_path,
    ]

    try:
        subprocess.run(cmd, capture_output=True, timeout=30, check=True)
        if os.path.isfile(thumb_path) and os.path.getsize(thumb_path) > 0:
            return thumb_path
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        pass

    return None
