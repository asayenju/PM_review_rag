import json
import math

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


def _parse_vector(value) -> list[float]:
    if isinstance(value, list):
        return [float(item) for item in value]
    if isinstance(value, str):
        return [float(item) for item in value.strip("[]").split(",") if item]
    return []


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot_product = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if not left_norm or not right_norm:
        return 0.0
    return dot_product / (left_norm * right_norm)


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


async def has_feature_assignment(profile_id: str, org_id: str, feature_id: str) -> bool:
    url = f"{settings.supabase_url}/rest/v1/pm_feature_assignments"
    params = {
        "profile_id": f"eq.{profile_id}",
        "org_id": f"eq.{org_id}",
        "feature_id": f"eq.{feature_id}",
        "select": "id",
        "limit": "1",
    }
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(url, headers=_service_headers(), params=params)
    if response.status_code >= 400:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Feature assignment lookup failed: {response.text}",
        )
    return bool(response.json())


async def match_review_chunks(
    org_id: str,
    feature_id: str,
    query_embedding: list[float],
    match_count: int,
) -> list[dict]:
    url = f"{settings.supabase_url}/rest/v1/review_chunks"
    params = {
        "org_id": f"eq.{org_id}",
        "feature_id": f"eq.{feature_id}",
        "select": "review_id,chunk_text,embedding",
        "limit": str(settings.query_scan_limit),
    }
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(url, headers=_service_headers(), params=params)
    if response.status_code >= 400:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Review chunk lookup failed: {response.text}",
        )
    matches = []
    for row in response.json():
        similarity = _cosine_similarity(query_embedding, _parse_vector(row.get("embedding")))
        matches.append(
            {
                "review_id": row.get("review_id"),
                "chunk_text": row.get("chunk_text"),
                "similarity": similarity,
            }
        )
    matches = sorted(matches, key=lambda item: item["similarity"], reverse=True)[:match_count]
    reviews_by_id = await get_reviews_by_ids([match["review_id"] for match in matches if match.get("review_id")])
    for match in matches:
        review = reviews_by_id.get(match.get("review_id"), {})
        match["title"] = review.get("title")
        match["rating"] = review.get("rating")
        match["reviewer_name"] = review.get("reviewer_name")
        match["reviewed_at"] = review.get("reviewed_at")
    return matches


async def get_reviews_by_ids(review_ids: list[str]) -> dict[str, dict]:
    unique_ids = list(dict.fromkeys(review_id for review_id in review_ids if review_id))
    if not unique_ids:
        return {}

    url = f"{settings.supabase_url}/rest/v1/reviews"
    params = {
        "id": "in.(" + ",".join(unique_ids) + ")",
        "select": "id,title,rating,reviewer_name,reviewed_at,body",
    }
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(url, headers=_service_headers(), params=params)
    if response.status_code >= 400:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Reviews lookup failed: {response.text}")
    return {row["id"]: row for row in response.json()}


async def list_reviews_for_feature(
    org_id: str,
    feature_id: str,
    limit: int,
    rating_direction: str,
) -> list[dict]:
    direction = "asc" if rating_direction == "asc" else "desc"
    url = f"{settings.supabase_url}/rest/v1/reviews"
    params = {
        "org_id": f"eq.{org_id}",
        "feature_id": f"eq.{feature_id}",
        "select": "id,title,rating,reviewer_name,reviewed_at,body",
        "order": f"rating.{direction}.nullslast",
        "limit": str(limit),
    }
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(url, headers=_service_headers(), params=params)
    if response.status_code >= 400:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Reviews list failed: {response.text}")
    return response.json()


async def get_or_create_organization(name: str, slug: str) -> dict:
    url = f"{settings.supabase_url}/rest/v1/organizations"
    params = {"slug": f"eq.{slug}", "select": "*", "limit": "1"}
    async with httpx.AsyncClient(timeout=20) as client:
        lookup = await client.get(url, headers=_service_headers(), params=params)
    if lookup.status_code >= 400:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Organization lookup failed: {lookup.text}",
        )
    rows = lookup.json()
    if rows:
        return rows[0]

    headers = _service_headers()
    headers["Prefer"] = "return=representation"
    async with httpx.AsyncClient(timeout=20) as client:
        create = await client.post(url, headers=headers, json=[{"name": name, "slug": slug}])
    if create.status_code >= 400:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Organization create failed: {create.text}",
        )
    return create.json()[0]


async def get_or_create_feature_by_slug(org_id: str, slug: str, name: str) -> dict:
    url = f"{settings.supabase_url}/rest/v1/features"
    params = {"org_id": f"eq.{org_id}", "slug": f"eq.{slug}", "select": "*", "limit": "1"}
    async with httpx.AsyncClient(timeout=20) as client:
        lookup = await client.get(url, headers=_service_headers(), params=params)
    if lookup.status_code >= 400:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Feature lookup failed: {lookup.text}")
    rows = lookup.json()
    if rows:
        return rows[0]

    headers = _service_headers()
    headers["Prefer"] = "return=representation"
    payload = {"org_id": org_id, "slug": slug, "name": name}
    async with httpx.AsyncClient(timeout=20) as client:
        create = await client.post(url, headers=headers, json=[payload])
    if create.status_code >= 400:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Feature create failed: {create.text}")
    return create.json()[0]


async def find_review_by_title(org_id: str, feature_id: str, title: str) -> dict | None:
    url = f"{settings.supabase_url}/rest/v1/reviews"
    params = {
        "org_id": f"eq.{org_id}",
        "feature_id": f"eq.{feature_id}",
        "title": f"eq.{title}",
        "select": "*",
        "limit": "1",
    }
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(url, headers=_service_headers(), params=params)
    if response.status_code >= 400:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Review lookup failed: {response.text}")
    rows = response.json()
    return rows[0] if rows else None


async def get_or_create_feature(org_id: str) -> dict:
    return await get_or_create_feature_by_slug(
        org_id=org_id,
        slug=settings.demo_feature_slug,
        name=settings.demo_feature_name,
    )


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
