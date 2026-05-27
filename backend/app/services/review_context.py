from ..core.config import settings


def _review_label(review: dict) -> str:
    parts = []
    title = review.get("title")
    rating = review.get("rating")
    reviewer_name = review.get("reviewer_name")
    reviewed_at = review.get("reviewed_at")

    if title:
        parts.append(f"Title: {title}")
    if rating is not None:
        parts.append(f"Rating: {rating}/10")
    if reviewer_name:
        parts.append(f"Reviewer: {reviewer_name}")
    if reviewed_at:
        parts.append(f"Reviewed at: {reviewed_at}")
    return " | ".join(parts)


def build_chunk_context(matches: list[dict]) -> str:
    lines = []
    remaining_chars = settings.query_max_context_chars
    for match in matches:
        chunk_text = (match.get("chunk_text") or "").strip()
        if not chunk_text:
            continue
        metadata = _review_label(match)
        line = f"- {metadata} | Review excerpt: {chunk_text}" if metadata else f"- Review excerpt: {chunk_text}"
        if len(line) > remaining_chars:
            line = line[:remaining_chars].strip()
        if line:
            lines.append(line)
            remaining_chars -= len(line)
        if remaining_chars <= 0:
            break
    return "\n".join(lines)


def build_review_context(reviews: list[dict]) -> str:
    lines = []
    remaining_chars = settings.query_max_context_chars
    for review in reviews:
        body = (review.get("body") or "").strip()
        metadata = _review_label(review)
        line = f"- {metadata} | Review body: {body}" if metadata else f"- Review body: {body}"
        if len(line) > remaining_chars:
            line = line[:remaining_chars].strip()
        if line:
            lines.append(line)
            remaining_chars -= len(line)
        if remaining_chars <= 0:
            break
    return "\n".join(lines)
