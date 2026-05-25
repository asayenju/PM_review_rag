from fastapi import APIRouter

from app.schemas.auth import AuthResponse, LoginRequest, SignUpRequest
from app.services.supabase_auth import login, sign_up

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/signup", response_model=AuthResponse)
async def signup_endpoint(payload: SignUpRequest):
    return await sign_up(payload.email, payload.password)


@router.post("/login", response_model=AuthResponse)
async def login_endpoint(payload: LoginRequest):
    return await login(payload.email, payload.password)
