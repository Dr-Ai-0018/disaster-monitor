"""
灾害监测与分析系统 - 美国公网服务器主入口
"""
import asyncio
import sys
import os
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from config.settings import settings
from utils.logger import setup_logger, get_logger

# 初始化日志
setup_logger(log_file=settings.LOG_FILE, level=settings.LOG_LEVEL)
logger = get_logger(__name__)


# ── 生命周期 ──────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动 / 关闭钩子"""
    logger.info("=" * 60)
    logger.info(f"🚀 {settings.APP_NAME} 启动中...")
    logger.info(f"   环境: {settings.APP_ENV}")
    logger.info("=" * 60)

    # 1. 初始化数据库
    try:
        from database.init_db import init_database
        init_database(settings.DATABASE_PATH)
        logger.info("✅ 数据库初始化完成")
    except Exception as e:
        logger.error(f"❌ 数据库初始化失败: {e}")
        sys.exit(1)

    # 2. 确保存储目录存在
    for path_key in ["html_path", "json_path", "images_path", "reports_path"]:
        Path(settings.STORAGE_CONFIG.get(path_key, f"storage/{path_key}")).mkdir(
            parents=True, exist_ok=True
        )

    # 2.5 初始化默认管理员和 GPU Worker Token
    try:
        if settings.SEED_ADMIN_ENABLED:
            from database.create_admin import create_default_admin
            admin_result = create_default_admin()
            logger.info(f"✅ 默认管理员已就绪 ({admin_result.get('status')})")
        if settings.SEED_GPU_TOKEN_ENABLED:
            from database.create_token import create_api_token
            token_result = create_api_token()
            logger.info(f"✅ 默认 GPU API Token 已就绪 ({token_result.get('status')})")
    except Exception as e:
        logger.error(f"❌ 默认账号或 Token 初始化失败: {e}")

    # 3. 初始化 GEE（非阻塞，失败不中断启动）
    try:
        from core.gee_manager import initialize_gee
        if initialize_gee():
            logger.info("✅ Google Earth Engine 初始化完成")
        else:
            logger.warning("⚠️  GEE 初始化失败，影像下载功能不可用")
    except Exception as e:
        logger.warning(f"⚠️  GEE 初始化异常: {e}")

    # 4. 启动定时任务调度器
    try:
        from core.task_scheduler import scheduler, setup_scheduler
        setup_scheduler()
        scheduler.start()
        logger.info("✅ 定时任务调度器已启动")
    except Exception as e:
        logger.error(f"❌ 调度器启动失败: {e}")

    logger.info("✅ 系统启动完成，监听 http://{}:{}".format(settings.SERVER_HOST, settings.SERVER_PORT))

    try:
        yield
    except asyncio.CancelledError:
        logger.info("服务关闭信号已接收")
        raise
    finally:
        logger.info("正在关闭服务...")
        try:
            from core.task_scheduler import scheduler
            if scheduler.running:
                scheduler.shutdown(wait=False)
        except Exception:
            pass
        logger.info("服务已关闭")


# ── FastAPI 应用 ──────────────────────────────────────

app = FastAPI(
    title="灾害监测与分析系统 API",
    description="分布式灾害监测平台 - 美国公网服务器",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 注册 API 路由 ─────────────────────────────────────

from api.auth import router as auth_router
from api.events import router as events_router
from api.tasks import router as tasks_router
from api.products import router as products_router
from api.reports import router as reports_router
from api.admin import router as admin_router
from api.event_pool import router as event_pool_router
from api.public import router as public_router

app.include_router(auth_router)
app.include_router(events_router)
app.include_router(tasks_router)
app.include_router(products_router)
app.include_router(reports_router)
app.include_router(admin_router)
app.include_router(event_pool_router)
app.include_router(public_router)

# ── 静态文件 & 影像存储 ───────────────────────────────

images_path = Path(settings.STORAGE_CONFIG.get("images_path", "storage/images"))
images_path.mkdir(parents=True, exist_ok=True)
app.mount("/storage/images", StaticFiles(directory=str(images_path)), name="images")

# 挂载前端静态资源
frontend_path = Path("frontend")
if (frontend_path / "css").exists():
    app.mount("/assets/css", StaticFiles(directory=str(frontend_path / "css")), name="css")
if (frontend_path / "js").exists():
    app.mount("/assets/js", StaticFiles(directory=str(frontend_path / "js")), name="js")


# ── 基础端点 ──────────────────────────────────────────

@app.get("/health")
def health_check():
    return {"status": "healthy", "version": "1.0.0", "service": settings.APP_NAME}


@app.get("/", include_in_schema=False)
def serve_public_page():
    """前台公开展示页面"""
    public_page = Path("frontend/public.html")
    if public_page.exists():
        return FileResponse(str(public_page))
    return {"message": "Disaster Monitoring System API", "docs": "/docs"}


@app.get("/admin", include_in_schema=False)
def serve_admin_page():
    """管理后台页面"""
    admin_page = Path("frontend/admin.html")
    if admin_page.exists():
        return FileResponse(str(admin_page))
    return {"message": "Admin panel not found", "redirect": "/"}


@app.get("/public", include_in_schema=False)
def serve_public_page_alt():
    """前台公开展示页面（备用路由）"""
    public_page = Path("frontend/public.html")
    if public_page.exists():
        return FileResponse(str(public_page))
    return {"message": "Public page not found", "redirect": "/"}


# ── 入口 ──────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.SERVER_HOST,
        port=settings.SERVER_PORT,
        reload=settings.DEBUG,
        reload_excludes=[
            "test/*",
            "test/output/*",
            "storage/*",
        ] if settings.DEBUG else None,
        workers=1 if settings.DEBUG else settings.SERVER_WORKERS,
        log_level=settings.LOG_LEVEL.lower(),
    )
