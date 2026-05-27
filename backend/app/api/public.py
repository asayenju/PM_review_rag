from fastapi import APIRouter

from ..schemas.query import PublicQueryRequest, QueryResponse
from ..services.public_query import answer_public_review_question

router = APIRouter(prefix="/api/public", tags=["public"])


@router.post("/query", response_model=QueryResponse)
async def public_query_endpoint(payload: PublicQueryRequest):
    answer = await answer_public_review_question(payload.question)
    return QueryResponse(answer=answer)
