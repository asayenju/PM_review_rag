from fastapi import HTTPException, status
from openai import AsyncOpenAI

from ..core.config import settings


def build_answer_input(question: str, chunks: list[str], history: str = "") -> str:
    safe_question = question.strip()[:settings.query_max_question_chars]
    safe_history = history.strip()[:settings.query_max_history_chars]
    history_section = f"Conversation history:\n{safe_history}\n\n" if safe_history else ""

    chunk_budget = settings.query_max_context_chars // max(len(chunks), 1)
    context_parts = [
        f"[Source {i+1}]\n{chunk.strip()[:chunk_budget]}"
        for i, chunk in enumerate(chunks)
    ]
    structured_context = "\n\n".join(context_parts)

    return f"{history_section}Question:\n{safe_question}\n\nReview context:\n{structured_context}"


async def answer_from_review_context(question: str, chunks: list[str], history: str = "") -> str:
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
            "Before forming your answer, consider all provided context chunks and synthesize insights across them. "
            "Be concise and specific, but ensure your answer reflects the full picture available in the context. "
            "Every factual sentence that uses review evidence must include the relevant source label inline, "
            "such as [Source 1]. Include at least one source citation in every evidence-backed answer. "
            "If the question is outside the assigned feature, outside customer review feedback, asks for private data, "
            "or cannot be answered from the context, politely decline in one sentence."
        ),
        input=build_answer_input(question, chunks, history),
        max_output_tokens=settings.query_max_output_tokens,
    )
    return response.output_text.strip()
