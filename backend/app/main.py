"""
摄影师智能预约平台 - FastAPI 应用入口

整合用户系统、摄影师资料、订单系统、站内消息、实时通信和管理后台六大模块，
提供 RESTful API 和 Swagger 自动文档。
"""

from fastapi import FastAPI
from backend.app.api.v1.users import router as users_router
from backend.app.api.v1.photographers import router as photographers_router
from fastapi.staticfiles import StaticFiles
from backend.app.api.v1.orders import router as orders_router
from backend.app.api.v1.messages import router as messages_router
from backend.app.api.v1.ws import router as ws_router
from backend.app.api.v1.admin import router as admin_router
from backend.app.api.v1.likes import router as likes_router
from backend.app.api.v1.favorites import router as favorites_router
from backend.app.api.v1.comments import router as comments_router
from backend.app.api.v1.ai import router as ai_router
from backend.app.api.v1.projects import router as projects_router
from backend.app.api.v1.photographer_applications import router as photographer_applications_router
from backend.app.api.v1.follows import router as follows_router
from backend.app.api.v1.photographer_dashboard import router as photographer_dashboard_router
from backend.app.api.v1.analytics import router as analytics_router
from backend.app.api.v1.recommendations import router as recommendations_router
from backend.app.api.v1.payments import router as payments_router
from backend.app.api.v1.notifications import router as notifications_router
from backend.app.api.v1.auth import router as auth_router
from backend.app.api.v1.inspirations import router as inspirations_router
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from backend.app.core.config import settings
from backend.app.core.timezone import UTCJSONResponse
from contextlib import asynccontextmanager
import subprocess
import sys
import os
import asyncio
from contextlib import suppress

# ---- 数据库迁移（自动执行） ----
def run_migrations():
    """启动时自动执行数据库迁移，新增表/字段不会丢失数据"""
    project_root = os.path.join(os.path.dirname(__file__), "..", "..")
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=project_root,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"[Migration] 迁移失败: {result.stderr}")
        raise RuntimeError("数据库迁移失败，应用未启动")
    else:
        print("[Migration] 数据库迁移完成")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理：启动时执行数据库迁移、预热缓存并启动后台任务，关闭时取消所有任务"""
    if settings.AUTO_RUN_MIGRATIONS:
        run_migrations()
    else:
        print("[Migration] AUTO_RUN_MIGRATIONS=false，跳过启动迁移")
    # 启动点赞缓存预热：从 DB 加载全部点赞数据到 Redis
    try:
        from backend.app.core.database import SessionLocal
        from backend.app.services.like_service import warmup_like_cache
        db = SessionLocal()
        try:
            warmed = warmup_like_cache(db)
            print(f"[LikeCache] 启动预热完成，共加载 {warmed} 个 target")
        finally:
            db.close()
    except Exception as e:
        print(f"[LikeCache] 预热失败（非致命）: {e}")
    from backend.app.services.order_service import (
        run_acceptance_expiry_worker,
        run_payment_expiry_worker,
        run_reschedule_expiry_worker,
    )
    reschedule_expiry_task = asyncio.create_task(run_reschedule_expiry_worker())
    payment_expiry_task = asyncio.create_task(run_payment_expiry_worker())
    acceptance_expiry_task = asyncio.create_task(run_acceptance_expiry_worker())
    from backend.app.services.automation_service import run_order_automation_worker
    from backend.app.services.notification_service import run_outbox_worker
    automation_task = asyncio.create_task(run_order_automation_worker())
    outbox_task = asyncio.create_task(run_outbox_worker())
    ai_index_task = None
    if settings.AI_INDEX_WORKER_ENABLED:
        from backend.app.services.ai_index_job_service import run_ai_index_worker
        ai_index_task = asyncio.create_task(run_ai_index_worker())
    inspiration_generation_task = None
    if settings.INSPIRATION_GENERATION_WORKER_ENABLED:
        from backend.app.services.inspiration_generation_service import run_inspiration_generation_worker
        inspiration_generation_task = asyncio.create_task(
            run_inspiration_generation_worker(
                poll_interval_seconds=settings.INSPIRATION_GENERATION_WORKER_POLL_SECONDS,
            )
        )
    image_generation_task = None
    if settings.IMAGE_GENERATION_WORKER_ENABLED:
        from backend.app.services.image_generation_job_service import run_image_generation_worker
        image_generation_task = asyncio.create_task(
            run_image_generation_worker(poll_interval_seconds=settings.IMAGE_GENERATION_WORKER_POLL_SECONDS)
        )
    try:
        from backend.app.services.ai_embedding_service import warmup_text_embedding_provider

        text_embedding_info = warmup_text_embedding_provider()
        if text_embedding_info:
            print(f"[TextEmbedding] 文本模型预热完成: {text_embedding_info}")
    except Exception as exc:
        print(f"[TextEmbedding] 文本模型预热失败（非致命）: {exc}")
    try:
        from backend.app.services.ai_embedding_service import warmup_image_embedding_provider

        image_embedding_info = warmup_image_embedding_provider()
        if image_embedding_info:
            print(f"[ImageEmbedding] 视觉模型预热完成: {image_embedding_info}")
    except Exception as exc:
        # 模型不可用时不阻塞普通文本 API；图片检索会在 diagnostics 中报告错误。
        print(f"[ImageEmbedding] 视觉模型预热失败（非致命）: {exc}")
    try:
        yield
    finally:
        reschedule_expiry_task.cancel()
        payment_expiry_task.cancel()
        acceptance_expiry_task.cancel()
        automation_task.cancel()
        outbox_task.cancel()
        if ai_index_task:
            ai_index_task.cancel()
        if inspiration_generation_task:
            inspiration_generation_task.cancel()
        if image_generation_task:
            image_generation_task.cancel()
        with suppress(asyncio.CancelledError):
            await reschedule_expiry_task
        with suppress(asyncio.CancelledError):
            await payment_expiry_task
        with suppress(asyncio.CancelledError):
            await acceptance_expiry_task
        with suppress(asyncio.CancelledError):
            await automation_task
        with suppress(asyncio.CancelledError):
            await outbox_task
        if ai_index_task:
            with suppress(asyncio.CancelledError):
                await ai_index_task
        if inspiration_generation_task:
            with suppress(asyncio.CancelledError):
                await inspiration_generation_task
        if image_generation_task:
            with suppress(asyncio.CancelledError):
                await image_generation_task

app = FastAPI(
    title="摄影师智能预约平台",
    description="""## 一个连接客户与摄影师的智能预约平台

### 功能模块
- **用户系统** - 注册、登录、个人信息管理、头像上传
- **摄影师资料** - 个人资料管理、套餐方案、作品集展示
- **订单系统** - 下单、接单、交付、验收、评价全流程
- **站内消息** - 用户间实时沟通，支持订单关联
- **实时通信** - WebSocket 即时消息推送
- **管理后台** - 仪表盘统计、用户管理、订单管理

### 技术说明
- 所有需要认证的接口需在 Header 中携带 `Authorization: Bearer <token>`
- 登录接口使用 OAuth2 Password 流程（表单格式 `username` + `password`）
- 支持分页的接口使用 `skip`（偏移量）和 `limit`（每页数量）参数
    """,
    version="0.1.0",
    lifespan=lifespan,
    default_response_class=UTCJSONResponse,
    contact={
        "name": "Photographer Booking Team",
    },
    license_info={
        "name": "MIT",
    },
)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """请求参数验证异常处理 - 返回详细的字段校验错误"""
    try:
        body = await request.body()
        body_str = body.decode("utf-8", errors="replace")[:2000]
    except RuntimeError:
        body_str = "<stream already consumed (multipart)>"

    print("=" * 50)
    print("【422 验证错误】")
    print("请求体：", body_str)
    print("错误详情：", exc.errors())
    print("=" * 50)
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()},
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(users_router, prefix="/api/v1")
app.include_router(photographers_router, prefix="/api/v1")
app.include_router(orders_router, prefix="/api/v1")
app.include_router(messages_router, prefix="/api/v1")
app.include_router(ws_router)
app.include_router(admin_router, prefix="/api/v1")
app.include_router(likes_router, prefix="/api/v1")
app.include_router(favorites_router, prefix="/api/v1")
app.include_router(comments_router, prefix="/api/v1")
app.include_router(ai_router, prefix="/api/v1")
app.include_router(projects_router, prefix="/api/v1")
app.include_router(photographer_applications_router, prefix="/api/v1")
app.include_router(follows_router, prefix="/api/v1")
app.include_router(photographer_dashboard_router, prefix="/api/v1")
app.include_router(analytics_router, prefix="/api/v1")
app.include_router(recommendations_router, prefix="/api/v1")
app.include_router(payments_router, prefix="/api/v1")
app.include_router(notifications_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(inspirations_router, prefix="/api/v1")


@app.get(
    "/",
    summary="平台首页",
    description="返回平台欢迎信息。",
    tags=["系统信息"],
)
def root():
    """返回平台首页欢迎信息"""
    return {"message": "欢迎来到摄影师智能预约平台！"}


@app.get(
    "/health",
    summary="健康检查",
    description="用于负载均衡器 / 监控系统的存活检测。",
    tags=["系统信息"],
)
def health_check():
    """健康检查接口，返回服务存活状态"""
    return {"status": "ok"}

os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=settings.UPLOAD_DIR), name="static")
