import json

import httpx
from fastapi import HTTPException, status

from ..core.config import settings


def _service_headers() -> dict[str, str]:
    if not settings.supabase_service_role_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="SUPABASE_SERVICE_ROLE_KEY is required for write operations",
        )
    return {
        "apikey": settings.supabase_service_role_key,
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "Content-Type": "application/json",
    }


def _vector_to_literal(values: list[float]) -> str:
    return "[" + ",".join(f"{v:.8f}" for v in values) + "]"


async def create_review(payload: dict) -> dict:
    url = f"{settings.supabase_url}/rest/v1/reviews"
    headers = _service_headers()
    headers["Prefer"] = "return=representation"
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(url, headers=headers, json=[payload])
    if response.status_code >= 400:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Review insert failed: {response.text}")
    rows = response.json()
    if not rows:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Review insert returned no rows")
    return rows[0]


async def get_review(review_id: str) -> dict:
    url = f"{settings.supabase_url}/rest/v1/reviews"
    params = {"id": f"eq.{review_id}", "select": "*", "limit": "1"}
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(url, headers=_service_headers(), params=params)
    if response.status_code >= 400:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Review lookup failed: {response.text}")
    rows = response.json()
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found")
    return rows[0]


async def update_review_status(review_id: str, status_value: str) -> None:
    url = f"{settings.supabase_url}/rest/v1/reviews?id=eq.{review_id}"
    payload = {"status": status_value}
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.patch(url, headers=_service_headers(), json=payload)
    if response.status_code >= 400:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Review status update failed: {response.text}")


async def delete_chunks_for_review(review_id: str) -> None:
    url = f"{settings.supabase_url}/rest/v1/review_chunks?review_id=eq.{review_id}"
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.delete(url, headers=_service_headers())
    if response.status_code >= 400:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Chunk delete failed: {response.text}")


async def insert_chunks(chunks: list[dict]) -> None:
    if not chunks:
        return
    url = f"{settings.supabase_url}/rest/v1/review_chunks"
    headers = _service_headers()
    headers["Prefer"] = "return=minimal"
    payload = []
    for chunk in chunks:
        row = dict(chunk)
        row["embedding"] = _vector_to_literal(chunk["embedding"])
        payload.append(row)
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(url, headers=headers, content=json.dumps(payload))
    if response.status_code >= 400:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Chunk insert failed: {response.text}")


async def get_or_create_feature(org_id: str) -> dict:
    url = f"{settings.supabase_url}/rest/v1/features"
    params = {"org_id": f"eq.{org_id}", "slug": f"eq.{settings.demo_feature_slug}", "select": "*", "limit": "1"}
    async with httpx.AsyncClient(timeout=20) as client:
        lookup = await client.get(url, headers=_service_headers(), params=params)
    if lookup.status_code >= 400:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Feature lookup failed: {lookup.text}")
    rows = lookup.json()
    if rows:
        return rows[0]

    headers = _service_headers()
    headers["Prefer"] = "return=representation"
    payload = {"org_id": org_id, "slug": settings.demo_feature_slug, "name": settings.demo_feature_name}
    async with httpx.AsyncClient(timeout=20) as client:
        create = await client.post(url, headers=headers, json=[payload])
    if create.status_code >= 400:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Feature create failed: {create.text}")
    return create.json()[0]


async def find_demo_review(org_id: str, feature_id: str) -> dict | None:
    url = f"{settings.supabase_url}/rest/v1/reviews"
    params = {
        "org_id": f"eq.{org_id}",
        "feature_id": f"eq.{feature_id}",
        "title": f"eq.{settings.demo_review_title}",
        "select": "*",
        "limit": "1",
    }
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(url, headers=_service_headers(), params=params)
    if response.status_code >= 400:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Demo review lookup failed: {response.text}")
    rows = response.json()
    return rows[0] if rows else None
