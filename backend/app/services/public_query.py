from .openai_answers import answer_from_review_context
from .openai_embeddings import embed_texts
from .query_guardrails import (
    OUT_OF_SCOPE,
    OUT_OF_SCOPE_ANSWER,
    REVIEW_RATING,
    classify_query,
    rating_sort_direction,
)
from .review_context import build_chunk_context, build_review_context
from .review_ingestion import create_review_and_process, process_review_chunks
from .vector_store import (
    find_review_by_title,
    get_or_create_feature_by_slug,
    get_or_create_organization,
    list_reviews_for_feature,
    match_review_chunks,
)
from ..core.config import settings

_NO_EVIDENCE_ANSWER = "I do not have enough public review evidence for that yet."

_PUBLIC_REVIEWS = [
    {
        "title": "Public Demo Review: Coupon Confusion",
        "body": (
            "The checkout flow feels quick, but applying coupons is confusing. I could not tell "
            "whether my promo code worked until the final payment step, and the error message did "
            "not explain why the code failed."
        ),
        "reviewer_name": "Public Demo Reviewer",
        "rating": 6,
    },
    {
        "title": "Public Demo Review: Mobile Cart Reset",
        "body": (
            "Shopping on mobile is smooth until the cart randomly resets after I leave the app. "
            "I want the cart to persist across sessions so I do not have to rebuild my order."
        ),
        "reviewer_name": "Mobile Customer",
        "rating": 5,
    },
    {
        "title": "Public Demo Review: Fast Checkout",
        "body": (
            "Checkout is fast and the payment form is easy to understand. The best part is that "
            "shipping choices are clear, but I still want better status updates after placing an order."
        ),
        "reviewer_name": "Repeat Buyer",
        "rating": 8,
    },
    {
        "title": "Public Demo Review: Error Messaging",
        "body": (
            "When payment fails, the product gives a generic error. Customers need clear guidance "
            "about whether the card, billing address, or network caused the failure."
        ),
        "reviewer_name": "Checkout Tester",
        "rating": 4,
    },
]


async def ensure_public_reviews() -> tuple[str, str]:
    org = await get_or_create_organization(
        name=settings.public_review_org_name,
        slug=settings.public_review_org_slug,
    )
    feature = await get_or_create_feature_by_slug(
        org_id=org["id"],
        slug=settings.public_review_feature_slug,
        name=settings.public_review_feature_name,
    )

    for review in _PUBLIC_REVIEWS:
        existing = await find_review_by_title(org["id"], feature["id"], review["title"])
        if existing:
            if existing.get("status") != "ready":
                await process_review_chunks(existing["id"])
            continue
        await create_review_and_process(
            org_id=org["id"],
            feature_id=feature["id"],
            title=review["title"],
            body=review["body"],
            reviewer_name=review["reviewer_name"],
            reviewer_email=None,
            rating=review["rating"],
        )

    return org["id"], feature["id"]


async def answer_public_review_question(question: str) -> str:
    query_intent = classify_query(question)
    if query_intent == OUT_OF_SCOPE:
        return OUT_OF_SCOPE_ANSWER

    org_id, feature_id = await ensure_public_reviews()
    if query_intent == REVIEW_RATING:
        reviews = await list_reviews_for_feature(
            org_id=org_id,
            feature_id=feature_id,
            limit=settings.query_match_count,
            rating_direction=rating_sort_direction(question),
        )
        context = build_review_context(reviews)
        if not context:
            return _NO_EVIDENCE_ANSWER
        return await answer_from_review_context(question=question, context=context)

    query_embedding = (await embed_texts([question]))[0]
    matches = await match_review_chunks(
        org_id=org_id,
        feature_id=feature_id,
        query_embedding=query_embedding,
        match_count=settings.query_match_count,
    )
    strong_matches = [
        match
        for match in matches
        if float(match.get("similarity") or 0) >= settings.query_min_similarity
    ]
    context = build_chunk_context(strong_matches)
    if not context:
        return _NO_EVIDENCE_ANSWER

    return await answer_from_review_context(question=question, context=context)
