"""FastAPI application factory."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger


@asynccontextmanager
async def _lifespan(app: FastAPI):
    logger.info("Dashboard FastAPI starting")
    yield
    logger.info("Dashboard FastAPI shutting down")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Leads Bot Dashboard API",
        version="0.1.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        lifespan=_lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        allow_credentials=True,
    )

    @app.get("/api/health")
    async def health():
        return {"status": "ok"}

    return app


app = create_app()
