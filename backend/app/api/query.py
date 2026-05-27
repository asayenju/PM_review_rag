from fastapi import APIRouter, Depends

from .dependencies import require_authenticated_user
from ..schemas.query import QueryRequest, QueryResponse
from ..services.query_processing import answer_feature_question

router = APIRouter(prefix="/api", tags=["query"])


@router.post("/query", response_model=QueryResponse)
async def query_endpoint(
    payload: QueryRequest,
    user: dict = Depends(require_authenticated_user),
):
    answer = await answer_feature_question(
        org_id=payload.org_id,
        feature_id=payload.feature_id,
        question=payload.question,
        user=user,
    )
    return QueryResponse(answer=answer)
