from app.services.review_ingestion import _chunk_text


def test_chunk_text_splits_sentences_and_clauses():
    chunks = _chunk_text(
        "The checkout flow is clear and fast. Users are confused about coupons, "
        "but mobile carts reset during checkout."
    )

    assert chunks == [
        "checkout flow clear fast",
        "users confused coupons",
        "mobile carts reset checkout",
    ]


def test_chunk_text_removes_low_signal_words_but_keeps_negation():
    chunks = _chunk_text("The app is not reliable and the error messages are very unclear.")

    assert chunks == ["app not reliable error messages unclear"]
