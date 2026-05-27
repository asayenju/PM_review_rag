import re

REVIEW_FEEDBACK = "review_feedback"
REVIEW_RATING = "review_rating"
OUT_OF_SCOPE = "out_of_scope"
OUT_OF_SCOPE_ANSWER = (
    "I can only answer questions about the available customer reviews and product feedback."
)

_RATING_PATTERNS = [
    r"\bworst\b",
    r"\blowest\b",
    r"\bbest\b",
    r"\bhighest\b",
    r"\bbad(?:dest)?\b",
    r"\blow[-\s]?rated\b",
    r"\bhigh[-\s]?rated\b",
    r"\brating\b",
    r"\brated\b",
    r"\brank(?:ed|ing)?\b",
]

_REVIEW_PATTERNS = [
    r"\breviews?\b",
    r"\bcustomers?\b",
    r"\busers?\b",
    r"\bfeedback\b",
    r"\bcomplain(?:t|ts|ing)?\b",
    r"\bpain points?\b",
    r"\bissues?\b",
    r"\bproblems?\b",
    r"\bfriction\b",
    r"\bconfus(?:e|ed|ing|ion)\b",
    r"\bimprove(?:ment|ments|d|s)?\b",
    r"\bpriorit(?:y|ize|ise|ization)\b",
    r"\blike\b",
    r"\blove\b",
    r"\bpositive\b",
    r"\bnegative\b",
    r"\bsentiment\b",
    r"\bsummar(?:y|ize|ise)\b",
    r"\btheme(?:s)?\b",
    r"\bcheckout\b",
    r"\bcart\b",
    r"\bcoupon\b",
    r"\bpayment\b",
    r"\border\b",
    r"\bshipping\b",
]

_ASC_RATING_PATTERNS = [
    r"\bworst\b",
    r"\blowest\b",
    r"\bbad(?:dest)?\b",
    r"\blow[-\s]?rated\b",
]


def _matches_any(patterns: list[str], normalized: str) -> bool:
    return any(re.search(pattern, normalized) for pattern in patterns)


def classify_query(question: str) -> str:
    normalized = " ".join(question.lower().split())
    if not normalized:
        return OUT_OF_SCOPE
    if _matches_any(_RATING_PATTERNS, normalized) and _matches_any(_REVIEW_PATTERNS, normalized):
        return REVIEW_RATING
    if _matches_any(_REVIEW_PATTERNS, normalized):
        return REVIEW_FEEDBACK
    return OUT_OF_SCOPE


def is_review_question(question: str) -> bool:
    return classify_query(question) != OUT_OF_SCOPE


def is_rating_query(question: str) -> bool:
    return classify_query(question) == REVIEW_RATING


def rating_sort_direction(question: str) -> str:
    normalized = " ".join(question.lower().split())
    return "asc" if _matches_any(_ASC_RATING_PATTERNS, normalized) else "desc"
