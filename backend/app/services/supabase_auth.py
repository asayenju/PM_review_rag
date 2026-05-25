import httpx
from fastapi import HTTPException, status

from app.core.config import settings
from app.schemas.auth import AuthResponse


def _map_auth_response(payload: dict) -> AuthResponse:
    user = payload.get("user") or {}
    return AuthResponse(
        access_token=payload.get("access_token", ""),
        refresh_token=payload.get("refresh_token"),
        user_id=user.get("id"),
        email=user.get("email"),
    )


async def sign_up(email: str, password: str) -> AuthResponse:
    url = f"{settings.supabase_url}/auth/v1/signup"
    headers = {
        "apikey": settings.supabase_anon_key,
        "Content-Type": "application/json",
    }
    body = {"email": email, "password": password}

    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(url, headers=headers, json=body)

    if response.status_code >= 400:
        detail = response.json().get("msg", response.text)
        raise HTTPException(status_code=response.status_code, detail=detail)

    data = response.json()
    # When email confirmation is enabled, Supabase may not issue a session immediately.
    if not data.get("access_token"):
        raise HTTPException(
            status_code=status.HTTP_202_ACCEPTED,
            detail="Signup created. Confirm email if required in Supabase Auth settings.",
        )

    return _map_auth_response(data)


async def login(email: str, password: str) -> AuthResponse:
    # Password grant is handled by Supabase Auth; backend only proxies and normalizes response.
    url = f"{settings.supabase_url}/auth/v1/token?grant_type=password"
    headers = {
        "apikey": settings.supabase_anon_key,
        "Content-Type": "application/json",
    }
    body = {"email": email, "password": password}

    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(url, headers=headers, json=body)

    if response.status_code >= 400:
        detail = response.json().get("msg", response.text)
        raise HTTPException(status_code=response.status_code, detail=detail)

    return _map_auth_response(response.json())
