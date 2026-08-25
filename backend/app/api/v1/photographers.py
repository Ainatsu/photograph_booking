"""
摄影师资料 API 路由

提供摄影师个人资料的创建/更新、查看、作品上传、方案浏览等功能。
"""

from fastapi import APIRouter, Depends, HTTPException, Request as FastAPIRequest, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from fastapi import UploadFile, File, Form
import mimetypes
import os
import re
import uuid
from datetime import date, datetime, timezone
from typing import Optional
import json
from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.api.deps import get_current_active_user
from backend.app.models.user import User
from backend.app.schemas.photographer import (
    PortfolioItemUpdate,
    PhotographerProfileCreate,
    PhotographerProfileResponse,
)
from backend.app.services.photographer_service import (
    create_or_update_profile,
    get_profile_by_user_id,
    get_all_profiles,
    get_all_works,
    get_all_packages,
    get_package_by_id,
    get_work_by_id,
)
from backend.app.services.ai_resource_index_service import refresh_ai_resource_documents_for_user
from backend.app.utils.file_upload import create_thumbnail_for_url, save_local_file_to_storage, save_upload_file
from backend.app.utils.video_utils import (
    VideoCompressionConfig,
    compress_video,
    generate_video_thumbnail,
    get_default_compression_config,
    get_video_duration_seconds,
    save_video_file,
    validate_video_extension,
)
from typing import List
from backend.app.core.cache import cache_get, cache_set, cache_delete, cache_delete_pattern

router = APIRouter(prefix="/photographers", tags=["摄影师资料"])


@router.get("/{user_id}/available-slots", summary="查询摄影师真实可预约档期")
def available_slots(
    user_id: int,
    start_date: date | None = None,
    days: int = 14,
    duration_minutes: int = 120,
    buffer_minutes: int = 30,
    db: Session = Depends(get_db),
):
    """查询摄影师真实可预约档期"""
    from backend.app.services.availability_service import list_bookable_slots, platform_today

    profile = get_profile_by_user_id(db, user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="摄影师资料不存在")
    # 服务层序列化结果不是 ORM；重新取模型以读取排期字段。
    from backend.app.models.photographer import PhotographerProfile
    profile_model = db.query(PhotographerProfile).filter(PhotographerProfile.user_id == user_id).first()
    return list_bookable_slots(
        db,
        profile_model,
        start_date or platform_today(),
        days,
        duration_minutes,
        buffer_minutes,
    )


def _split_tags(value: str) -> list[str]:
    """按常见分隔符拆分并清洗标签字符串"""
    return [
        tag.strip()
        for tag in value.replace("，", ",").replace("、", ",").replace("\n", ",").split(",")
        if tag.strip()
    ]


@router.post(
    "/profile",
    response_model=PhotographerProfileResponse,
    summary="创建/更新摄影师资料",
    description="创建或更新当前摄影师用户的个人资料，包括风格标签、套餐方案、拍摄地点等。仅摄影师角色可操作。",
    response_description="创建/更新后的摄影师资料",
)
def create_profile(
    data: PhotographerProfileCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """创建或更新当前摄影师的个人资料"""
    if current_user.role != "photographer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="仅摄影师角色可以创建资料",
        )

    profile = create_or_update_profile(db, current_user.id, data.model_dump(exclude_unset=True))
    cache_delete(f"photographer:{current_user.id}")
    cache_delete_pattern("photographer_packages*")
    cache_delete_pattern("photographer_works:*")
    cache_delete_pattern("photographer_list:*")
    return profile


@router.get(
    "/profile/{user_id}",
    response_model=PhotographerProfileResponse,
    summary="查看摄影师资料",
    description="公开查看指定摄影师的详细资料，包含套餐、作品集、可预约时间等。数据缓存 5 分钟。",
    response_description="摄影师详细资料",
)
def view_profile(user_id: int, db: Session = Depends(get_db)):
    """公开查看指定摄影师的详细资料（带缓存）"""
    cache_key = f"photographer:{user_id}"
    cached = cache_get(cache_key)
    if cached:
        return cached

    profile = get_profile_by_user_id(db, user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="摄影师资料不存在")
    cache_set(cache_key, profile, ttl=300)
    return profile


@router.get(
    "/profiles",
    response_model=list[PhotographerProfileResponse],
    summary="浏览摄影师列表",
    description="分页浏览摄影师简要资料，支持关键词、城市、风格、skip 和 limit 参数，数据缓存 3 分钟。",
    response_description="摄影师列表",
)
def list_profiles(
    query: str | None = None,
    city: str | None = None,
    style: str | None = None,
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
):
    """分页浏览摄影师简要资料列表（带缓存）"""
    cache_key = f"photographer_list:{skip}:{limit}:{query or '-'}:{city or '-'}:{style or '-'}"
    cached = cache_get(cache_key)
    if cached:
        return cached

    result = get_all_profiles(
        db,
        skip=skip,
        limit=limit,
        query_text=query,
        city=city,
        style=style,
    )
    cache_set(cache_key, result, ttl=180)
    return result


@router.get(
    "/works",
    summary="浏览全部作品",
    description="分页浏览公开作品，支持关键词、城市、风格、skip 和 limit 参数，数据缓存 5 分钟。",
    response_description="作品列表",
)
def list_works(
    query: str | None = None,
    city: str | None = None,
    style: str | None = None,
    skip: int = 0,
    limit: int = 60,
    db: Session = Depends(get_db),
):
    """分页浏览公开作品列表（带缓存）"""
    cache_key = f"photographer_works:{skip}:{limit}:{query or '-'}:{city or '-'}:{style or '-'}"
    cached = cache_get(cache_key)
    if cached:
        return cached

    result = get_all_works(
        db,
        skip=skip,
        limit=limit,
        query_text=query,
        city=city,
        style=style,
    )
    cache_set(cache_key, result, ttl=300)
    return result


@router.get(
    "/works/{work_id}",
    summary="查看作品详情",
    description="根据作品 ID 获取单个作品的详细信息，包含摄影师信息。",
    response_description="作品详细信息",
)
def view_work(work_id: str, db: Session = Depends(get_db)):
    """根据 ID 查看单个作品的详细信息"""
    work = get_work_by_id(db, work_id)
    if not work:
        raise HTTPException(status_code=404, detail="作品不存在")
    return work


@router.put(
    "/works/{work_id}",
    summary="编辑自己的作品",
    description="更新当前用户所发布作品的标题、风格标签和创作说明，媒体文件保持不变。",
    response_description="更新后的作品详情",
)
def update_work(
    work_id: str,
    data: PortfolioItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """编辑自己发布的作品信息"""
    work = get_work_by_id(db, work_id)
    if not work:
        raise HTTPException(status_code=404, detail="作品不存在")
    if int(work.get("user_id") or 0) != current_user.id:
        raise HTTPException(status_code=403, detail="只能编辑自己发布的作品")

    from backend.app.models.photographer import PhotographerProfile

    profile = db.query(PhotographerProfile).filter(
        PhotographerProfile.user_id == current_user.id
    ).first()
    if not profile:
        raise HTTPException(status_code=404, detail="摄影师资料不存在")

    normalized_tags = [tag.strip() for tag in data.tags if tag.strip()][:12]
    found = False
    next_portfolio = []
    for item in list(profile.portfolio or []):
        next_item = dict(item)
        if str(next_item.get("id") or "") == work_id:
            next_item.update({
                "title": data.title.strip(),
                "tags": normalized_tags,
                "tag": normalized_tags[0] if normalized_tags else "",
                "description": data.description.strip(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })
            found = True
        next_portfolio.append(next_item)

    if not found:
        raise HTTPException(status_code=404, detail="作品不存在")

    profile.portfolio = next_portfolio
    db.commit()
    refresh_ai_resource_documents_for_user(db, current_user.id)
    cache_delete(f"photographer:{current_user.id}")
    cache_delete_pattern("photographer_works:*")
    cache_delete_pattern("photographer_list:*")
    return {"message": "作品已更新", "work": get_work_by_id(db, work_id)}


@router.get(
    "/packages",
    summary="浏览所有套餐方案",
    description="公开浏览摄影方案，支持关键词、城市、风格、预算和分页参数，数据缓存 5 分钟。",
    response_description="套餐方案列表",
)
def list_packages(
    query: str | None = None,
    city: str | None = None,
    style: str | None = None,
    budget_min: int | None = None,
    budget_max: int | None = None,
    skip: int = 0,
    limit: int | None = None,
    db: Session = Depends(get_db),
):
    """分页浏览摄影套餐方案列表（带缓存）"""
    cache_key = (
        f"photographer_packages:{skip}:{limit or 'all'}:{query or '-'}:{city or '-'}:"
        f"{style or '-'}:{budget_min if budget_min is not None else '-'}:"
        f"{budget_max if budget_max is not None else '-'}"
    )
    cached = cache_get(cache_key)
    if cached:
        return cached

    result = get_all_packages(
        db,
        query_text=query,
        city=city,
        style=style,
        budget_min=budget_min,
        budget_max=budget_max,
        skip=skip,
        limit=limit,
    )
    cache_set(cache_key, result, ttl=300)
    return result


@router.get(
    "/packages/{package_id}",
    summary="查看方案详情",
    description="根据方案 ID 获取单个摄影方案的详细信息，包含摄影师信息。",
    response_description="方案详细信息",
)
def view_package(package_id: str, db: Session = Depends(get_db)):
    """根据 ID 查看单个摄影方案的详细信息"""
    pkg = get_package_by_id(db, package_id)
    if not pkg:
        raise HTTPException(status_code=404, detail="方案不存在")
    return pkg


@router.post(
    "/portfolio/upload",
    summary="上传作品图片",
    description="上传图片到作品集。支持同时上传作品标签、标题和描述。所有用户均可操作。",
    response_description="上传成功，返回作品信息",
)
async def upload_portfolio(
    files: Optional[List[UploadFile]] = File(None),
    file: Optional[UploadFile] = File(None),
    tag: str = Form(""),
    title: str = Form(""),
    description: str = Form(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """上传图片到作品集并生成新作品"""
    uploaded_files = list(files or [])
    if file is not None:
        uploaded_files.append(file)

    if not uploaded_files:
        raise HTTPException(status_code=400, detail="Please upload at least one image")
    if len(uploaded_files) > 18:
        raise HTTPException(status_code=400, detail="A work can include at most 18 images")

    urls = []
    thumbnail_urls = []
    for upload in uploaded_files:
        url = await save_upload_file(upload)
        urls.append(url)
        thumbnail_urls.append(create_thumbnail_for_url(url) or "")

    from backend.app.models.photographer import PhotographerProfile
    profile = db.query(PhotographerProfile).filter(
        PhotographerProfile.user_id == current_user.id
    ).first()

    if not profile:
        profile = PhotographerProfile(user_id=current_user.id)
        db.add(profile)
        db.commit()
        db.refresh(profile)

    new_work = {
        "id": uuid.uuid4().hex,
        "url": urls[0],
        "images": urls,
        "media_type": "image",
        "tag": tag,
        "tags": _split_tags(tag),
        "title": title,
        "description": description,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    if thumbnail_urls:
        new_work["thumbnail_urls"] = thumbnail_urls
        if thumbnail_urls[0]:
            new_work["thumbnail_url"] = thumbnail_urls[0]
    works = list(profile.portfolio or [])
    works.append(new_work)
    profile.portfolio = works
    db.commit()
    refresh_ai_resource_documents_for_user(db, current_user.id)

    cache_delete(f"photographer:{current_user.id}")
    cache_delete_pattern("photographer_packages*")
    cache_delete_pattern("photographer_works:*")
    cache_delete_pattern("photographer_list:*")

    return {"message": "作品上传成功", "work": new_work}


@router.post(
    "/package-samples/upload",
    summary="上传套餐样片",
    description="批量上传摄影套餐的示例图片。仅摄影师角色可操作。",
    response_description="上传结果，返回样片 URL 列表",
)
async def upload_package_samples(
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """批量上传摄影套餐的示例图片"""
    if current_user.role != "photographer":
        raise HTTPException(status_code=403, detail="仅摄影师可上传")

    urls = []
    thumbnail_urls = []
    for file in files:
        url = await save_upload_file(file, sub_dir="package_samples")
        urls.append(url)
        thumbnail_urls.append(create_thumbnail_for_url(url) or "")

    return {"urls": urls, "thumbnail_urls": thumbnail_urls}


# ---- 视频作品 ----


@router.post(
    "/video/upload",
    summary="上传视频作品",
    description="上传视频文件到作品集，支持 MP4/AVI/MOV/WMV/WEBM/MKV/FLV 格式，自动压缩处理。所有已登录用户均可操作。",
    response_description="上传成功，返回视频作品信息",
)
async def upload_video_work(
    file: UploadFile = File(...),
    cover: Optional[UploadFile] = File(None),
    tag: str = Form(""),
    title: str = Form(""),
    description: str = Form(""),
    compress: str = Form("true"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """上传视频作品，自动生成封面缩略图并按需压缩"""
    # 验证格式
    validate_video_extension(file.filename or "video.mp4")

    # 保存原视频
    url, file_path = await save_video_file(file, sub_dir="videos")

    # 获取视频时长
    cover_sub_dir = "videos/covers"
    duration = get_video_duration_seconds(file_path)

    # 生成缩略图
    thumbnail_url = None
    if cover is not None and cover.filename:
        thumbnail_url = await save_upload_file(cover, sub_dir=cover_sub_dir)
    else:
        cover_dir = os.path.join(settings.UPLOAD_DIR, cover_sub_dir)
        thumb_path = generate_video_thumbnail(file_path, cover_dir, frame_number=30)
        if thumb_path:
            thumbnail_url = await save_local_file_to_storage(
                thumb_path,
                cover_sub_dir,
                os.path.basename(thumb_path),
                "image/jpeg",
            )

    # 压缩处理
    compressed_url = None
    compressed_duration = None
    if compress.lower() != "false":
        compression_config = get_default_compression_config()
        video_dir = os.path.join(settings.UPLOAD_DIR, "videos")
        compressed_path = compress_video(file_path, video_dir, compression_config)
        if compressed_path:
            compressed_url = await save_local_file_to_storage(
                compressed_path,
                "videos",
                os.path.basename(compressed_path),
                "video/mp4",
            )
            compressed_duration = get_video_duration_seconds(compressed_path)

    # 更新用户作品集
    from backend.app.models.photographer import PhotographerProfile
    profile = db.query(PhotographerProfile).filter(
        PhotographerProfile.user_id == current_user.id
    ).first()

    if not profile:
        profile = PhotographerProfile(user_id=current_user.id)
        db.add(profile)
        db.commit()
        db.refresh(profile)

    new_work = {
        "id": uuid.uuid4().hex,
        "url": url,
        "media_type": "video",
        "tag": tag,
        "tags": _split_tags(tag),
        "title": title,
        "description": description,
        "thumbnail_url": thumbnail_url,
        "duration": duration,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    if compressed_url:
        new_work["compressed_url"] = compressed_url
        if compressed_duration:
            new_work["compressed_duration"] = compressed_duration

    works = list(profile.portfolio or [])
    works.append(new_work)
    profile.portfolio = works
    db.commit()
    refresh_ai_resource_documents_for_user(db, current_user.id)

    cache_delete(f"photographer:{current_user.id}")
    cache_delete_pattern("photographer_packages*")
    cache_delete_pattern("photographer_works:*")
    cache_delete_pattern("photographer_list:*")

    return {"message": "视频上传成功", "work": new_work}


@router.get(
    "/video/stream",
    summary="流式播放视频",
    description="提供视频文件的 HTTP Range 流式播放，支持拖动进度条时请求部分字节。",
)
def stream_video(url: str, request: FastAPIRequest):
    """视频流播放，支持 HTTP Range 请求头"""
    if not (isinstance(url, str) and url.startswith("/static/")):
        raise HTTPException(status_code=400, detail="Invalid video URL")

    relative_path = url.removeprefix("/static/").replace("/", os.sep)
    file_path = os.path.join(settings.UPLOAD_DIR, relative_path)

    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="视频文件不存在")

    file_size = os.path.getsize(file_path)
    mime_type, _ = mimetypes.guess_type(file_path)
    if not mime_type:
        mime_type = "video/mp4"

    range_header = request.headers.get("range")
    start = 0
    end = file_size - 1

    if range_header:
        match = re.match(r"bytes=(\d+)-(\d*)", range_header)
        if match:
            start = int(match.group(1))
            end_str = match.group(2)
            end = min(int(end_str) if end_str else file_size - 1, file_size - 1)

    chunk_size = min(end - start + 1, 1024 * 1024)
    content_length = end - start + 1

    def file_iterator():
        with open(file_path, "rb") as f:
            f.seek(start)
            remaining = content_length
            while remaining > 0:
                chunk = f.read(min(chunk_size, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk

    headers = {
        "Content-Type": mime_type,
        "Accept-Ranges": "bytes",
        "Cache-Control": "public, max-age=86400",
    }

    if range_header:
        headers["Content-Range"] = f"bytes {start}-{end}/{file_size}"
        headers["Content-Length"] = str(content_length)
        return StreamingResponse(
            file_iterator(),
            status_code=206,
            headers=headers,
            media_type=mime_type,
        )
    else:
        headers["Content-Length"] = str(file_size)
        return StreamingResponse(
            file_iterator(),
            status_code=200,
            headers=headers,
            media_type=mime_type,
        )
