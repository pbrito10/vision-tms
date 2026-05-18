from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import router
from src.shared.logging_config import configure_logging


configure_logging()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Vision TMS API",
        version="1.0.0",
        description="FastAPI bridge for the industrial task recognition pipeline.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    return app


app = create_app()
