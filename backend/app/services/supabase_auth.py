import httpx
from fastapi import HTTPException, status

from ..core.config import settings
from ..schemas.auth import AuthResponse


def _map_auth_response(payload: dict) -> AuthResponse:
    user = payload.get("user") or {}
    return AuthResponse(
        access_token=payload.get("access_token", ""),
        refresh_token=payload.get("refresh_token"),
        user_id=user.get("id"),
        email=user.get("email"),
    )


async def _upsert_profile(user_id: str, email: str, display_name: str) -> None:
    if not settings.supabase_service_role_key:
        return

    url = f"{settings.supabase_url}/rest/v1/profiles"
    headers = {
        "apikey": settings.supabase_service_role_key,
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=minimal",
    }
    payload = [{"id": user_id, "email": email, "display_name": display_name}]

    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(url, headers=headers, json=payload)

    if response.status_code >= 400:
        detail = response.json().get("message", response.text)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Profile upsert failed: {detail}")


async def sign_up(display_name: str, email: str, password: str) -> AuthResponse:
    url = f"{settings.supabase_url}/auth/v1/signup"
    headers = {
        "apikey": settings.supabase_anon_key,
        "Content-Type": "application/json",
    }
    body = {
        "email": email,
        "password": password,
        "data": {"display_name": display_name},
    }

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

    auth_response = _map_auth_response(data)
    if auth_response.user_id:
        await _upsert_profile(auth_response.user_id, email, display_name)
    return auth_response


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


async def get_user_from_access_token(access_token: str) -> dict:
    url = f"{settings.supabase_url}/auth/v1/user"
    headers = {
        "apikey": settings.supabase_anon_key,
        "Authorization": f"Bearer {access_token}",
    }
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(url, headers=headers)
    if response.status_code >= 400:
        detail = response.json().get("msg", response.text)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid token: {detail}")
    return response.json()
