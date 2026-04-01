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

        init_database(
            settings.DATABASE_PATH,
            str((Path(__file__).resolve().parent / "database" / "schema.sql").resolve()),
        )
        logger.info("workflow database additions initialized")
    except Exception as e:
        logger.error(f"database init failed: {e}")
        sys.exit(1)
    yield


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

frontend_path = Path(__file__).resolve().parent / "frontend"
app.mount("/assets/js", StaticFiles(directory=str(frontend_path / "js")), name="js")


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "legacy_root": str(settings.LEGACY_ROOT),
        "database_path": settings.DATABASE_PATH,
    }


@app.get("/", include_in_schema=False)
@app.get("/admin", include_in_schema=False)
def admin_page():
    return FileResponse(str(frontend_path / "admin.html"))


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
