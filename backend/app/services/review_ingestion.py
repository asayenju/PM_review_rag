import logging
import re
from datetime import datetime, timezone

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

# Split reviews into intent-sized units before embedding instead of using one long character window.
_SENTENCE_OR_CLAUSE_BOUNDARY = re.compile(
    r"(?<=[.!?;])\s+|(?<=,)\s+(?=(?:and|but|because|so|while|though|however)\b)",
    re.IGNORECASE,
)
_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9'-]*")
# Keep stored chunk text focused on searchable product signals; preserve negation words separately.
_STOP_WORDS = {
    "a",
    "about",
    "above",
    "after",
    "again",
    "against",
    "all",
    "am",
    "an",
    "and",
    "any",
    "are",
    "as",
    "at",
    "be",
    "been",
    "being",
    "between",
    "both",
    "but",
    "by",
    "can",
    "could",
    "did",
    "do",
    "does",
    "doing",
    "down",
    "during",
    "each",
    "few",
    "for",
    "from",
    "had",
    "has",
    "have",
    "having",
    "he",
    "her",
    "here",
    "hers",
    "him",
    "his",
    "how",
    "i",
    "if",
    "in",
    "into",
    "is",
    "it",
    "its",
    "just",
    "me",
    "more",
    "most",
    "my",
    "of",
    "on",
    "once",
    "only",
    "or",
    "our",
    "ours",
    "out",
    "over",
    "own",
    "really",
    "same",
    "she",
    "should",
    "so",
    "some",
    "such",
    "than",
    "that",
    "the",
    "their",
    "theirs",
    "them",
    "then",
    "there",
    "these",
    "they",
    "this",
    "those",
    "through",
    "to",
    "too",
    "under",
    "until",
    "up",
    "very",
    "was",
    "we",
    "were",
    "what",
    "when",
    "where",
    "which",
    "while",
    "who",
    "whom",
    "why",
    "will",
    "with",
    "would",
    "you",
    "your",
    "yours",
}


def _keyword_chunk(text: str) -> str:
    tokens = _TOKEN.findall(text.lower())
    keywords = [token for token in tokens if token not in _STOP_WORDS and len(token) > 1]
    return " ".join(keywords)


def _chunk_text(text: str) -> list[str]:
    clean = " ".join(text.split())
    if not clean:
        return []

    chunks = []
    for unit in _SENTENCE_OR_CLAUSE_BOUNDARY.split(clean):
        chunk = _keyword_chunk(unit)
        if chunk:
            chunks.append(chunk)

    return chunks or [_keyword_chunk(clean) or clean]


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
