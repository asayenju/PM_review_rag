from fastapi import APIRouter, Depends

from .dependencies import require_authenticated_user
from ..schemas.query import (
    AssignedFeatureResponse,
    ConversationMessageResponse,
    ConversationResponse,
    CreateConversationRequest,
    SendConversationMessageRequest,
    SendConversationMessageResponse,
)
from ..services.conversations import (
    create_conversation_for_user,
    get_assigned_features_for_user,
    get_conversations_for_user,
    get_messages_for_user,
    send_message_for_user,
)

router = APIRouter(prefix="/api", tags=["conversations"])


@router.get("/me/features", response_model=list[AssignedFeatureResponse])
async def assigned_features_endpoint(user: dict = Depends(require_authenticated_user)):
    return await get_assigned_features_for_user(user)


@router.get("/conversations", response_model=list[ConversationResponse])
async def list_conversations_endpoint(user: dict = Depends(require_authenticated_user)):
    return await get_conversations_for_user(user)


@router.post("/conversations", response_model=ConversationResponse)
async def create_conversation_endpoint(
    payload: CreateConversationRequest,
    user: dict = Depends(require_authenticated_user),
):
    return await create_conversation_for_user(
        user=user,
        org_id=payload.org_id,
        feature_id=payload.feature_id,
        title=payload.title,
    )


@router.get("/conversations/{conversation_id}/messages", response_model=list[ConversationMessageResponse])
async def list_conversation_messages_endpoint(
    conversation_id: str,
    user: dict = Depends(require_authenticated_user),
):
    return await get_messages_for_user(user=user, conversation_id=conversation_id)


@router.post("/conversations/{conversation_id}/messages", response_model=SendConversationMessageResponse)
async def send_conversation_message_endpoint(
    conversation_id: str,
    payload: SendConversationMessageRequest,
    user: dict = Depends(require_authenticated_user),
):
    return await send_message_for_user(user=user, conversation_id=conversation_id, content=payload.content)
