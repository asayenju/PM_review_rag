from fastapi import HTTPException, status

from .query_processing import generate_feature_answer
from .vector_store import (
    create_conversation,
    get_conversation,
    has_feature_assignment,
    insert_conversation_message,
    list_assigned_features,
    list_conversation_messages,
    list_conversations,
    touch_conversation,
)


def _user_id(user: dict) -> str:
    user_id = user.get("id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authenticated user is missing an id")
    return user_id


def _message_response(message: dict) -> dict:
    return {
        "id": message["id"],
        "role": message["role"],
        "content": message["content"],
        "created_at": message.get("created_at"),
    }


def _history_text(messages: list[dict]) -> str:
    lines = []
    for message in messages:
        role = "PM" if message.get("role") == "user" else "Assistant"
        content = " ".join((message.get("content") or "").split())
        if content:
            lines.append(f"{role}: {content}")
    return "\n".join(lines)


async def get_assigned_features_for_user(user: dict) -> list[dict]:
    return await list_assigned_features(_user_id(user))


async def get_conversations_for_user(user: dict) -> list[dict]:
    return await list_conversations(_user_id(user))


async def create_conversation_for_user(user: dict, org_id: str, feature_id: str, title: str | None) -> dict:
    user_id = _user_id(user)
    if not await has_feature_assignment(user_id, org_id, feature_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to this feature.")
    conversation = await create_conversation(
        {
            "org_id": org_id,
            "user_id": user_id,
            "feature_id": feature_id,
            "title": title or "New feature chat",
            "status": "active",
        }
    )
    conversation["feature_name"] = None
    return conversation


async def get_messages_for_user(user: dict, conversation_id: str) -> list[dict]:
    conversation = await get_conversation(conversation_id, _user_id(user))
    messages = await list_conversation_messages(conversation["id"])
    return [_message_response(message) for message in messages]


async def send_message_for_user(user: dict, conversation_id: str, content: str) -> dict:
    user_id = _user_id(user)
    conversation = await get_conversation(conversation_id, user_id)
    org_id = conversation["org_id"]
    feature_id = conversation.get("feature_id")
    if not feature_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Conversation is not attached to a feature.")

    if not await has_feature_assignment(user_id, org_id, feature_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to this feature.")

    user_message = await insert_conversation_message(
        {
            "conversation_id": conversation_id,
            "org_id": org_id,
            "role": "user",
            "content": content,
        }
    )
    recent_messages = await list_conversation_messages(conversation_id, limit=10, newest_first=True)
    history = _history_text([message for message in recent_messages if message["id"] != user_message["id"]])
    answer_result = await generate_feature_answer(
        org_id=org_id,
        feature_id=feature_id,
        question=content,
        user=user,
        history=history,
    )
    assistant_message = await insert_conversation_message(
        {
            "conversation_id": conversation_id,
            "org_id": org_id,
            "role": "assistant",
            "content": answer_result["answer"],
            "retrieved_chunk_ids": answer_result.get("retrieved_chunk_ids") or None,
        }
    )

    await touch_conversation(conversation_id)
    return {
        "user_message": _message_response(user_message),
        "assistant_message": _message_response(assistant_message),
    }
