from app.core.config import settings
from app.services.review_ingestion import _chunk_text


def test_chunk_text_returns_empty_for_blank_text():
    assert _chunk_text(" \n\t ") == []


def test_chunk_text_preserves_short_review_text():
    chunks = _chunk_text(
        "The checkout flow is clear and fast. Users are confused about coupons, "
        "but mobile carts reset during checkout."
    )

    assert chunks == [
        "The checkout flow is clear and fast. Users are confused about coupons, "
        "but mobile carts reset during checkout."
    ]


def test_chunk_text_splits_long_review_with_configured_size_limit():
    text = " ".join(f"sentence-{index:03d}" for index in range(220))

    chunks = _chunk_text(text)

    assert len(chunks) > 1
    assert all(len(chunk) <= settings.chunk_size_chars for chunk in chunks)


def test_chunk_text_overlaps_adjacent_long_chunks():
    text = " ".join(f"sentence-{index:03d}" for index in range(220))

    chunks = _chunk_text(text)

    first_tokens = chunks[0].split()
    second_tokens = chunks[1].split()
    assert set(first_tokens[-20:]) & set(second_tokens[:20])
