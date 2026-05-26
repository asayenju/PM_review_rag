# Backend Guide: What Was Added and Why

This file explains the recent backend implementation for:
- review ingestion APIs
- text chunking
- OpenAI embeddings
- Supabase pgvector storage
- demo seed flow

The goal is to help you study the architecture and rebuild it yourself.

## 1) High-Level Architecture

Flow:
1. Client calls API endpoint (`/api/reviews` or `/api/demo/seed-default-review`).
2. API verifies bearer token via Supabase Auth.
3. Backend inserts a `reviews` row with status `pending`.
4. Backend chunks review text.
5. Backend requests embeddings from OpenAI.
6. Backend stores chunk rows in `review_chunks` (including vector + metadata).
7. Review status is updated to `ready` (or `failed` on error).

Main layers:
- `api/`: HTTP routes + dependency injection
- `schemas/`: request/response contracts
- `services/`: business logic and external integrations
- `core/config.py`: environment settings

## 2) New Files and Their Purpose

### API layer

- `app/api/dependencies.py`
  - Adds `require_authenticated_user`.
  - Reads `Authorization: Bearer <token>`.
  - Calls Supabase `/auth/v1/user` to validate token.

- `app/api/reviews.py`
  - Adds 3 endpoints:
    - `POST /api/reviews`
    - `POST /api/reviews/{review_id}/chunk`
    - `POST /api/demo/seed-default-review`
  - Delegates real work to services.

### Schemas

- `app/schemas/reviews.py`
  - `CreateReviewRequest`
  - `CreateReviewResponse`
  - `RechunkResponse`
  - `SeedDemoRequest`
  - `SeedDemoResponse`

### Services

- `app/services/openai_embeddings.py`
  - `embed_texts(texts: list[str]) -> list[list[float]]`
  - Uses OpenAI embeddings API with model from env.

- `app/services/vector_store.py`
  - Supabase REST write/read helpers:
    - create/get review
    - update review status
    - delete old chunks for a review
    - insert chunk rows with vector literal format for pgvector
    - get/create default demo feature
    - find existing demo review

- `app/services/review_ingestion.py`
  - Orchestration logic:
    - `_chunk_text(...)` for deterministic chunking
    - `create_review_and_process(...)`
    - `process_review_chunks(review_id)`
  - Controls lifecycle status transitions.

### Existing files updated

- `app/main.py`
  - Registers the new reviews router.

- `app/core/config.py`
  - Adds env settings for:
    - OpenAI key/model
    - embedding dimensions
    - chunk size/overlap
    - demo feature/review defaults

- `app/services/supabase_auth.py`
  - Adds token validation helper `get_user_from_access_token(...)`.

- `requirements.txt`
  - Adds OpenAI SDK dependency.

## 3) API Contracts (Current)

## `POST /api/reviews`
Request body:
- `org_id` (required)
- `feature_id` (optional)
- `title` (optional)
- `body` (required)
- `reviewer_name` (optional)
- `reviewer_email` (optional)
- `rating` (optional, 1-10)

Response:
- `review_id`
- `chunk_count`
- `status`

## `POST /api/reviews/{review_id}/chunk`
Response:
- `review_id`
- `chunk_count`
- `status`

## `POST /api/demo/seed-default-review`
Request:
- `org_id` (required)
- `feature_id` (optional)

Response:
- `review_id`
- `feature_id`
- `chunk_count`
- `status`
- `created` (false when reusing existing demo review)

All endpoints above require bearer auth.

## 4) Status Lifecycle

`reviews.status` transitions:
- `pending` after initial review insert
- `chunking` before chunk generation
- `embedding` before OpenAI call
- `ready` after chunk rows are inserted
- `failed` on any exception during processing

This gives observability and retry-friendly behavior.

## 5) Chunking Strategy

Current chunker is simple and deterministic:
- Normalizes whitespace
- Splits by fixed character length (`CHUNK_SIZE_CHARS`)
- Uses overlap (`CHUNK_OVERLAP_CHARS`) to reduce boundary loss

Why this is useful for v1:
- Easy to reason about
- Stable outputs for testing
- No tokenizer dependency required initially

## 6) Vector Storage Details

`pgvector` does not create embeddings. It stores and searches vectors.

What this implementation does:
- Calls OpenAI to produce embeddings.
- Stores each chunk row with:
  - `review_id`
  - `org_id`
  - `feature_id`
  - `chunk_text`
  - `chunk_index`
  - `embedding_model`
  - `dimensions`
  - `embedding` (vector)

Important schema requirement:
- `review_chunks` must have an `embedding vector(1536)` column for `text-embedding-3-small`.

## 7) Demo Seed Behavior

`POST /api/demo/seed-default-review`:
- ensures a default feature exists (`demo_feature_slug`)
- checks whether demo review already exists
- if exists: reprocesses chunks
- if not: creates a canonical review and processes it

This is intended for repeatable demos.

## 8) Known Issues from Real Test Run

During integration testing:
1. OpenAI returned `429 insufficient_quota` (embedding API billing/quota issue).
2. Supabase table lacked `review_chunks.embedding` column in current DB.

Result:
- reviews were created and transitioned to `failed`
- no vectors were stored yet

## 9) What to Study First (Recommended)

1. `app/api/reviews.py`
   - Understand request -> service flow.
2. `app/services/review_ingestion.py`
   - Understand orchestration and status transitions.
3. `app/services/vector_store.py`
   - Understand Supabase REST interaction patterns.
4. `app/services/openai_embeddings.py`
   - Understand external model dependency boundaries.
5. `app/core/config.py`
   - Understand how env-driven behavior is configured.

## 10) If You Rebuild It Yourself

Suggested order:
1. Build `POST /api/reviews` with only review insert + status update.
2. Add chunking (no embeddings yet).
3. Add OpenAI embeddings call.
4. Add chunk insert into `review_chunks`.
5. Add `/chunk` reprocess endpoint.
6. Add demo seed endpoint.
7. Add robust error mapping and tests.

Keep each step working before moving to the next.
