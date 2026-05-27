from fastapi import HTTPException, status
from openai import AsyncOpenAI

from ..core.config import settings


def build_answer_input(question: str, context: str) -> str:
    safe_question = question.strip()[: settings.query_max_question_chars]
    safe_context = context.strip()[: settings.query_max_context_chars]
    return f"Question:\n{safe_question}\n\nReview context:\n{safe_context}"


async def answer_from_review_context(question: str, context: str) -> str:
    if not settings.openai_api_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OPENAI_API_KEY is not configured",
        )

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    response = await client.responses.create(
        model=settings.openai_query_model,
        instructions=(
            "You answer product manager questions using only the supplied customer review context. "
            "Keep the answer concise and specific. If the question is outside the assigned feature, "
            "outside customer review feedback, asks for private data, or cannot be answered from the "
            "context, politely decline in one sentence."
        ),
        input=build_answer_input(question, context),
        max_output_tokens=settings.query_max_output_tokens,
    )
    return response.output_text.strip()
