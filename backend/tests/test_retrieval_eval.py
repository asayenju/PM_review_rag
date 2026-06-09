from scripts.evaluate_retrieval import (
    QUESTIONS,
    aggregate_generation_scores,
    aggregate_metrics,
    build_low_scoring_questions,
    build_generation_judge_input,
    build_retrieved_context,
    build_synthetic_reviews,
    calculate_metrics,
    clean_expected_facts,
    extract_cited_source_ranks,
    parse_generation_judge_response,
    unique_review_ids,
)


def test_build_synthetic_reviews_is_deterministic_shape():
    reviews = build_synthetic_reviews()

    assert len(reviews) == 50
    assert reviews[0].title == "Retrieval Eval 01 - Pricing"
    assert reviews[0].theme == "pricing"
    assert reviews[9].theme == "collaboration"
    assert reviews[10].theme == "pricing"
    assert all(review.body for review in reviews)
    assert all(review.reviewer_email.startswith("retrieval-eval-") for review in reviews)


def test_questions_include_answerable_and_unanswerable_cases():
    assert any(question.answerable for question in QUESTIONS)
    assert any(not question.answerable for question in QUESTIONS)


def test_unique_review_ids_preserves_first_seen_order():
    matches = [
        {"review_id": "review-1"},
        {"review_id": "review-1"},
        {"review_id": "review-2"},
        {"review_id": None},
        {"review_id": "review-3"},
    ]

    assert unique_review_ids(matches) == ["review-1", "review-2", "review-3"]


def test_calculate_metrics_scores_review_level_relevance():
    metrics = calculate_metrics(
        retrieved_ids=["review-3", "review-2", "review-1"],
        relevant_ids={"review-1", "review-2", "review-4"},
        reviewed_at_by_id={
            "review-1": "2026-01-01T00:00:00+00:00",
            "review-2": "2026-01-02T00:00:00+00:00",
            "review-4": "2026-01-04T00:00:00+00:00",
        },
    )

    assert metrics["recall"] == 2 / 3
    assert metrics["average_precision"] == ((1 / 2) + (2 / 3)) / 3
    assert metrics["mrr"] == 1 / 2
    assert metrics["freshness_rank"] == 0
    assert metrics["source_diversity"] == 3
    assert metrics["hit"] is True


def test_calculate_metrics_handles_unanswerable_question():
    metrics = calculate_metrics(
        retrieved_ids=[],
        relevant_ids=set(),
        reviewed_at_by_id={},
    )

    assert metrics == {
        "recall": None,
        "average_precision": None,
        "mrr": None,
        "freshness_rank": None,
        "source_diversity": 0,
        "hit": False,
    }


def test_aggregate_metrics_uses_answerable_questions_for_quality_metrics():
    rows = [
        {
            "answerable": True,
            "metrics": {
                "recall": 1.0,
                "average_precision": 0.75,
                "mrr": 1.0,
                "freshness_rank": 2,
                "source_diversity": 3,
                "hit": True,
            },
        },
        {
            "answerable": True,
            "metrics": {
                "recall": 0.0,
                "average_precision": 0.0,
                "mrr": 0.0,
                "freshness_rank": 0,
                "source_diversity": 0,
                "hit": False,
            },
        },
        {
            "answerable": False,
            "metrics": {
                "recall": None,
                "average_precision": None,
                "mrr": None,
                "freshness_rank": None,
                "source_diversity": 0,
                "hit": False,
            },
        },
    ]

    aggregate = aggregate_metrics(rows)

    assert aggregate["question_count"] == 3
    assert aggregate["answerable_question_count"] == 2
    assert aggregate["recall"] == 0.5
    assert aggregate["mean_average_precision"] == 0.375
    assert aggregate["mrr"] == 0.5
    assert aggregate["freshness_rank"] == 1
    assert aggregate["source_diversity"] == 1
    assert aggregate["hit_rate"] == 0.5


def test_build_retrieved_context_keeps_ranked_source_details():
    context = build_retrieved_context(
        [
            {
                "review_id": "review-1",
                "title": "Pricing",
                "reviewer_name": "PM Buyer",
                "rating": 7,
                "reviewed_at": "2026-01-01T00:00:00+00:00",
                "similarity": 0.87,
                "chunk_text": "pricing page hides seat limits",
            }
        ]
    )

    assert context == [
            {
                "rank": 1,
                "source_label": "Source 1",
                "review_id": "review-1",
                "title": "Pricing",
                "reviewer_name": "PM Buyer",
            "rating": 7,
            "reviewed_at": "2026-01-01T00:00:00+00:00",
            "similarity": 0.87,
            "text": "pricing page hides seat limits",
        }
    ]


def test_clean_expected_facts_keeps_only_supported_facts():
    expected_facts = [
        "Customers say the pricing page hides seat limits and add-on costs until checkout.",
        "Several buyers want a clearer annual discount comparison before they ask finance for approval.",
    ]
    retrieved_context = [
        {
            "rank": 1,
            "text": (
                "Customers say the pricing page hides seat limits and add-on costs until checkout. "
                "The reviewer ties this to pricing."
            ),
        }
    ]

    cleaned = clean_expected_facts(expected_facts, retrieved_context)

    assert cleaned == ["Customers say the pricing page hides seat limits and add-on costs until checkout."]


def test_build_generation_judge_input_includes_answer_context_and_expected_facts():
    judge_input = build_generation_judge_input(
        QUESTIONS[0],
        "Customers want clearer pricing.",
        [{"rank": 1, "text": "Customers say the pricing page hides seat limits and add-on costs until checkout."}],
    )

    assert '"question_id": "pricing-costs"' in judge_input
    assert '"generated_answer": "Customers want clearer pricing."' in judge_input
    assert "pricing page hides seat limits" in judge_input
    assert "Customers say the pricing page hides seat limits" in judge_input
    assert "annual discount comparison" not in judge_input
    assert "used_source_ranks" in judge_input
    assert "faithfulness" in judge_input


def test_parse_generation_judge_response_clamps_scores_and_computes_overall():
    result = parse_generation_judge_response(
        """
        {
          "faithfulness": 5,
          "answer_relevance": 4,
          "completeness": 6,
          "conciseness": 0,
          "used_source_ranks": [1, "2", "bad"],
          "rationale": {"faithfulness": "supported"}
        }
        """
    )

    assert result["scores"] == {
        "faithfulness": 5,
        "answer_relevance": 4,
        "completeness": 5,
        "conciseness": 1,
        "overall": 3.75,
    }
    assert result["used_source_ranks"] == [1, 2]
    assert result["rationale"] == {"faithfulness": "supported"}


def test_extract_cited_source_ranks_preserves_unique_order():
    assert extract_cited_source_ranks("Pricing is unclear [Source 2]. See also [source 1] and [Source 2].") == [2, 1]


def test_build_low_scoring_questions_reports_retrieval_and_generation_gaps():
    rows = [
        {
            "id": "q1",
            "question": "What pricing concerns are customers raising?",
            "answerable": True,
            "answer": "Customers want clearer pricing.",
            "metrics": {
                "recall": 0.5,
                "average_precision": 0.4,
                "mrr": 1.0,
                "freshness_rank": 0,
            },
            "generation_eval": {
                "scores": {
                    "faithfulness": 5,
                    "answer_relevance": 4,
                    "completeness": 3,
                    "conciseness": 5,
                    "overall": 4.25,
                }
            },
            "source_usage": {"judged_used_source_ranks": [1], "cited_source_ranks": []},
        },
        {
            "id": "q2",
            "question": "How should notifications change?",
            "answerable": True,
            "answer": "Too much text.",
            "metrics": {
                "recall": 1.0,
                "average_precision": 1.0,
                "mrr": 1.0,
                "freshness_rank": 1,
            },
            "generation_eval": {
                "scores": {
                    "faithfulness": 2,
                    "answer_relevance": 3,
                    "completeness": 2,
                    "conciseness": 4,
                    "overall": 2.75,
                }
            },
            "source_usage": {"judged_used_source_ranks": [], "cited_source_ranks": [1]},
        },
    ]

    report = build_low_scoring_questions(rows)

    assert report[0]["id"] == "q1"
    assert report[0]["reasons"] == ["recall=0.50", "map=0.40", "completeness=3"]
    assert report[1]["id"] == "q2"
    assert report[1]["reasons"] == ["faithfulness=2", "answer_relevance=3", "completeness=2"]


def test_parse_generation_judge_response_raises_for_malformed_payload():
    try:
        parse_generation_judge_response("not json")
    except ValueError:
        pass
    else:
        raise AssertionError("malformed judge response should raise ValueError")


def test_aggregate_generation_scores_ignores_unjudged_and_error_rows():
    rows = [
        {
            "generation_eval": {
                "scores": {
                    "faithfulness": 5,
                    "answer_relevance": 4,
                    "completeness": 3,
                    "conciseness": 2,
                    "overall": 3.5,
                }
            }
        },
        {"generation_eval": {"error": "parse failed"}},
        {"generation_eval": None},
    ]

    aggregate = aggregate_generation_scores(rows)

    assert aggregate == {
        "judged_question_count": 1,
        "faithfulness": 5,
        "answer_relevance": 4,
        "completeness": 3,
        "conciseness": 2,
        "overall": 3.5,
    }
