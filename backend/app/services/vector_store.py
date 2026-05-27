import json
import math
from datetime import datetime, timezone

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


async def list_assigned_features(profile_id: str) -> list[dict]:
    assignments_url = f"{settings.supabase_url}/rest/v1/pm_feature_assignments"
    assignment_params = {
        "profile_id": f"eq.{profile_id}",
        "select": "org_id,feature_id",
    }
    async with httpx.AsyncClient(timeout=20) as client:
        assignments_response = await client.get(assignments_url, headers=_service_headers(), params=assignment_params)
    if assignments_response.status_code >= 400:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Feature assignments lookup failed: {assignments_response.text}",
        )

    assignments = assignments_response.json()
    feature_ids = [row["feature_id"] for row in assignments if row.get("feature_id")]
    if not feature_ids:
        return []

    features_url = f"{settings.supabase_url}/rest/v1/features"
    feature_params = {
        "id": "in.(" + ",".join(feature_ids) + ")",
        "select": "id,org_id,name,slug",
    }
    async with httpx.AsyncClient(timeout=20) as client:
        features_response = await client.get(features_url, headers=_service_headers(), params=feature_params)
    if features_response.status_code >= 400:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Features lookup failed: {features_response.text}")

    features_by_id = {feature["id"]: feature for feature in features_response.json()}
    result = []
    for assignment in assignments:
        feature = features_by_id.get(assignment.get("feature_id"))
        if not feature:
            continue
        result.append(
            {
                "org_id": assignment["org_id"],
                "feature_id": feature["id"],
                "name": feature.get("name") or "Untitled feature",
                "slug": feature.get("slug"),
            }
        )
    return result


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
        "select": "id,review_id,chunk_text,embedding",
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
                "chunk_id": row.get("id"),
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


async def create_conversation(payload: dict) -> dict:
    url = f"{settings.supabase_url}/rest/v1/conversations"
    headers = _service_headers()
    headers["Prefer"] = "return=representation"
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(url, headers=headers, json=[payload])
    if response.status_code >= 400:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Conversation create failed: {response.text}")
    rows = response.json()
    if not rows:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Conversation create returned no rows")
    return rows[0]


async def get_conversation(conversation_id: str, user_id: str) -> dict:
    url = f"{settings.supabase_url}/rest/v1/conversations"
    params = {
        "id": f"eq.{conversation_id}",
        "user_id": f"eq.{user_id}",
        "select": "*",
        "limit": "1",
    }
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(url, headers=_service_headers(), params=params)
    if response.status_code >= 400:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Conversation lookup failed: {response.text}")
    rows = response.json()
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return rows[0]


async def list_conversations(user_id: str) -> list[dict]:
    url = f"{settings.supabase_url}/rest/v1/conversations"
    params = {
        "user_id": f"eq.{user_id}",
        "status": "eq.active",
        "select": "id,org_id,feature_id,title,status,updated_at",
        "order": "updated_at.desc",
    }
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(url, headers=_service_headers(), params=params)
    if response.status_code >= 400:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Conversation list failed: {response.text}")
    conversations = response.json()
    feature_ids = [row["feature_id"] for row in conversations if row.get("feature_id")]
    features_by_id = {}
    if feature_ids:
        features_url = f"{settings.supabase_url}/rest/v1/features"
        feature_params = {
            "id": "in.(" + ",".join(list(dict.fromkeys(feature_ids))) + ")",
            "select": "id,name",
        }
        async with httpx.AsyncClient(timeout=20) as client:
            features_response = await client.get(features_url, headers=_service_headers(), params=feature_params)
        if features_response.status_code >= 400:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Conversation feature lookup failed: {features_response.text}")
        features_by_id = {feature["id"]: feature for feature in features_response.json()}

    for conversation in conversations:
        feature = features_by_id.get(conversation.get("feature_id"))
        conversation["feature_name"] = feature.get("name") if feature else None
    return conversations


async def insert_conversation_message(payload: dict) -> dict:
    url = f"{settings.supabase_url}/rest/v1/conversation_messages"
    headers = _service_headers()
    headers["Prefer"] = "return=representation"
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(url, headers=headers, json=[payload])
    if response.status_code >= 400:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Conversation message insert failed: {response.text}")
    rows = response.json()
    if not rows:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Conversation message insert returned no rows")
    return rows[0]


async def list_conversation_messages(conversation_id: str, limit: int | None = None, newest_first: bool = False) -> list[dict]:
    url = f"{settings.supabase_url}/rest/v1/conversation_messages"
    params = {
        "conversation_id": f"eq.{conversation_id}",
        "select": "id,role,content,created_at",
        "order": "created_at.desc" if newest_first else "created_at.asc",
    }
    if limit is not None:
        params["limit"] = str(limit)
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(url, headers=_service_headers(), params=params)
    if response.status_code >= 400:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Conversation messages lookup failed: {response.text}")
    rows = response.json()
    return list(reversed(rows)) if newest_first else rows


async def touch_conversation(conversation_id: str) -> None:
    url = f"{settings.supabase_url}/rest/v1/conversations?id=eq.{conversation_id}"
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.patch(
            url,
            headers=_service_headers(),
            json={"updated_at": datetime.now(timezone.utc).isoformat()},
        )
    if response.status_code >= 400:
        # updated_at usually has a DB trigger/default. Message persistence should not fail if this is absent.
        return
