from app.core.config import settings
from app.services.openai_answers import build_answer_input


def test_build_answer_input_clamps_question_and_context():
    question = "q" * (settings.query_max_question_chars + 50)
    chunks = ["c" * (settings.query_max_context_chars + 50)]

    payload = build_answer_input(question, chunks)

    assert "q" * settings.query_max_question_chars in payload
    assert "q" * (settings.query_max_question_chars + 1) not in payload
    assert "c" * settings.query_max_context_chars in payload
    assert "c" * (settings.query_max_context_chars + 1) not in payload


def test_build_answer_input_formats_review_context_without_source_labels():
    payload = build_answer_input("What changed?", ["- checkout coupon errors", "- mobile cart resets"])

    assert "Question:\nWhat changed?" in payload
    assert "Review context:\nContext item 1:\n- checkout coupon errors" in payload
    assert "Context item 2:\n- mobile cart resets" in payload
    assert "[Source 1]" not in payload
    assert "embedding" not in payload.lower()


def test_build_answer_input_includes_bounded_history():
    payload = build_answer_input("Follow up?", ["- checkout issue"], "PM: Earlier question\nAssistant: Earlier answer")

    assert "Conversation history:\nPM: Earlier question\nAssistant: Earlier answer" in payload
    assert "Question:\nFollow up?" in payload
    assert "Review context:\nContext item 1:\n- checkout issue" in payload
