import argparse
import asyncio
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean

from app.core.config import settings
from app.services.query_processing import evaluate_feature_retrieval
from app.services.vector_store import find_review_by_title, get_or_create_feature_by_slug, get_or_create_organization
from scripts.evaluate_retrieval import (
    EVAL_USER_EMAIL,
    EVAL_USER_PASSWORD,
    aggregate_generation_scores,
    ask_api,
    build_low_scoring_questions,
    build_retrieved_context,
    build_source_usage,
    clean_expected_facts,
    ensure_feature_assignment,
    judge_generation_answer,
    login_or_signup,
    patch_reviewed_at,
    post_review,
    rechunk_review,
    unique_review_ids,
)


DATASET_NAME = "IberaSoft/ecommerce-reviews-sentiment"
EVAL_ORG_SLUG = "ecommerce-review-eval-org"
EVAL_FEATURE_SLUG = "ecommerce-review-eval-feature"
REVIEW_COUNT = 100
LABEL_TO_SENTIMENT = {0: "negative", 1: "neutral", 2: "positive"}
RATING_TO_SENTIMENT = {1: "negative", 2: "negative", 3: "neutral", 4: "positive", 5: "positive"}
LOCAL_TOPIC_KEYWORDS = {
    "pricing": ("pricing", "price", "seat", "checkout", "fee", "cost", "add-on", "tier"),
    "onboarding": ("onboarding", "setup", "workspace", "checklist", "guide", "empty state"),
    "integrations": ("jira", "salesforce", "integration", "sync", "csv", "export", "field mapping"),
    "reporting": ("dashboard", "report", "chart", "cohort", "saved view", "scheduled", "segments"),
    "performance": ("slow", "performance", "crawl", "load", "lag", "rendering", "import", "takes forever"),
    "permissions": ("permission", "role", "audit log", "security", "contractor", "roadmap data"),
    "mobile": ("mobile", "phone", "offline", "field pm", "save button", "comment threads"),
    "notifications": ("notification", "email", "mention", "alert", "digest", "inbox"),
    "billing": ("billing", "invoice", "receipt", "tax", "purchase order", "po number", "finance"),
    "collaboration": ("triage", "collaboration", "assign", "owner", "duplicate", "decision note", "mention"),
}


@dataclass(frozen=True)
class EcommerceReview:
    title: str
    body: str
    category: str
    source: str
    sentiment: str
    dataset_review_id: str
    reviewer_name: str
    reviewer_email: str
    rating: int
    reviewed_at: str
    topics: tuple[str, ...] = ()


@dataclass(frozen=True)
class EcommerceQuestion:
    id: str
    question: str
    relevance_kind: str | None = None
    relevance_value: str | None = None
    answerable: bool = True


def _clean_text(value, default: str = "") -> str:
    text = " ".join(str(value or default).split())
    return text or default


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "unknown"


def _coerce_int(value, default: int | None = None) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def sentiment_for_label(label) -> str | None:
    return LABEL_TO_SENTIMENT.get(_coerce_int(label))


def sentiment_for_rating(rating) -> str | None:
    return RATING_TO_SENTIMENT.get(_coerce_int(rating))


def is_valid_dataset_row(row: dict) -> bool:
    text = _clean_text(row.get("text"))
    rating = _coerce_int(row.get("rating"))
    sentiment = sentiment_for_label(row.get("label"))
    return bool(text and len(text) >= 20 and rating is not None and 1 <= rating <= 5 and sentiment)


def map_dataset_row(row: dict, index: int, reviewed_at: str) -> EcommerceReview:
    text = _clean_text(row.get("text"))
    category = _clean_text(row.get("category"), "Uncategorized")[:80]
    source = _clean_text(row.get("source"), "Unknown Source")[:80]
    sentiment = sentiment_for_label(row.get("label"))
    if not sentiment:
        raise ValueError(f"Unsupported sentiment label for row {index}: {row.get('label')!r}")
    rating = _coerce_int(row.get("rating"))
    if rating is None or not 1 <= rating <= 5:
        raise ValueError(f"Unsupported rating for row {index}: {row.get('rating')!r}")

    dataset_review_id = _clean_text(row.get("review_id"), f"row-{index:03d}")[:120]
    body = (
        f"Category: {category}. Source: {source}. Sentiment: {sentiment}. "
        f"Original review: {text}"
    )
    return EcommerceReview(
        title=f"Ecommerce Eval {index:03d} - {category} - {source}"[:300],
        body=body,
        category=category,
        source=source,
        sentiment=sentiment,
        dataset_review_id=dataset_review_id,
        reviewer_name="Ecommerce Eval Reviewer",
        reviewer_email=f"ecommerce-eval-{_slug(dataset_review_id)}-{index:03d}@example.com"[:320],
        rating=rating,
        reviewed_at=reviewed_at,
    )


def is_valid_json_review_row(row: dict) -> bool:
    text = _clean_text(row.get("text"))
    title = _clean_text(row.get("title"))
    rating = _coerce_int(row.get("rating"))
    review_id = _clean_text(row.get("id"))
    return bool(review_id and title and text and len(text) >= 20 and rating is not None and 1 <= rating <= 5)


def load_json_review_rows(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("reviews") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        raise RuntimeError(f"{path} must contain a list or an object with a reviews list.")
    valid_rows = [dict(row) for row in rows if isinstance(row, dict) and is_valid_json_review_row(row)]
    if not valid_rows:
        raise RuntimeError(f"{path} did not contain any valid reviews.")
    return valid_rows


def infer_topics(title: str, text: str) -> tuple[str, ...]:
    normalized = f"{title} {text}".lower()
    topics = [
        topic
        for topic, keywords in LOCAL_TOPIC_KEYWORDS.items()
        if any(keyword in normalized for keyword in keywords)
    ]
    return tuple(topics or ("general",))


def map_json_review_row(row: dict, index: int, source_name: str) -> EcommerceReview:
    title = _clean_text(row.get("title"))[:220]
    text = _clean_text(row.get("text"))
    rating = _coerce_int(row.get("rating"))
    if rating is None or not 1 <= rating <= 5:
        raise ValueError(f"Unsupported rating for JSON row {index}: {row.get('rating')!r}")
    sentiment = sentiment_for_rating(rating) or "neutral"
    dataset_review_id = _clean_text(row.get("id"), f"json-row-{index:03d}")[:120]
    reviewer_name = _clean_text(row.get("reviewer_name"), "Synthetic Review Eval Reviewer")[:200]
    role = _clean_text(row.get("role"), "Unknown role")
    company_size = _clean_text(row.get("company_size"), "Unknown company size")
    reviewed_at = _clean_text(row.get("reviewed_at"))
    if reviewed_at:
        reviewed_at = datetime.fromisoformat(reviewed_at).replace(tzinfo=timezone.utc).isoformat()
    else:
        reviewed_at = (datetime.now(timezone.utc) - timedelta(days=index)).isoformat()
    topics = infer_topics(title, text)
    category = ", ".join(topic.title() for topic in topics)
    body = (
        f"Category: {category}. Source: {source_name}. Sentiment: {sentiment}. "
        f"Role: {role}. Company size: {company_size}. Original review: {text}"
    )
    return EcommerceReview(
        title=f"Synthetic JSON Eval {index:03d} - {title}"[:300],
        body=body,
        category=category,
        source=source_name,
        sentiment=sentiment,
        dataset_review_id=dataset_review_id,
        reviewer_name=reviewer_name,
        reviewer_email=f"synthetic-json-eval-{_slug(dataset_review_id)}-{index:03d}@example.com"[:320],
        rating=rating,
        reviewed_at=reviewed_at,
        topics=topics,
    )


def load_dataset_rows(dataset_name: str = DATASET_NAME, count: int = REVIEW_COUNT) -> list[dict]:
    try:
        from datasets import load_dataset
    except ImportError as exc:
        raise RuntimeError("Install backend requirements so Hugging Face datasets can be loaded.") from exc

    try:
        dataset = load_dataset(dataset_name, split="train")
    except Exception as exc:
        raise RuntimeError(f"Could not load dataset {dataset_name!r}: {exc}") from exc

    rows = []
    for row in dataset:
        if is_valid_dataset_row(row):
            rows.append(dict(row))
        if len(rows) == count:
            return rows
    raise RuntimeError(f"Dataset {dataset_name!r} produced only {len(rows)} valid rows; {count} are required.")


def build_ecommerce_reviews(rows: list[dict], count: int = REVIEW_COUNT) -> list[EcommerceReview]:
    if len(rows) < count:
        raise RuntimeError(f"Need {count} valid ecommerce reviews, got {len(rows)}.")
    base_time = datetime.now(timezone.utc) - timedelta(days=count)
    reviews = []
    for index, row in enumerate(rows[:count], start=1):
        reviewed_at = (base_time + timedelta(days=index - 1)).isoformat()
        reviews.append(map_dataset_row(row, index, reviewed_at))
    return reviews


def build_json_reviews(rows: list[dict], source_name: str) -> list[EcommerceReview]:
    return [map_json_review_row(row, index, source_name) for index, row in enumerate(rows, start=1)]


def _top_values(reviews: list[EcommerceReview], attr: str, limit: int) -> list[str]:
    counts = Counter(getattr(review, attr) for review in reviews)
    return [value for value, _ in counts.most_common(limit)]


def build_ecommerce_questions(reviews: list[EcommerceReview]) -> list[EcommerceQuestion]:
    questions = []
    for category in _top_values(reviews, "category", 5):
        questions.append(
            EcommerceQuestion(
                id=f"category-{_slug(category)}",
                question=f"What feedback are customers giving about {category} reviews?",
                relevance_kind="category",
                relevance_value=category,
            )
        )
    for sentiment in [value for value in LABEL_TO_SENTIMENT.values() if any(r.sentiment == value for r in reviews)]:
        questions.append(
            EcommerceQuestion(
                id=f"sentiment-{sentiment}",
                question=f"What {sentiment} customer feedback appears in the reviews?",
                relevance_kind="sentiment",
                relevance_value=sentiment,
            )
        )
    for source in _top_values(reviews, "source", 2):
        questions.append(
            EcommerceQuestion(
                id=f"source-{_slug(source)}",
                question=f"What feedback is coming from {source} reviews?",
                relevance_kind="source",
                relevance_value=source,
            )
        )
    questions.extend(
        [
            EcommerceQuestion("weather", "What is the weather today?", answerable=False),
            EcommerceQuestion("payroll", "What payroll provider should we use?", answerable=False),
        ]
    )
    return questions


def build_json_questions(reviews: list[EcommerceReview]) -> list[EcommerceQuestion]:
    topic_counts = Counter(topic for review in reviews for topic in review.topics if topic != "general")
    questions = [
        EcommerceQuestion(
            id=f"topic-{_slug(topic)}",
            question=f"What {topic} feedback are customers raising in these reviews?",
            relevance_kind="topic",
            relevance_value=topic,
        )
        for topic, _ in topic_counts.most_common(10)
    ]
    questions.extend(
        [
            EcommerceQuestion("weather", "What is the weather today?", answerable=False),
            EcommerceQuestion("payroll", "What payroll provider should we use?", answerable=False),
        ]
    )
    return questions


def relevant_dataset_ids(question: EcommerceQuestion, reviews: list[EcommerceReview]) -> set[str]:
    if not question.answerable or not question.relevance_kind or question.relevance_value is None:
        return set()
    if question.relevance_kind == "topic":
        return {
            review.dataset_review_id
            for review in reviews
            if question.relevance_value in review.topics
        }
    return {
        review.dataset_review_id
        for review in reviews
        if getattr(review, question.relevance_kind) == question.relevance_value
    }


def calculate_at_k_metrics(retrieved_ids: list[str], relevant_ids: set[str], reviewed_at_by_id: dict[str, str], k: int) -> dict:
    if not relevant_ids:
        return {
            "recall": None,
            "average_precision": None,
            "mrr": None,
            "freshness_rank": None,
            "source_diversity": len(set(retrieved_ids)),
            "hit": False,
        }

    retrieved_at_k = retrieved_ids[:k]
    relevant_retrieved = [review_id for review_id in retrieved_at_k if review_id in relevant_ids]
    denominator = min(len(relevant_ids), k)
    recall = len(set(relevant_retrieved)) / denominator if denominator else 0.0
    precision_at_relevant_ranks = [
        len([candidate for candidate in retrieved_at_k[:rank] if candidate in relevant_ids]) / rank
        for rank, review_id in enumerate(retrieved_at_k, start=1)
        if review_id in relevant_ids
    ]
    average_precision = sum(precision_at_relevant_ranks) / denominator if denominator else 0.0
    first_relevant_rank = next(
        (rank for rank, review_id in enumerate(retrieved_at_k, start=1) if review_id in relevant_ids),
        None,
    )
    newest_relevant_id = max(relevant_ids, key=lambda review_id: reviewed_at_by_id.get(review_id, ""))
    freshness_rank = next(
        (rank for rank, review_id in enumerate(retrieved_at_k, start=1) if review_id == newest_relevant_id),
        0,
    )
    return {
        "recall": recall,
        "average_precision": average_precision,
        "mrr": 1 / first_relevant_rank if first_relevant_rank else 0.0,
        "freshness_rank": freshness_rank,
        "source_diversity": len(set(retrieved_at_k)),
        "hit": bool(relevant_retrieved),
    }


def aggregate_metrics(rows: list[dict]) -> dict:
    answerable = [row for row in rows if row["answerable"]]

    def avg(name: str) -> float | None:
        values = [row["metrics"][name] for row in answerable if row["metrics"][name] is not None]
        return mean(values) if values else None

    return {
        "question_count": len(rows),
        "answerable_question_count": len(answerable),
        "recall_at_k": avg("recall"),
        "mean_average_precision_at_k": avg("average_precision"),
        "mrr": avg("mrr"),
        "freshness_rank": avg("freshness_rank"),
        "source_diversity": mean(row["metrics"]["source_diversity"] for row in rows) if rows else 0,
        "hit_rate": mean(1 if row["metrics"]["hit"] else 0 for row in answerable) if answerable else 0,
    }


def build_expected_facts(retrieved_context: list[dict], relevant_review_ids: set[str]) -> list[str]:
    return [
        source["text"]
        for source in retrieved_context
        if source.get("review_id") in relevant_review_ids and source.get("text")
    ]


async def seed_ecommerce_reviews(
    api_base: str,
    token: str,
    org_id: str,
    feature_id: str,
    reviews: list[EcommerceReview],
    force_post: bool,
) -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
    review_id_by_dataset_id = {}
    dataset_id_by_review_id = {}
    reviewed_at_by_dataset_id = {}
    for review in reviews:
        existing = None if force_post else await find_review_by_title(org_id, feature_id, review.title)
        if existing:
            review_id = existing["id"]
            await rechunk_review(api_base, token, review_id)
        else:
            review_id = await post_review(api_base, token, org_id, feature_id, review)
        await patch_reviewed_at(review_id, review.reviewed_at)
        review_id_by_dataset_id[review.dataset_review_id] = review_id
        dataset_id_by_review_id[review_id] = review.dataset_review_id
        reviewed_at_by_dataset_id[review.dataset_review_id] = review.reviewed_at
    return review_id_by_dataset_id, dataset_id_by_review_id, reviewed_at_by_dataset_id


async def run_evaluation(
    api_base: str,
    output: Path,
    force_post: bool,
    skip_generation_eval: bool,
    input_json: Path | None = None,
) -> dict:
    if input_json:
        dataset_rows = load_json_review_rows(input_json)
        reviews = build_json_reviews(dataset_rows, input_json.name)
        questions = build_json_questions(reviews)
        dataset_name = str(input_json)
        org_name = "Synthetic JSON Review Evaluation Org"
        org_slug = "synthetic-json-review-eval-org"
        feature_name = "Synthetic JSON Review Evaluation Feature"
        feature_slug = "synthetic-json-review-eval-feature"
    else:
        dataset_rows = load_dataset_rows()
        reviews = build_ecommerce_reviews(dataset_rows)
        questions = build_ecommerce_questions(reviews)
        dataset_name = DATASET_NAME
        org_name = "Ecommerce Review Evaluation Org"
        org_slug = EVAL_ORG_SLUG
        feature_name = "Ecommerce Review Evaluation Feature"
        feature_slug = EVAL_FEATURE_SLUG

    auth = await login_or_signup(api_base)
    token = auth["access_token"]
    profile_id = auth["user_id"]
    if not profile_id:
        raise RuntimeError("Eval auth response did not include user_id")

    org = await get_or_create_organization(org_name, org_slug)
    feature = await get_or_create_feature_by_slug(org["id"], feature_slug, feature_name)
    await ensure_feature_assignment(profile_id, org["id"], feature["id"])

    review_id_by_dataset_id, dataset_id_by_review_id, reviewed_at_by_dataset_id = await seed_ecommerce_reviews(
        api_base=api_base,
        token=token,
        org_id=org["id"],
        feature_id=feature["id"],
        reviews=reviews,
        force_post=force_post,
    )

    rows = []
    user = {"id": profile_id}
    for item in questions:
        answer = await ask_api(api_base, token, org["id"], feature["id"], item.question)
        retrieval = await evaluate_feature_retrieval(org["id"], feature["id"], item.question, user)
        retrieved_context = build_retrieved_context(retrieval["matches"])
        retrieved_review_ids = unique_review_ids(retrieval["matches"])
        retrieved_dataset_ids = [
            dataset_id_by_review_id[review_id]
            for review_id in retrieved_review_ids
            if review_id in dataset_id_by_review_id
        ]
        relevant_dataset_review_ids = relevant_dataset_ids(item, reviews)
        relevant_review_ids = {
            review_id_by_dataset_id[dataset_id]
            for dataset_id in relevant_dataset_review_ids
            if dataset_id in review_id_by_dataset_id
        }
        metrics = calculate_at_k_metrics(
            retrieved_dataset_ids,
            relevant_dataset_review_ids,
            reviewed_at_by_dataset_id,
            settings.query_match_count,
        )
        expected_facts = clean_expected_facts(build_expected_facts(retrieved_context, relevant_review_ids), retrieved_context)
        generation_eval = None
        if not skip_generation_eval:
            generation_eval = await judge_generation_answer(item, answer, retrieved_context, expected_facts)
        source_usage = build_source_usage(answer, retrieved_context, generation_eval)
        rows.append(
            {
                "id": item.id,
                "question": item.question,
                "answerable": item.answerable,
                "relevance_kind": item.relevance_kind,
                "relevance_value": item.relevance_value,
                "answer": answer,
                "retrieved_context": retrieved_context,
                "expected_facts": expected_facts,
                "retrieved_review_ids": retrieved_review_ids,
                "retrieved_dataset_review_ids": retrieved_dataset_ids,
                "relevant_dataset_review_ids": sorted(relevant_dataset_review_ids),
                "metrics": metrics,
                "generation_eval": generation_eval,
                "source_usage": source_usage,
            }
        )

    report = {
        "dataset": dataset_name,
        "api_base": api_base,
        "org_id": org["id"],
        "feature_id": feature["id"],
        "review_count": len(reviews),
        "k": settings.query_match_count,
        "aggregate": aggregate_metrics(rows),
        "generation_aggregate": aggregate_generation_scores(rows),
        "low_scoring_questions": build_low_scoring_questions(rows),
        "questions": rows,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate RAG over 100 real ecommerce customer reviews.")
    parser.add_argument("--api-base", default="http://127.0.0.1:4000")
    parser.add_argument("--output", default="/tmp/pm_rag_eval_ecommerce_reviews.json")
    parser.add_argument("--input-json", type=Path, help="Load review rows from a local JSON file instead of Hugging Face.")
    parser.add_argument("--force-post", action="store_true", help="Post duplicate ecommerce reviews instead of reusing titles.")
    parser.add_argument("--skip-generation-eval", action="store_true", help="Skip LLM judging and only report retrieval metrics.")
    return parser.parse_args()


def print_summary(report: dict) -> None:
    aggregate = report["aggregate"]
    print(f"Seeded/evaluated {report['review_count']} real ecommerce reviews with k={report['k']}")
    print(f"Dataset: {report['dataset']}")
    print(f"Org: {report['org_id']}")
    print(f"Feature: {report['feature_id']}")
    print("Aggregate retrieval metrics:")
    for name in ["recall_at_k", "mean_average_precision_at_k", "mrr", "freshness_rank", "source_diversity", "hit_rate"]:
        value = aggregate[name]
        print(f"  {name}: {value:.4f}" if isinstance(value, float) else f"  {name}: {value}")
    generation = report.get("generation_aggregate") or {}
    if generation.get("judged_question_count"):
        print("Generation metrics:")
        for name in ["faithfulness", "answer_relevance", "completeness", "conciseness", "overall"]:
            value = generation[name]
            print(f"  {name}: {value:.4f}" if isinstance(value, float) else f"  {name}: {value}")
    low_questions = report.get("low_scoring_questions") or []
    if low_questions:
        print("Low-scoring questions:")
        for row in low_questions:
            print(f"  {row['id']}: {', '.join(row['reasons'])}")


async def async_main() -> None:
    args = parse_args()
    report = await run_evaluation(
        args.api_base.rstrip("/"),
        Path(args.output),
        args.force_post,
        args.skip_generation_eval,
        args.input_json,
    )
    print_summary(report)
    print(f"Wrote detailed results to {args.output}")


if __name__ == "__main__":
    try:
        asyncio.run(async_main())
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
