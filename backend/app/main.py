from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.auth import router as auth_router
from .api.conversations import router as conversations_router
from .api.public import router as public_router
from .api.query import router as query_router
from .api.reviews import router as reviews_router
from .core.config import settings
from .core.logging import log_requests, setup_logging

setup_logging()
app = FastAPI(title="Startup Backend")

allowed_origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
dev_origin_regex = r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$" if settings.app_env == "development" else None

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=dev_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.middleware("http")(log_requests)


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(auth_router)
app.include_router(conversations_router)
app.include_router(reviews_router)
app.include_router(query_router)
app.include_router(public_router)
