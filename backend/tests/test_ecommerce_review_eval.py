import sys
from types import SimpleNamespace

import pytest

from scripts.evaluate_ecommerce_reviews import (
    EcommerceReview,
    build_ecommerce_questions,
    build_ecommerce_reviews,
    build_json_questions,
    build_json_reviews,
    calculate_at_k_metrics,
    infer_topics,
    is_valid_dataset_row,
    is_valid_json_review_row,
    load_dataset_rows,
    map_json_review_row,
    map_dataset_row,
    relevant_dataset_ids,
    sentiment_for_label,
    sentiment_for_rating,
)


def sample_row(**overrides):
    row = {
        "text": "This product shipped quickly and the build quality was much better than expected.",
        "label": 2,
        "rating": 5,
        "category": "Electronics",
        "source": "Amazon",
        "review_id": "amz_rev_001",
    }
    row.update(overrides)
    return row


def test_sentiment_for_label_maps_dataset_labels():
    assert sentiment_for_label(0) == "negative"
    assert sentiment_for_label(1) == "neutral"
    assert sentiment_for_label(2) == "positive"
    assert sentiment_for_label(9) is None


def test_sentiment_for_rating_maps_local_json_ratings():
    assert sentiment_for_rating(1) == "negative"
    assert sentiment_for_rating(3) == "neutral"
    assert sentiment_for_rating(5) == "positive"
    assert sentiment_for_rating(6) is None


def test_is_valid_dataset_row_checks_schema_requirements():
    assert is_valid_dataset_row(sample_row())
    assert not is_valid_dataset_row(sample_row(text="too short"))
    assert not is_valid_dataset_row(sample_row(rating=0))
    assert not is_valid_dataset_row(sample_row(label=9))


def test_is_valid_json_review_row_checks_local_file_requirements():
    row = {
        "id": "r001",
        "title": "Performance issue",
        "text": "Opening a project takes forever after importing thousands of feedback items.",
        "rating": 2,
    }

    assert is_valid_json_review_row(row)
    assert not is_valid_json_review_row({**row, "id": ""})
    assert not is_valid_json_review_row({**row, "text": "too short"})
    assert not is_valid_json_review_row({**row, "rating": 6})


def test_map_dataset_row_fits_review_schema():
    review = map_dataset_row(sample_row(), 1, "2026-01-01T00:00:00+00:00")

    assert review.title == "Ecommerce Eval 001 - Electronics - Amazon"
    assert review.rating == 5
    assert review.reviewer_email == "ecommerce-eval-amz-rev-001-001@example.com"
    assert review.dataset_review_id == "amz_rev_001"
    assert "Category: Electronics." in review.body
    assert "Source: Amazon." in review.body
    assert "Sentiment: positive." in review.body
    assert "Original review:" in review.body


def test_map_json_review_row_fits_review_schema_and_infers_topics():
    review = map_json_review_row(
        {
            "id": "r001",
            "reviewer_name": "Sarah K.",
            "role": "Senior PM",
            "company_size": "201-500",
            "rating": 2,
            "reviewed_at": "2026-03-14",
            "title": "Promising but falls apart at scale",
            "text": "Opening a project takes forever and the Jira sync still requires CSV exports.",
        },
        1,
        "synthetic_reviews.json",
    )

    assert review.title == "Synthetic JSON Eval 001 - Promising but falls apart at scale"
    assert review.rating == 2
    assert review.sentiment == "negative"
    assert review.reviewer_email == "synthetic-json-eval-r001-001@example.com"
    assert review.reviewed_at == "2026-03-14T00:00:00+00:00"
    assert "performance" in review.topics
    assert "integrations" in review.topics
    assert "Role: Senior PM." in review.body


def test_build_ecommerce_reviews_fails_with_too_few_valid_rows():
    with pytest.raises(RuntimeError, match="Need 2 valid ecommerce reviews"):
        build_ecommerce_reviews([sample_row()], count=2)


def test_infer_topics_falls_back_to_general():
    assert infer_topics("Nice tool", "This is useful for our team.") == ("general",)


def test_load_dataset_rows_fails_when_dataset_has_too_few_valid_rows(monkeypatch):
    fake_datasets = SimpleNamespace(load_dataset=lambda *args, **kwargs: [sample_row()])
    monkeypatch.setitem(sys.modules, "datasets", fake_datasets)

    with pytest.raises(RuntimeError, match="produced only 1 valid rows; 2 are required"):
        load_dataset_rows(count=2)


def test_build_ecommerce_questions_uses_categories_sentiments_sources_and_controls():
    reviews = [
        EcommerceReview(
            title=f"title {index}",
            body="body text long enough",
            category=category,
            source=source,
            sentiment=sentiment,
            dataset_review_id=f"review-{index}",
            reviewer_name="Reviewer",
            reviewer_email=f"reviewer-{index}@example.com",
            rating=rating,
            reviewed_at="2026-01-01T00:00:00+00:00",
        )
        for index, (category, source, sentiment, rating) in enumerate(
            [
                ("Electronics", "Amazon", "positive", 5),
                ("Electronics", "Amazon", "negative", 1),
                ("Software/SaaS", "G2", "neutral", 3),
                ("Books", "Amazon", "positive", 4),
            ],
            start=1,
        )
    ]

    questions = build_ecommerce_questions(reviews)
    ids = [question.id for question in questions]

    assert "category-electronics" in ids
    assert "category-software-saas" in ids
    assert "sentiment-positive" in ids
    assert "sentiment-negative" in ids
    assert "sentiment-neutral" in ids
    assert "source-amazon" in ids
    assert "source-g2" in ids
    assert "weather" in ids
    assert "payroll" in ids


def test_build_json_questions_uses_inferred_topics_and_controls():
    reviews = build_json_reviews(
        [
            {
                "id": "r001",
                "title": "Slow Jira sync",
                "text": "The Jira sync is slow and CSV export is still required.",
                "rating": 2,
            },
            {
                "id": "r002",
                "title": "Billing invoices",
                "text": "Finance needs downloadable invoices with tax details.",
                "rating": 3,
            },
        ],
        "synthetic_reviews.json",
    )

    questions = build_json_questions(reviews)
    ids = [question.id for question in questions]

    assert "topic-integrations" in ids
    assert "topic-performance" in ids
    assert "topic-billing" in ids
    assert "weather" in ids
    assert "payroll" in ids


def test_relevant_dataset_ids_filters_by_question_metadata():
    reviews = [
        EcommerceReview(
            title="Electronics",
            body="body",
            category="Electronics",
            source="Amazon",
            sentiment="positive",
            dataset_review_id="review-1",
            reviewer_name="Reviewer",
            reviewer_email="reviewer-1@example.com",
            rating=5,
            reviewed_at="2026-01-01T00:00:00+00:00",
        ),
        EcommerceReview(
            title="Books",
            body="body",
            category="Books",
            source="Amazon",
            sentiment="negative",
            dataset_review_id="review-2",
            reviewer_name="Reviewer",
            reviewer_email="reviewer-2@example.com",
            rating=1,
            reviewed_at="2026-01-01T00:00:00+00:00",
        ),
    ]
    question = build_ecommerce_questions(reviews)[0]

    assert relevant_dataset_ids(question, reviews) == {"review-1"}


def test_relevant_dataset_ids_filters_by_topic_metadata():
    reviews = build_json_reviews(
        [
            {
                "id": "r001",
                "title": "Slow Jira sync",
                "text": "The Jira sync is slow and CSV export is still required.",
                "rating": 2,
            },
            {
                "id": "r002",
                "title": "Billing invoices",
                "text": "Finance needs downloadable invoices with tax details.",
                "rating": 3,
            },
        ],
        "synthetic_reviews.json",
    )
    question = next(item for item in build_json_questions(reviews) if item.id == "topic-integrations")

    assert relevant_dataset_ids(question, reviews) == {"r001"}


def test_calculate_at_k_metrics_uses_k_limited_recall_denominator():
    metrics = calculate_at_k_metrics(
        retrieved_ids=["review-1", "review-3", "review-9"],
        relevant_ids={"review-1", "review-2", "review-3", "review-4", "review-5"},
        reviewed_at_by_id={"review-5": "2026-01-05", "review-3": "2026-01-03"},
        k=3,
    )

    assert metrics["recall"] == 2 / 3
    assert metrics["average_precision"] == ((1 / 1) + (2 / 2)) / 3
    assert metrics["mrr"] == 1
    assert metrics["freshness_rank"] == 0
    assert metrics["hit"] is True
