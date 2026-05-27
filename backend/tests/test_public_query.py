import asyncio

from app.services import public_query


def test_answer_public_review_question_uses_backend_public_scope(monkeypatch):
    async def fake_ensure_public_reviews():
        return "public-org", "public-feature"

    async def fake_embed_texts(texts):
        assert texts == ["What should we improve?"]
        return [[0.4, 0.5, 0.6]]

    async def fake_match_review_chunks(org_id, feature_id, query_embedding, match_count):
        assert org_id == "public-org"
        assert feature_id == "public-feature"
        assert query_embedding == [0.4, 0.5, 0.6]
        return [{"chunk_text": "coupon errors confuse customers", "similarity": 0.8}]

    async def fake_answer_from_review_context(question, context):
        assert question == "What should we improve?"
        assert "coupon errors confuse customers" in context
        return "Customers want clearer coupon errors."

    monkeypatch.setattr(public_query, "ensure_public_reviews", fake_ensure_public_reviews)
    monkeypatch.setattr(public_query, "embed_texts", fake_embed_texts)
    monkeypatch.setattr(public_query, "match_review_chunks", fake_match_review_chunks)
    monkeypatch.setattr(public_query, "answer_from_review_context", fake_answer_from_review_context)

    answer = asyncio.run(public_query.answer_public_review_question("What should we improve?"))

    assert answer == "Customers want clearer coupon errors."


def test_answer_public_review_question_returns_no_evidence_for_weak_matches(monkeypatch):
    async def fake_ensure_public_reviews():
        return "public-org", "public-feature"

    async def fake_embed_texts(_texts):
        return [[0.4, 0.5, 0.6]]

    async def fake_match_review_chunks(org_id, feature_id, query_embedding, match_count):
        return [{"chunk_text": "unrelated review text", "similarity": 0.05}]

    async def fail_answer_from_review_context(question, context):
        raise AssertionError("answer generation should not run without strong public evidence")

    monkeypatch.setattr(public_query, "ensure_public_reviews", fake_ensure_public_reviews)
    monkeypatch.setattr(public_query, "embed_texts", fake_embed_texts)
    monkeypatch.setattr(public_query, "match_review_chunks", fake_match_review_chunks)
    monkeypatch.setattr(public_query, "answer_from_review_context", fail_answer_from_review_context)

    answer = asyncio.run(public_query.answer_public_review_question("What should we improve?"))

    assert answer == "I do not have enough public review evidence for that yet."


def test_answer_public_review_question_declines_weather_before_seed_or_retrieval(monkeypatch):
    async def fail_ensure_public_reviews():
        raise AssertionError("public seed should not run for out-of-scope questions")

    async def fail_embed_texts(_texts):
        raise AssertionError("embedding should not run for out-of-scope questions")

    async def fail_match_review_chunks(org_id, feature_id, query_embedding, match_count):
        raise AssertionError("retrieval should not run for out-of-scope questions")

    monkeypatch.setattr(public_query, "ensure_public_reviews", fail_ensure_public_reviews)
    monkeypatch.setattr(public_query, "embed_texts", fail_embed_texts)
    monkeypatch.setattr(public_query, "match_review_chunks", fail_match_review_chunks)

    answer = asyncio.run(public_query.answer_public_review_question("What is the weather today?"))

    assert answer == "I can only answer questions about the available customer reviews and product feedback."


def test_answer_public_review_question_uses_rating_lookup_without_embedding(monkeypatch):
    async def fake_ensure_public_reviews():
        return "public-org", "public-feature"

    async def fake_list_reviews_for_feature(org_id, feature_id, limit, rating_direction):
        assert org_id == "public-org"
        assert feature_id == "public-feature"
        assert rating_direction == "asc"
        return [
            {
                "title": "Public Demo Review: Error Messaging",
                "rating": 4,
                "reviewer_name": "Checkout Tester",
                "reviewed_at": "2026-05-27T00:00:00Z",
                "body": "When payment fails, the product gives a generic error.",
            }
        ]

    async def fail_embed_texts(_texts):
        raise AssertionError("embedding should not run for rating questions")

    async def fake_answer_from_review_context(question, context):
        assert question == "What is the worst rating review?"
        assert "Title: Public Demo Review: Error Messaging" in context
        assert "Rating: 4/10" in context
        return "The worst rated review is Error Messaging with a 4/10."

    monkeypatch.setattr(public_query, "ensure_public_reviews", fake_ensure_public_reviews)
    monkeypatch.setattr(public_query, "list_reviews_for_feature", fake_list_reviews_for_feature)
    monkeypatch.setattr(public_query, "embed_texts", fail_embed_texts)
    monkeypatch.setattr(public_query, "answer_from_review_context", fake_answer_from_review_context)

    answer = asyncio.run(public_query.answer_public_review_question("What is the worst rating review?"))

    assert answer == "The worst rated review is Error Messaging with a 4/10."
