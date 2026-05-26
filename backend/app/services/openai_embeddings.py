import logging

from fastapi import HTTPException, status
from openai import AsyncOpenAI

from ..core.config import settings

logger = logging.getLogger("app.openai_embeddings")


async def embed_texts(texts: list[str]) -> list[list[float]]:
    if not settings.openai_api_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OPENAI_API_KEY is not configured",
        )
    if not texts:
        return []

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    response = await client.embeddings.create(model=settings.openai_embedding_model, input=texts)
    vectors = [item.embedding for item in response.data]
    if any(len(v) != settings.embedding_dimensions for v in vectors):
        logger.warning("Embedding dimension mismatch with configured value")
    return vectors
