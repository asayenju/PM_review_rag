import argparse
import asyncio
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean

import httpx
from openai import AsyncOpenAI

from app.core.config import settings
from app.services.query_processing import evaluate_feature_retrieval
from app.services.vector_store import (
    find_review_by_title,
    get_or_create_feature_by_slug,
    get_or_create_organization,
)


EVAL_ORG_SLUG = "retrieval-eval-org"
EVAL_FEATURE_SLUG = "retrieval-eval-feature"
EVAL_USER_EMAIL = "retrieval-eval-pm@example.com"
EVAL_USER_PASSWORD = "RetrievalEval123!"
GENERATION_SCORE_NAMES = ("faithfulness", "answer_relevance", "completeness", "conciseness")
LOW_GENERATION_SCORE_THRESHOLD = 3
LOW_RETRIEVAL_SCORE_THRESHOLD = 0.75


@dataclass(frozen=True)
class SyntheticReview:
    title: str
    body: str
    theme: str
    reviewer_name: str
    reviewer_email: str
    rating: int
    reviewed_at: str


@dataclass(frozen=True)
class EvaluationQuestion:
    id: str
    question: str
    relevant_themes: tuple[str, ...]
    answerable: bool = True


THEMES = {
    "pricing": [
        "Customers say the pricing page hides seat limits and add-on costs until checkout.",
        "Several buyers want a clearer annual discount comparison before they ask finance for approval.",
    ],
    "onboarding": [
        "New admins finish setup faster when the checklist explains invite, import, and launch steps.",
        "Teams complain that empty states do not show what to do after the first workspace is created.",
    ],
    "integrations": [
        "Customers request a native Jira integration that syncs status changes without manual CSV exports.",
        "Salesforce users want field mapping previews before they enable the integration for all teams.",
    ],
    "reporting": [
        "Product leaders want exportable dashboards with cohort filters, saved views, and scheduled emails.",
        "Managers say the charts are useful but the report builder makes it hard to compare segments.",
    ],
    "performance": [
        "Large accounts report slow page loads when they open projects with thousands of feedback items.",
        "Users notice search results lag after importing bulk review history from multiple sources.",
    ],
    "permissions": [
        "Admins need granular roles so contractors can comment without seeing billing or private roadmap data.",
        "Enterprise reviewers ask for audit logs that show permission changes by user and timestamp.",
    ],
    "mobile": [
        "Mobile users say comment threads are cramped and the save button is hard to reach on smaller screens.",
        "Field PMs want offline note capture because customer calls often happen away from stable Wi-Fi.",
    ],
    "notifications": [
        "Users receive too many duplicate email alerts when a teammate edits the same review repeatedly.",
        "PMs want digest notifications grouped by feature instead of a separate alert for every mention.",
    ],
    "billing": [
        "Finance teams need downloadable invoices with purchase order numbers and clearer tax details.",
        "Admins say failed card messages should explain whether the card, bank, or billing address caused the issue.",
    ],
    "collaboration": [
        "Reviewers want shared triage queues where PMs can assign owners and resolve duplicate feedback together.",
        "Teams ask for inline mentions and decision notes so context stays attached to each customer review.",
    ],
}


QUESTIONS = [
    EvaluationQuestion("pricing-costs", "What pricing concerns are customers raising?", ("pricing",)),
    EvaluationQuestion("onboarding-empty-state", "What makes onboarding confusing for new admins?", ("onboarding",)),
    EvaluationQuestion("jira-salesforce", "Which integrations are customers asking us to improve?", ("integrations",)),
    EvaluationQuestion("dashboards", "What reporting and dashboard improvements do PMs want?", ("reporting",)),
    EvaluationQuestion("slow-imports", "Where are users seeing performance problems?", ("performance",)),
    EvaluationQuestion("roles-audit", "What permissions or audit log needs are coming up?", ("permissions",)),
    EvaluationQuestion("mobile-field-pm", "What are mobile PMs struggling with?", ("mobile",)),
    EvaluationQuestion("notification-digest", "How should notifications change?", ("notifications",)),
    EvaluationQuestion("billing-invoices", "What billing issues need product attention?", ("billing",)),
    EvaluationQuestion("triage-collaboration", "How do teams want to collaborate on review triage?", ("collaboration",)),
    EvaluationQuestion("admin-controls", "What admin controls are enterprise customers requesting?", ("permissions", "billing")),
    EvaluationQuestion("workflow-speed", "What slows teams down during setup or daily review work?", ("onboarding", "performance")),
    EvaluationQuestion("fresh-notifications", "What is the latest notification feedback?", ("notifications",)),
    EvaluationQuestion("weather", "What is the weather today?", tuple(), answerable=False),
    EvaluationQuestion("payroll", "What payroll provider should we use?", tuple(), answerable=False),
]


def build_synthetic_reviews(count: int = 50) -> list[SyntheticReview]:
    base_time = datetime.now(timezone.utc) - timedelta(days=count)
    themes = list(THEMES)
    reviews = []
    for index in range(count):
        theme = themes[index % len(themes)]
        theme_lines = THEMES[theme]
        reviewed_at = (base_time + timedelta(days=index)).isoformat()
        title = f"Retrieval Eval {index + 1:02d} - {theme.title()}"
        body = (
            f"{theme_lines[index % len(theme_lines)]} "
            f"The reviewer specifically ties this to the {theme} workflow. "
            f"Impact level {index % 5 + 1}: this feedback should be considered for roadmap planning."
        )
        reviews.append(
            SyntheticReview(
                title=title,
                body=body,
                theme=theme,
                reviewer_name=f"Eval Reviewer {index + 1:02d}",
                reviewer_email=f"retrieval-eval-{index + 1:02d}@example.com",
                rating=(index % 10) + 1,
                reviewed_at=reviewed_at,
            )
        )
    return reviews


def unique_review_ids(matches: list[dict]) -> list[str]:
    seen = set()
    ids = []
    for match in matches:
        review_id = match.get("review_id")
        if review_id and review_id not in seen:
            seen.add(review_id)
            ids.append(review_id)
    return ids


def calculate_metrics(retrieved_ids: list[str], relevant_ids: set[str], reviewed_at_by_id: dict[str, str]) -> dict:
    if not relevant_ids:
        return {
            "recall": None,
            "average_precision": None,
            "mrr": None,
            "freshness_rank": None,
            "source_diversity": len(set(retrieved_ids)),
            "hit": False,
        }

    relevant_retrieved = [review_id for review_id in retrieved_ids if review_id in relevant_ids]
    recall = len(set(relevant_retrieved)) / len(relevant_ids)
    precision_at_relevant_ranks = [
        len([candidate for candidate in retrieved_ids[:rank] if candidate in relevant_ids]) / rank
        for rank, review_id in enumerate(retrieved_ids, start=1)
        if review_id in relevant_ids
    ]
    average_precision = sum(precision_at_relevant_ranks) / len(relevant_ids)
    first_relevant_rank = next(
        (rank for rank, review_id in enumerate(retrieved_ids, start=1) if review_id in relevant_ids),
        None,
    )
    newest_relevant_id = max(relevant_ids, key=lambda review_id: reviewed_at_by_id.get(review_id, ""))
    freshness_rank = next(
        (rank for rank, review_id in enumerate(retrieved_ids, start=1) if review_id == newest_relevant_id),
        0,
    )
    return {
        "recall": recall,
        "average_precision": average_precision,
        "mrr": 1 / first_relevant_rank if first_relevant_rank else 0.0,
        "freshness_rank": freshness_rank,
        "source_diversity": len(set(retrieved_ids)),
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
        "recall": avg("recall"),
        "mean_average_precision": avg("average_precision"),
        "mrr": avg("mrr"),
        "freshness_rank": avg("freshness_rank"),
        "source_diversity": mean(row["metrics"]["source_diversity"] for row in rows) if rows else 0,
        "hit_rate": mean(1 if row["metrics"]["hit"] else 0 for row in answerable) if answerable else 0,
    }


def expected_facts_for_question(question: EvaluationQuestion) -> list[str]:
    facts = []
    for theme in question.relevant_themes:
        facts.extend(THEMES.get(theme, []))
    return facts


def _normalize_support_text(text: str) -> str:
    return " ".join(text.lower().split())


def clean_expected_facts(expected_facts: list[str], retrieved_context: list[dict]) -> list[str]:
    retrieved_text = "\n".join(_normalize_support_text(item.get("text") or "") for item in retrieved_context)
    return [fact for fact in expected_facts if _normalize_support_text(fact) in retrieved_text]


def build_retrieved_context(matches: list[dict]) -> list[dict]:
    context = []
    for rank, match in enumerate(matches, start=1):
        context.append(
            {
                "rank": rank,
                "source_label": f"Source {rank}",
                "review_id": match.get("review_id"),
                "title": match.get("title"),
                "reviewer_name": match.get("reviewer_name"),
                "rating": match.get("rating"),
                "reviewed_at": match.get("reviewed_at"),
                "similarity": match.get("similarity"),
                "text": match.get("chunk_text") or match.get("body") or "",
            }
        )
    return context


def build_generation_judge_input(
    question: EvaluationQuestion,
    answer: str,
    retrieved_context: list[dict],
    expected_facts: list[str] | None = None,
) -> str:
    expected_facts = expected_facts if expected_facts is not None else clean_expected_facts(
        expected_facts_for_question(question),
        retrieved_context,
    )
    payload = {
        "question_id": question.id,
        "question": question.question,
        "answerable": question.answerable,
        "generated_answer": answer,
        "retrieved_context": retrieved_context,
        "expected_facts": expected_facts,
        "rubric": {
            "faithfulness": "1 means unsupported or contradicted by retrieved context; 5 means every material claim is supported by retrieved context.",
            "answer_relevance": "1 means it does not answer the question; 5 means it directly and specifically answers the question.",
            "completeness": "1 means it misses most expected facts or fails to refuse unanswerable questions; 5 means it covers the expected facts appropriate to the question.",
            "conciseness": "1 means verbose, repetitive, or padded; 5 means concise without omitting important information.",
        },
        "source_usage_task": (
            "Identify which retrieved context sources materially support the generated answer. "
            "Return their integer ranks in used_source_ranks. If the answer refuses or does not use context, return an empty list."
        ),
    }
    return json.dumps(payload, indent=2)


def _extract_json_object(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


def parse_generation_judge_response(text: str) -> dict:
    payload = _extract_json_object(text)
    scores = {}
    for name in GENERATION_SCORE_NAMES:
        value = int(payload[name])
        scores[name] = max(1, min(5, value))
    scores["overall"] = mean(scores[name] for name in GENERATION_SCORE_NAMES)
    used_source_ranks = []
    for rank in payload.get("used_source_ranks") or []:
        try:
            used_source_ranks.append(int(rank))
        except (TypeError, ValueError):
            continue
    return {
        "scores": scores,
        "used_source_ranks": used_source_ranks,
        "rationale": payload.get("rationale") or {},
    }


def aggregate_generation_scores(rows: list[dict]) -> dict:
    judged_rows = [row for row in rows if row.get("generation_eval") and not row["generation_eval"].get("error")]
    if not judged_rows:
        return {
            "judged_question_count": 0,
            "faithfulness": None,
            "answer_relevance": None,
            "completeness": None,
            "conciseness": None,
            "overall": None,
        }

    def avg(name: str) -> float:
        return mean(row["generation_eval"]["scores"][name] for row in judged_rows)

    return {
        "judged_question_count": len(judged_rows),
        "faithfulness": avg("faithfulness"),
        "answer_relevance": avg("answer_relevance"),
        "completeness": avg("completeness"),
        "conciseness": avg("conciseness"),
        "overall": avg("overall"),
    }


async def judge_generation_answer(
    question: EvaluationQuestion,
    answer: str,
    retrieved_context: list[dict],
    expected_facts: list[str] | None = None,
) -> dict:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required for generation evaluation")

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    judge_input = build_generation_judge_input(question, answer, retrieved_context, expected_facts)
    instructions = (
        "You are a strict RAG answer evaluator. Score the generated answer using only the supplied "
        "retrieved context and expected facts. Return only valid JSON with integer scores from 1 to 5 "
        "for faithfulness, answer_relevance, completeness, and conciseness, a used_source_ranks array, "
        "and a rationale object. "
        "For unanswerable questions, reward answers that refuse or say there is not enough evidence."
    )
    for attempt in range(2):
        response = await client.responses.create(
            model=settings.openai_query_model,
            instructions=instructions,
            input=judge_input,
            max_output_tokens=500,
        )
        try:
            return parse_generation_judge_response(response.output_text.strip())
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            if attempt == 1:
                return {"error": f"Judge response parse failed: {exc}", "raw_response": response.output_text.strip()}
    return {"error": "Judge response retry loop exited unexpectedly"}


def service_headers() -> dict[str, str]:
    if not settings.supabase_service_role_key:
        raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY is required for retrieval evaluation")
    return {
        "apikey": settings.supabase_service_role_key,
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "Content-Type": "application/json",
    }


async def login_or_signup(api_base: str) -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        login_response = await client.post(
            f"{api_base}/api/auth/login",
            json={"email": EVAL_USER_EMAIL, "password": EVAL_USER_PASSWORD},
        )
        if login_response.status_code == 200:
            return login_response.json()

        signup_response = await client.post(
            f"{api_base}/api/auth/signup",
            json={
                "display_name": "Retrieval Eval PM",
                "email": EVAL_USER_EMAIL,
                "password": EVAL_USER_PASSWORD,
            },
        )
        if signup_response.status_code == 200:
            return signup_response.json()

        retry_login = await client.post(
            f"{api_base}/api/auth/login",
            json={"email": EVAL_USER_EMAIL, "password": EVAL_USER_PASSWORD},
        )
        retry_login.raise_for_status()
        return retry_login.json()


async def ensure_feature_assignment(profile_id: str, org_id: str, feature_id: str) -> None:
    headers = service_headers()
    params = {
        "profile_id": f"eq.{profile_id}",
        "org_id": f"eq.{org_id}",
        "feature_id": f"eq.{feature_id}",
        "select": "id",
        "limit": "1",
    }
    url = f"{settings.supabase_url}/rest/v1/pm_feature_assignments"
    async with httpx.AsyncClient(timeout=20) as client:
        lookup = await client.get(url, headers=headers, params=params)
        lookup.raise_for_status()
        if lookup.json():
            return
        create = await client.post(
            url,
            headers={**headers, "Prefer": "return=minimal"},
            json=[{"profile_id": profile_id, "org_id": org_id, "feature_id": feature_id}],
        )
        create.raise_for_status()


async def patch_reviewed_at(review_id: str, reviewed_at: str) -> None:
    url = f"{settings.supabase_url}/rest/v1/reviews?id=eq.{review_id}"
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.patch(url, headers=service_headers(), json={"reviewed_at": reviewed_at})
    response.raise_for_status()


async def post_review(api_base: str, token: str, org_id: str, feature_id: str, review: SyntheticReview) -> str:
    payload = {
        "org_id": org_id,
        "feature_id": feature_id,
        "title": review.title,
        "body": review.body,
        "reviewer_name": review.reviewer_name,
        "reviewer_email": review.reviewer_email,
        "rating": review.rating,
    }
    for attempt in range(3):
        async with httpx.AsyncClient(timeout=90) as client:
            response = await client.post(
                f"{api_base}/api/reviews",
                headers={"Authorization": f"Bearer {token}"},
                json=payload,
            )
        if response.status_code < 500:
            response.raise_for_status()
            return response.json()["review_id"]
        if attempt == 2:
            response.raise_for_status()
        await asyncio.sleep(1.0 * (attempt + 1))
    raise RuntimeError("Review post retry loop exited unexpectedly")


async def rechunk_review(api_base: str, token: str, review_id: str) -> None:
    for attempt in range(3):
        async with httpx.AsyncClient(timeout=90) as client:
            response = await client.post(
                f"{api_base}/api/reviews/{review_id}/chunk",
                headers={"Authorization": f"Bearer {token}"},
            )
        if response.status_code < 500:
            response.raise_for_status()
            return
        if attempt == 2:
            response.raise_for_status()
        await asyncio.sleep(1.0 * (attempt + 1))


async def ask_api(api_base: str, token: str, org_id: str, feature_id: str, question: str) -> str:
    async with httpx.AsyncClient(timeout=90) as client:
        response = await client.post(
            f"{api_base}/api/query",
            headers={"Authorization": f"Bearer {token}"},
            json={"org_id": org_id, "feature_id": feature_id, "question": question},
        )
    response.raise_for_status()
    return response.json()["answer"]


def extract_cited_source_ranks(answer: str) -> list[int]:
    seen = set()
    ranks = []
    for match in re.finditer(r"\[Source\s+(\d+)\]", answer, flags=re.IGNORECASE):
        rank = int(match.group(1))
        if rank not in seen:
            seen.add(rank)
            ranks.append(rank)
    return ranks


def build_source_usage(answer: str, retrieved_context: list[dict], generation_eval: dict | None) -> dict:
    by_rank = {source["rank"]: source for source in retrieved_context}
    cited_ranks = extract_cited_source_ranks(answer)
    judged_ranks = []
    if generation_eval and not generation_eval.get("error"):
        judged_ranks = generation_eval.get("used_source_ranks") or []
    used_ranks = [rank for rank in judged_ranks if rank in by_rank]
    return {
        "cited_source_ranks": [rank for rank in cited_ranks if rank in by_rank],
        "judged_used_source_ranks": used_ranks,
        "judged_used_sources": [by_rank[rank] for rank in used_ranks],
    }


def low_score_reasons(row: dict) -> list[str]:
    reasons = []
    if row["answerable"]:
        recall = row["metrics"].get("recall")
        average_precision = row["metrics"].get("average_precision")
        if recall is not None and recall < LOW_RETRIEVAL_SCORE_THRESHOLD:
            reasons.append(f"recall={recall:.2f}")
        if average_precision is not None and average_precision < LOW_RETRIEVAL_SCORE_THRESHOLD:
            reasons.append(f"map={average_precision:.2f}")

    generation_eval = row.get("generation_eval")
    if generation_eval and not generation_eval.get("error"):
        for name in GENERATION_SCORE_NAMES:
            score = generation_eval["scores"][name]
            if score <= LOW_GENERATION_SCORE_THRESHOLD:
                reasons.append(f"{name}={score}")
    return reasons


def build_low_scoring_questions(rows: list[dict]) -> list[dict]:
    diagnostics = []
    for row in rows:
        reasons = low_score_reasons(row)
        if not reasons:
            continue
        generation_eval = row.get("generation_eval") or {}
        diagnostics.append(
            {
                "id": row["id"],
                "question": row["question"],
                "answerable": row["answerable"],
                "reasons": reasons,
                "retrieval": {
                    "recall": row["metrics"].get("recall"),
                    "mean_average_precision": row["metrics"].get("average_precision"),
                    "mrr": row["metrics"].get("mrr"),
                    "freshness_rank": row["metrics"].get("freshness_rank"),
                },
                "generation_scores": generation_eval.get("scores"),
                "used_source_ranks": row.get("source_usage", {}).get("judged_used_source_ranks", []),
                "cited_source_ranks": row.get("source_usage", {}).get("cited_source_ranks", []),
                "answer": row["answer"],
            }
        )
    return diagnostics


async def seed_reviews(
    api_base: str,
    token: str,
    org_id: str,
    feature_id: str,
    reviews: list[SyntheticReview],
    force_post: bool,
) -> tuple[dict[str, str], dict[str, str]]:
    review_id_by_title = {}
    reviewed_at_by_id = {}
    for review in reviews:
        existing = None if force_post else await find_review_by_title(org_id, feature_id, review.title)
        if existing:
            review_id = existing["id"]
            await rechunk_review(api_base, token, review_id)
        else:
            review_id = await post_review(api_base, token, org_id, feature_id, review)
        await patch_reviewed_at(review_id, review.reviewed_at)
        review_id_by_title[review.title] = review_id
        reviewed_at_by_id[review_id] = review.reviewed_at
    return review_id_by_title, reviewed_at_by_id


async def run_evaluation(api_base: str, output: Path, force_post: bool, skip_generation_eval: bool) -> dict:
    auth = await login_or_signup(api_base)
    token = auth["access_token"]
    profile_id = auth["user_id"]
    if not profile_id:
        raise RuntimeError("Eval auth response did not include user_id")

    org = await get_or_create_organization("Retrieval Evaluation Org", EVAL_ORG_SLUG)
    feature = await get_or_create_feature_by_slug(org["id"], EVAL_FEATURE_SLUG, "Retrieval Evaluation Feature")
    await ensure_feature_assignment(profile_id, org["id"], feature["id"])

    reviews = build_synthetic_reviews()
    review_id_by_title, reviewed_at_by_id = await seed_reviews(
        api_base=api_base,
        token=token,
        org_id=org["id"],
        feature_id=feature["id"],
        reviews=reviews,
        force_post=force_post,
    )
    review_ids_by_theme: dict[str, set[str]] = {}
    for review in reviews:
        review_ids_by_theme.setdefault(review.theme, set()).add(review_id_by_title[review.title])

    rows = []
    user = {"id": profile_id}
    for item in QUESTIONS:
        answer = await ask_api(api_base, token, org["id"], feature["id"], item.question)
        retrieval = await evaluate_feature_retrieval(org["id"], feature["id"], item.question, user)
        retrieved_context = build_retrieved_context(retrieval["matches"])
        retrieved_ids = unique_review_ids(retrieval["matches"])
        relevant_ids = set()
        for theme in item.relevant_themes:
            relevant_ids.update(review_ids_by_theme.get(theme, set()))
        metrics = calculate_metrics(retrieved_ids, relevant_ids, reviewed_at_by_id)
        expected_facts = clean_expected_facts(expected_facts_for_question(item), retrieved_context)
        generation_eval = None
        if not skip_generation_eval:
            generation_eval = await judge_generation_answer(item, answer, retrieved_context, expected_facts)
        source_usage = build_source_usage(answer, retrieved_context, generation_eval)
        rows.append(
            {
                "id": item.id,
                "question": item.question,
                "answerable": item.answerable,
                "answer": answer,
                "retrieved_context": retrieved_context,
                "expected_facts": expected_facts,
                "retrieved_review_ids": retrieved_ids,
                "relevant_review_ids": sorted(relevant_ids),
                "metrics": metrics,
                "generation_eval": generation_eval,
                "source_usage": source_usage,
            }
        )

    report = {
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
    parser = argparse.ArgumentParser(description="Seed synthetic PM reviews and evaluate retrieval and generation quality.")
    parser.add_argument("--api-base", default="http://127.0.0.1:4000")
    parser.add_argument("--output", default="/tmp/pm_rag_eval_results_generation.json")
    parser.add_argument("--force-post", action="store_true", help="Post duplicate synthetic reviews instead of reusing titles.")
    parser.add_argument("--skip-generation-eval", action="store_true", help="Skip LLM judging and only report retrieval metrics.")
    return parser.parse_args()


def print_summary(report: dict) -> None:
    aggregate = report["aggregate"]
    print(f"Seeded/evaluated {report['review_count']} synthetic reviews with k={report['k']}")
    print(f"Org: {report['org_id']}")
    print(f"Feature: {report['feature_id']}")
    print("Aggregate metrics:")
    for name in ["recall", "mean_average_precision", "mrr", "freshness_rank", "source_diversity", "hit_rate"]:
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
    )
    print_summary(report)
    print(f"Wrote detailed results to {args.output}")


if __name__ == "__main__":
    asyncio.run(async_main())
