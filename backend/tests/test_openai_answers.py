from app.core.config import settings
from app.services.openai_answers import build_answer_input


def test_build_answer_input_clamps_question_and_context():
    question = "q" * (settings.query_max_question_chars + 50)
    context = "c" * (settings.query_max_context_chars + 50)

    payload = build_answer_input(question, context)

    assert "q" * settings.query_max_question_chars in payload
    assert "q" * (settings.query_max_question_chars + 1) not in payload
    assert "c" * settings.query_max_context_chars in payload
    assert "c" * (settings.query_max_context_chars + 1) not in payload


def test_build_answer_input_only_contains_question_and_review_context():
    payload = build_answer_input("What changed?", "- checkout coupon errors")

    assert "Question:\nWhat changed?" in payload
    assert "Review context:\n- checkout coupon errors" in payload
    assert "embedding" not in payload.lower()
    assert "[" not in payload
