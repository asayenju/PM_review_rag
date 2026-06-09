import logging
from datetime import datetime, timezone

from langchain_text_splitters import RecursiveCharacterTextSplitter

from .openai_embeddings import embed_texts
from .vector_store import (
    create_review,
    delete_chunks_for_review,
    get_review,
    insert_chunks,
    update_review_status,
)
from ..core.config import settings

logger = logging.getLogger("app.review_ingestion")


def _chunk_text(text: str) -> list[str]:
    clean = " ".join(text.split())
    if not clean:
        return []

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size_chars,
        chunk_overlap=settings.chunk_overlap_chars,
    )
    return [chunk.strip() for chunk in splitter.split_text(clean) if chunk.strip()]


async def create_review_and_process(
    org_id: str,
    body: str,
    feature_id: str | None,
    title: str | None,
    reviewer_name: str | None,
    reviewer_email: str | None,
    rating: int | None,
) -> tuple[str, int, str]:
    review = await create_review(
        {
            "org_id": org_id,
            "feature_id": feature_id,
            "title": title,
            "body": body,
            "reviewer_name": reviewer_name,
            "reviewer_email": reviewer_email,
            "rating": rating,
            "status": "pending",
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    review_id = review["id"]
    chunk_count = await process_review_chunks(review_id)
    return review_id, chunk_count, "ready"


async def process_review_chunks(review_id: str) -> int:
    review = await get_review(review_id)
    try:
        await update_review_status(review_id, "chunking")
        chunks = _chunk_text(review["body"])
        await delete_chunks_for_review(review_id)

        await update_review_status(review_id, "embedding")
        vectors = await embed_texts(chunks)

        payload = []
        for i, (chunk_text, vector) in enumerate(zip(chunks, vectors)):
            payload.append(
                {
                    "review_id": review_id,
                    "org_id": review["org_id"],
                    "feature_id": review.get("feature_id"),
                    "chunk_text": chunk_text,
                    "chunk_index": i,
                    "embedding_model": settings.openai_embedding_model,
                    "dimensions": len(vector),
                    "embedding": vector,
                }
            )
        await insert_chunks(payload)
        await update_review_status(review_id, "ready")
        return len(payload)
    except Exception:
        logger.exception("Review chunk processing failed for review_id=%s", review_id)
        await update_review_status(review_id, "failed")
        raise
