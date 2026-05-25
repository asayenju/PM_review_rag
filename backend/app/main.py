from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.core.config import settings
from app.core.logging import log_requests, setup_logging

setup_logging()
app = FastAPI(title="Startup Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.middleware("http")(log_requests)


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(auth_router)
