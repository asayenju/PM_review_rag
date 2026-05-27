from app.services.query_guardrails import OUT_OF_SCOPE, REVIEW_FEEDBACK, REVIEW_RATING, classify_query, rating_sort_direction


def test_classify_query_allows_review_feedback_questions():
    assert classify_query("What are customers complaining about?") == REVIEW_FEEDBACK
    assert classify_query("What should we improve first?") == REVIEW_FEEDBACK
    assert classify_query("Summarize the public reviews") == REVIEW_FEEDBACK


def test_classify_query_allows_rating_review_questions():
    assert classify_query("What is the worst rating review?") == REVIEW_RATING
    assert classify_query("Which review has the highest rating?") == REVIEW_RATING
    assert rating_sort_direction("What is the worst rating review?") == "asc"
    assert rating_sort_direction("Which review has the highest rating?") == "desc"


def test_classify_query_blocks_unrelated_questions():
    assert classify_query("What is the weather today?") == OUT_OF_SCOPE
    assert classify_query("What is the capital of France?") == OUT_OF_SCOPE
    assert classify_query("Write me a poem about databases") == OUT_OF_SCOPE
