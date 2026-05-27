from fastapi import HTTPException, status

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
from .vector_store import has_feature_assignment, list_reviews_for_feature, match_review_chunks
from ..core.config import settings

_NO_EVIDENCE_ANSWER = "I do not have enough review evidence for that feature yet."
_NO_ACCESS_DETAIL = "You do not have access to ask about this feature."


def _user_profile_id(user: dict) -> str | None:
    return user.get("id")


async def generate_feature_answer(
    org_id: str,
    feature_id: str,
    question: str,
    user: dict,
    history: str = "",
) -> dict:
    profile_id = _user_profile_id(user)
    if not profile_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authenticated user is missing an id")

    is_assigned = await has_feature_assignment(profile_id=profile_id, org_id=org_id, feature_id=feature_id)
    if not is_assigned:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=_NO_ACCESS_DETAIL)

    query_intent = classify_query(question)
    if query_intent == OUT_OF_SCOPE:
        return {"answer": OUT_OF_SCOPE_ANSWER, "retrieved_chunk_ids": []}

    if query_intent == REVIEW_RATING:
        reviews = await list_reviews_for_feature(
            org_id=org_id,
            feature_id=feature_id,
            limit=settings.query_match_count,
            rating_direction=rating_sort_direction(question),
        )
        context = build_review_context(reviews)
        if not context:
            return {"answer": _NO_EVIDENCE_ANSWER, "retrieved_chunk_ids": []}
        answer = await answer_from_review_context(question=question, context=context, history=history)
        return {"answer": answer, "retrieved_chunk_ids": []}

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
        return {"answer": _NO_EVIDENCE_ANSWER, "retrieved_chunk_ids": []}

    answer = await answer_from_review_context(question=question, context=context, history=history)
    return {
        "answer": answer,
        "retrieved_chunk_ids": [match["chunk_id"] for match in strong_matches if match.get("chunk_id")],
    }


async def answer_feature_question(org_id: str, feature_id: str, question: str, user: dict) -> str:
    result = await generate_feature_answer(org_id=org_id, feature_id=feature_id, question=question, user=user)
    return result["answer"]
