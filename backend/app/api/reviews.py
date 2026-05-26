from fastapi import APIRouter, Depends

from .dependencies import require_authenticated_user
from ..schemas.reviews import (
    CreateReviewRequest,
    CreateReviewResponse,
    RechunkResponse,
    SeedDemoRequest,
    SeedDemoResponse,
)
from ..services.review_ingestion import create_review_and_process, process_review_chunks
from ..services.vector_store import find_demo_review, get_or_create_feature

router = APIRouter(prefix="/api", tags=["reviews"])


@router.post("/reviews", response_model=CreateReviewResponse)
async def create_review_endpoint(
    payload: CreateReviewRequest,
    _user: dict = Depends(require_authenticated_user),
):
    review_id, chunk_count, status = await create_review_and_process(
        org_id=payload.org_id,
        feature_id=payload.feature_id,
        title=payload.title,
        body=payload.body,
        reviewer_name=payload.reviewer_name,
        reviewer_email=payload.reviewer_email,
        rating=payload.rating,
    )
    return CreateReviewResponse(review_id=review_id, chunk_count=chunk_count, status=status)


@router.post("/reviews/{review_id}/chunk", response_model=RechunkResponse)
async def rechunk_review_endpoint(
    review_id: str,
    _user: dict = Depends(require_authenticated_user),
):
    chunk_count = await process_review_chunks(review_id)
    return RechunkResponse(review_id=review_id, chunk_count=chunk_count, status="ready")


@router.post("/demo/seed-default-review", response_model=SeedDemoResponse)
async def seed_default_demo_review(
    payload: SeedDemoRequest,
    _user: dict = Depends(require_authenticated_user),
):
    feature = await get_or_create_feature(payload.org_id)
    feature_id = payload.feature_id or feature["id"]

    existing = await find_demo_review(payload.org_id, feature_id)
    if existing:
        chunk_count = await process_review_chunks(existing["id"])
        return SeedDemoResponse(
            review_id=existing["id"],
            feature_id=feature_id,
            chunk_count=chunk_count,
            status="ready",
            created=False,
        )

    review_id, chunk_count, status = await create_review_and_process(
        org_id=payload.org_id,
        feature_id=feature_id,
        title="Default Shared Demo Review",
        body=(
            "Users consistently praise the checkout flow for being clear and fast, but they report "
            "confusion around coupon application and occasional cart resets on mobile. The most "
            "requested improvement is clearer error messaging and persistent cart state across sessions."
        ),
        reviewer_name="Demo Seed",
        reviewer_email="demo-seed@example.com",
        rating=8,
    )
    return SeedDemoResponse(
        review_id=review_id,
        feature_id=feature_id,
        chunk_count=chunk_count,
        status=status,
        created=True,
    )
