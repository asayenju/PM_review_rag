import asyncio

from app.services import conversations


def test_send_message_for_user_passes_recent_history(monkeypatch):
    async def fake_get_conversation(conversation_id, user_id):
        return {"id": conversation_id, "org_id": "org-1", "feature_id": "feature-1"}

    async def fake_has_feature_assignment(user_id, org_id, feature_id):
        return True

    async def fake_insert_conversation_message(payload):
        return {
            "id": "user-message" if payload["role"] == "user" else "assistant-message",
            "role": payload["role"],
            "content": payload["content"],
            "created_at": "2026-05-27T00:00:00Z",
        }

    async def fake_list_conversation_messages(conversation_id, limit=None, newest_first=False):
        return [
            {"id": "old-user", "role": "user", "content": "What did customers dislike?"},
            {"id": "old-assistant", "role": "assistant", "content": "They disliked coupon errors."},
            {"id": "user-message", "role": "user", "content": "What should we prioritize?"},
        ]

    async def fake_generate_feature_answer(org_id, feature_id, question, user, history=""):
        assert org_id == "org-1"
        assert feature_id == "feature-1"
        assert question == "What should we prioritize?"
        assert "PM: What did customers dislike?" in history
        assert "Assistant: They disliked coupon errors." in history
        assert "What should we prioritize?" not in history
        return {"answer": "Prioritize coupon error clarity.", "retrieved_chunk_ids": ["chunk-1"]}

    async def fake_touch_conversation(conversation_id):
        return None

    monkeypatch.setattr(conversations, "get_conversation", fake_get_conversation)
    monkeypatch.setattr(conversations, "has_feature_assignment", fake_has_feature_assignment)
    monkeypatch.setattr(conversations, "insert_conversation_message", fake_insert_conversation_message)
    monkeypatch.setattr(conversations, "list_conversation_messages", fake_list_conversation_messages)
    monkeypatch.setattr(conversations, "generate_feature_answer", fake_generate_feature_answer)
    monkeypatch.setattr(conversations, "touch_conversation", fake_touch_conversation)

    response = asyncio.run(
        conversations.send_message_for_user(
            user={"id": "profile-1"},
            conversation_id="conversation-1",
            content="What should we prioritize?",
        )
    )

    assert response["assistant_message"]["content"] == "Prioritize coupon error clarity."
