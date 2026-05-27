import asyncio

import pytest
from fastapi import HTTPException

from app.services import query_processing


def test_answer_feature_question_rejects_unassigned_pm_before_embedding(monkeypatch):
    async def fake_has_feature_assignment(profile_id, org_id, feature_id):
        return False

    async def fail_embed_texts(_texts):
        raise AssertionError("embedding should not run for unauthorized feature access")

    monkeypatch.setattr(query_processing, "has_feature_assignment", fake_has_feature_assignment)
    monkeypatch.setattr(query_processing, "embed_texts", fail_embed_texts)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            query_processing.answer_feature_question(
                org_id="org-1",
                feature_id="feature-1",
                question="What are users asking for?",
                user={"id": "profile-1"},
            )
        )

    assert exc.value.status_code == 403
    assert exc.value.detail == "You do not have access to ask about this feature."


def test_answer_feature_question_returns_no_evidence_for_weak_matches(monkeypatch):
    async def fake_has_feature_assignment(profile_id, org_id, feature_id):
        return True

    async def fake_embed_texts(texts):
        assert texts == ["What are users asking for?"]
        return [[0.1, 0.2, 0.3]]

    async def fake_match_review_chunks(org_id, feature_id, query_embedding, match_count):
        assert org_id == "org-1"
        assert feature_id == "feature-1"
        assert query_embedding == [0.1, 0.2, 0.3]
        return [{"chunk_text": "checkout coupon confusion", "similarity": 0.1}]

    async def fail_answer_from_review_context(question, context):
        raise AssertionError("answer generation should not run without strong evidence")

    monkeypatch.setattr(query_processing, "has_feature_assignment", fake_has_feature_assignment)
    monkeypatch.setattr(query_processing, "embed_texts", fake_embed_texts)
    monkeypatch.setattr(query_processing, "match_review_chunks", fake_match_review_chunks)
    monkeypatch.setattr(query_processing, "answer_from_review_context", fail_answer_from_review_context)

    answer = asyncio.run(
        query_processing.answer_feature_question(
            org_id="org-1",
            feature_id="feature-1",
            question="What are users asking for?",
            user={"id": "profile-1"},
        )
    )

    assert answer == "I do not have enough review evidence for that feature yet."


def test_answer_feature_question_generates_answer_from_scoped_context(monkeypatch):
    async def fake_has_feature_assignment(profile_id, org_id, feature_id):
        return True

    async def fake_embed_texts(_texts):
        return [[0.1, 0.2, 0.3]]

    async def fake_match_review_chunks(org_id, feature_id, query_embedding, match_count):
        return [
            {"chunk_text": "checkout coupon application confusing", "similarity": 0.82},
            {"chunk_text": "mobile cart resets across sessions", "similarity": 0.74},
        ]

    async def fake_answer_from_review_context(question, context, history=""):
        assert question == "What should we improve?"
        assert "checkout coupon application confusing" in context
        assert "mobile cart resets across sessions" in context
        return "Users want clearer coupon handling and persistent mobile carts."

    monkeypatch.setattr(query_processing, "has_feature_assignment", fake_has_feature_assignment)
    monkeypatch.setattr(query_processing, "embed_texts", fake_embed_texts)
    monkeypatch.setattr(query_processing, "match_review_chunks", fake_match_review_chunks)
    monkeypatch.setattr(query_processing, "answer_from_review_context", fake_answer_from_review_context)

    answer = asyncio.run(
        query_processing.answer_feature_question(
            org_id="org-1",
            feature_id="feature-1",
            question="What should we improve?",
            user={"id": "profile-1"},
        )
    )

    assert answer == "Users want clearer coupon handling and persistent mobile carts."


def test_answer_feature_question_declines_weather_after_auth_before_embedding(monkeypatch):
    async def fake_has_feature_assignment(profile_id, org_id, feature_id):
        return True

    async def fail_embed_texts(_texts):
        raise AssertionError("embedding should not run for out-of-scope questions")

    async def fail_match_review_chunks(org_id, feature_id, query_embedding, match_count):
        raise AssertionError("retrieval should not run for out-of-scope questions")

    monkeypatch.setattr(query_processing, "has_feature_assignment", fake_has_feature_assignment)
    monkeypatch.setattr(query_processing, "embed_texts", fail_embed_texts)
    monkeypatch.setattr(query_processing, "match_review_chunks", fail_match_review_chunks)

    answer = asyncio.run(
        query_processing.answer_feature_question(
            org_id="org-1",
            feature_id="feature-1",
            question="What is the weather today?",
            user={"id": "profile-1"},
        )
    )

    assert answer == "I can only answer questions about the available customer reviews and product feedback."


def test_answer_feature_question_blocks_unrelated_question_after_auth_before_embedding(monkeypatch):
    async def fake_has_feature_assignment(profile_id, org_id, feature_id):
        return True

    async def fail_embed_texts(_texts):
        raise AssertionError("embedding should not run for out-of-scope questions")

    monkeypatch.setattr(query_processing, "has_feature_assignment", fake_has_feature_assignment)
    monkeypatch.setattr(query_processing, "embed_texts", fail_embed_texts)

    answer = asyncio.run(
        query_processing.answer_feature_question(
            org_id="org-1",
            feature_id="feature-1",
            question="What is the capital of France?",
            user={"id": "profile-1"},
        )
    )

    assert answer == "I can only answer questions about the available customer reviews and product feedback."


def test_answer_feature_question_uses_rating_lookup_without_embedding(monkeypatch):
    async def fake_has_feature_assignment(profile_id, org_id, feature_id):
        return True

    async def fake_list_reviews_for_feature(org_id, feature_id, limit, rating_direction):
        assert org_id == "org-1"
        assert feature_id == "feature-1"
        assert rating_direction == "asc"
        return [
            {
                "title": "Buggy Checkout",
                "rating": 2,
                "reviewer_name": "PM Customer",
                "reviewed_at": "2026-05-27T00:00:00Z",
                "body": "Checkout failed twice with no clear error.",
            }
        ]

    async def fail_embed_texts(_texts):
        raise AssertionError("embedding should not run for rating questions")

    async def fake_answer_from_review_context(question, context, history=""):
        assert "Title: Buggy Checkout" in context
        assert "Rating: 2/10" in context
        return "The worst review is Buggy Checkout with a 2/10."

    monkeypatch.setattr(query_processing, "has_feature_assignment", fake_has_feature_assignment)
    monkeypatch.setattr(query_processing, "list_reviews_for_feature", fake_list_reviews_for_feature)
    monkeypatch.setattr(query_processing, "embed_texts", fail_embed_texts)
    monkeypatch.setattr(query_processing, "answer_from_review_context", fake_answer_from_review_context)

    answer = asyncio.run(
        query_processing.answer_feature_question(
            org_id="org-1",
            feature_id="feature-1",
            question="What is the worst rating review?",
            user={"id": "profile-1"},
        )
    )

    assert answer == "The worst review is Buggy Checkout with a 2/10."
