"""
拍摄企划（项目）相关 API 路由

提供企划的浏览、发布、报名、录用摄影师等功能。
"""

from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_active_user, get_current_active_user_optional
from backend.app.core.database import get_db
from backend.app.utils.file_upload import create_thumbnail_for_url, save_upload_file
from backend.app.models.project import ProjectApplicationStatus, ProjectStatus
from backend.app.models.user import User
from backend.app.schemas.project import (
    ProjectApplicationCreate,
    ProjectApplicationResponse,
    ProjectApplicationUpdate,
    ProjectCloseRequest,
    ProjectCreate,
    ProjectDetailResponse,
    ProjectResponse,
    ProjectSelectResponse,
    ProjectUpdate,
)
from backend.app.services.order_service import get_latest_order_event, push_order_event_update
from backend.app.services.project_service import (
    apply_project,
    close_project,
    create_project,
    ensure_project_visible,
    get_application_by_id,
    get_my_application,
    get_project_by_id,
    list_my_applications,
    list_my_projects,
    list_open_projects,
    list_project_applications,
    list_project_events,
    publish_project,
    select_application,
    serialize_application,
    serialize_event,
    serialize_project,
    update_application,
    update_project,
    withdraw_application,
)

router = APIRouter(prefix="/projects", tags=["shoot projects"])


def _parse_project_status(value: str | None) -> ProjectStatus | None:
    """解析企划状态字符串为枚举，非法值返回 400"""
    if value is None:
        return None
    try:
        return ProjectStatus(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid project status") from exc


def _parse_application_status(value: str | None) -> ProjectApplicationStatus | None:
    """解析报名状态字符串为枚举，非法值返回 400"""
    if value is None:
        return None
    try:
        return ProjectApplicationStatus(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid application status") from exc


def _require_role(user: User, role: str) -> None:
    """校验当前用户角色，不符合则返回 403"""
    if user.role != role:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Only {role}s can use this endpoint")


@router.get("/", response_model=list[ProjectResponse])
def browse_projects(
    query: str | None = None,
    city: str | None = None,
    category: str | None = None,
    budget_min: int | None = None,
    budget_max: int | None = None,
    style_tags: str | None = None,
    customer_id: int | None = None,
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_active_user_optional),
):
    """浏览开放的拍摄企划列表，支持多种条件筛选"""
    projects = list_open_projects(
        db,
        city=city,
        category=category,
        budget_min=budget_min,
        budget_max=budget_max,
        style_tags=style_tags,
        customer_id=customer_id,
        skip=skip,
        limit=limit,
        query_text=query,
    )
    return [serialize_project(db, project, current_user) for project in projects]


@router.post("/", response_model=ProjectResponse, status_code=201)
def create_project_endpoint(
    data: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """创建新的拍摄企划"""
    project = create_project(db, current_user.id, data)
    return serialize_project(db, project, current_user)


@router.get("/my", response_model=list[ProjectResponse])
def my_projects(
    status: str | None = None,
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """查看当前用户发布的企划列表"""
    project_status = _parse_project_status(status)
    projects = list_my_projects(db, current_user.id, project_status, skip, limit)
    return [serialize_project(db, project, current_user) for project in projects]


@router.get("/my-applications", response_model=list[ProjectApplicationResponse])
def my_applications(
    status: str | None = None,
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """查看摄影师提交的企划报名列表"""
    _require_role(current_user, "photographer")
    application_status = _parse_application_status(status)
    applications = list_my_applications(db, current_user.id, application_status, skip, limit)
    return [serialize_application(db, application, include_project=True) for application in applications]


@router.get("/{project_id}", response_model=ProjectDetailResponse)
def project_detail(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_active_user_optional),
):
    """查看企划详情、报名列表与事件记录"""
    project = get_project_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    ensure_project_visible(project, current_user, db)

    applications = []
    events = []
    my_application = None
    if current_user and (current_user.is_admin or current_user.id == project.customer_id):
        applications = [
            serialize_application(db, application)
            for application in list_project_applications(db, project, project.customer_id)
        ]
        events = [serialize_event(event) for event in list_project_events(db, project, current_user)]
    elif current_user and current_user.role == "photographer":
        application = get_my_application(db, project.id, current_user.id)
        if application:
            my_application = serialize_application(db, application)

    return {
        "project": serialize_project(db, project, current_user),
        "applications": applications,
        "my_application": my_application,
        "events": events,
    }


@router.put("/{project_id}", response_model=ProjectResponse)
def update_project_endpoint(
    project_id: int,
    data: ProjectUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """更新企划信息"""
    project = get_project_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    project = update_project(db, project, current_user.id, data)
    return serialize_project(db, project, current_user)


@router.put("/{project_id}/publish", response_model=ProjectResponse)
def publish_project_endpoint(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """发布企划，开放摄影师报名"""
    project = get_project_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    project = publish_project(db, project, current_user.id)
    return serialize_project(db, project, current_user)


@router.put("/{project_id}/close", response_model=ProjectResponse)
def close_project_endpoint(
    project_id: int,
    data: ProjectCloseRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """关闭企划，停止招募"""
    project = get_project_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    project = close_project(db, project, current_user.id, data.reason)
    return serialize_project(db, project, current_user)


@router.get("/{project_id}/applications", response_model=list[ProjectApplicationResponse])
def project_applications(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """查看企划的报名列表"""
    project = get_project_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    applications = list_project_applications(db, project, current_user.id)
    return [serialize_application(db, application) for application in applications]


@router.post("/{project_id}/applications", response_model=ProjectApplicationResponse, status_code=201)
def apply_project_endpoint(
    project_id: int,
    data: ProjectApplicationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """摄影师报名企划"""
    _require_role(current_user, "photographer")
    project = get_project_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    application = apply_project(db, project, current_user.id, data)
    return serialize_application(db, application)


@router.put("/{project_id}/applications/me", response_model=ProjectApplicationResponse)
def update_my_application(
    project_id: int,
    data: ProjectApplicationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """更新自己提交的企划报名"""
    _require_role(current_user, "photographer")
    application = get_my_application(db, project_id, current_user.id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    application = update_application(db, application, current_user.id, data)
    return serialize_application(db, application)


@router.put("/{project_id}/applications/me/withdraw", response_model=ProjectApplicationResponse)
def withdraw_my_application(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """撤回自己提交的企划报名"""
    _require_role(current_user, "photographer")
    application = get_my_application(db, project_id, current_user.id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    application = withdraw_application(db, application, current_user.id)
    return serialize_application(db, application)


@router.post(
    "/{project_id}/applications/{application_id}/select",
    response_model=ProjectSelectResponse,
)
async def select_project_application(
    project_id: int,
    application_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """企划方录用指定摄影师报名并生成订单"""
    project = get_project_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if current_user.id != project.customer_id:
        raise HTTPException(status_code=403, detail="Only the project owner can select an application")
    application = get_application_by_id(db, application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    project, application, order = select_application(db, project, application, current_user.id)
    await push_order_event_update(get_latest_order_event(db, order.id), order)
    return {
        "project": serialize_project(db, project, current_user),
        "application": serialize_application(db, application),
        "order": order,
    }


@router.post(
    "/upload-images",
    summary="上传企划参考图",
    description="批量上传拍摄企划的参考图片。仅已登录用户可操作。",
    response_description="上传结果，返回图片 URL 列表",
)
async def upload_project_images(
    files: List[UploadFile] = File(...),
    current_user: User = Depends(get_current_active_user),
):
    """批量上传企划参考图，返回图片 URL 列表"""
    urls = []
    for file in files:
        url = await save_upload_file(file, sub_dir="project_refs")
        urls.append(url)
        create_thumbnail_for_url(url)
    return {"urls": urls}
