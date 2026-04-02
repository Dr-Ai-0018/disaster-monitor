from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from config.settings import settings
from utils.logger import get_logger, setup_logger

setup_logger(settings.LOG_FILE, settings.LOG_LEVEL)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        from database.init_db import init_database
        from models.models import get_session_factory
        from services.batch_job_service import reconcile_batch_jobs_on_startup
        from services.scheduler_service import start_scheduler, stop_scheduler
        from services.workflow_service import sync_workflow_projection_if_needed

        init_database(
            settings.DATABASE_PATH,
            str((Path(__file__).resolve().parent / "database" / "schema.sql").resolve()),
        )
        logger.info("workflow database additions initialized")
        reconcile_batch_jobs_on_startup()
        logger.info("workflow batch jobs reconciled on startup")
        if settings.ENABLE_SCHEDULER:
            start_scheduler()
        session = get_session_factory()()
        try:
            sync_workflow_projection_if_needed(session, force=True)
            logger.info("workflow projection warmed on startup")
        finally:
            session.close()
    except Exception as e:
        logger.error(f"database init failed: {e}")
        sys.exit(1)
    yield
    try:
        from services.scheduler_service import stop_scheduler

        stop_scheduler()
    except Exception as e:
        logger.warning(f"scheduler stop failed: {e}")


app = FastAPI(title="Workflow Server", version="2.0.0", lifespan=lifespan, docs_url="/docs")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from api.auth import router as auth_router
from api.workflow import router as workflow_router

app.include_router(auth_router)
app.include_router(workflow_router)

frontend_dist = Path(__file__).resolve().parent / "frontend" / "dist"


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "legacy_root": str(settings.LEGACY_ROOT),
        "database_path": settings.DATABASE_PATH,
    }


if frontend_dist.exists():
    app.mount("/assets", StaticFiles(directory=str(frontend_dist / "assets")), name="assets")
    
    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_spa(full_path: str):
        if full_path.startswith("api/"):
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Not found")
        
        file_path = frontend_dist / full_path
        if file_path.is_file():
            return FileResponse(str(file_path))
        
        index_path = frontend_dist / "index.html"
        if index_path.exists():
            return FileResponse(str(index_path))
        
        return {"message": "Frontend not built"}
else:
    @app.get("/", include_in_schema=False)
    def no_frontend():
        return {"message": "Frontend not built. Run: cd frontend && pnpm build"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.SERVER_HOST,
        port=settings.SERVER_PORT,
        reload=settings.DEBUG,
        workers=1 if settings.DEBUG else settings.SERVER_WORKERS,
        log_level=settings.LOG_LEVEL.lower(),
    )
