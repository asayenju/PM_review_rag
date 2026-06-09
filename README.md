# PM Review RAG

PM Review RAG is a FastAPI + Next.js application for asking product-manager questions over customer reviews. The backend stores reviews in Supabase, chunks and embeds review text with OpenAI embeddings, retrieves feature-scoped review evidence, and generates concise answers with source labels.

## Project Structure

```text
frontend/                 Next.js app
backend/                  FastAPI app
backend/app/api/          HTTP routes
backend/app/services/     RAG, ingestion, OpenAI, Supabase, and conversation logic
backend/app/schemas/      Pydantic request/response models
backend/scripts/          Evaluation harness for retrieval and generation quality
backend/tests/            Backend unit tests
```

The main RAG files are:

- `backend/app/services/review_ingestion.py`: turns review bodies into searchable chunks and stores embeddings.
- `backend/app/services/vector_store.py`: reads/writes Supabase tables and ranks chunks by cosine similarity.
- `backend/app/services/query_processing.py`: enforces access, routes question types, retrieves context, and calls generation.
- `backend/app/services/review_context.py`: formats retrieved chunks or rating-selected reviews into source strings.
- `backend/app/services/openai_answers.py`: builds the LLM input and calls the OpenAI Responses API.
- `backend/scripts/evaluate_retrieval.py`: seeds synthetic reviews, runs API questions, and reports retrieval + generation metrics.

## Local Setup

### Backend

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload --host 0.0.0.0 --port 4000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The frontend defaults to the local backend on port `4000`.

## Backend Environment

Create `backend/.env`:

```bash
SUPABASE_URL=...
SUPABASE_ANON_KEY=...
SUPABASE_SERVICE_ROLE_KEY=...
OPENAI_API_KEY=...

OPENAI_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_QUERY_MODEL=gpt-4.1-mini
EMBEDDING_DIMENSIONS=1536

QUERY_MATCH_COUNT=8
QUERY_SCAN_LIMIT=200
QUERY_MIN_SIMILARITY=0.25
QUERY_MAX_CONTEXT_CHARS=3000
QUERY_MAX_HISTORY_CHARS=2000
QUERY_MAX_QUESTION_CHARS=1000
QUERY_MAX_OUTPUT_TOKENS=180

DEMO_FEATURE_SLUG=default-demo-feature
DEMO_FEATURE_NAME=Default Demo Feature
DEMO_REVIEW_TITLE=Default Shared Demo Review

PUBLIC_REVIEW_ORG_SLUG=public-review-demo
PUBLIC_REVIEW_ORG_NAME=Public Review Demo
PUBLIC_REVIEW_FEATURE_SLUG=public-checkout-experience
PUBLIC_REVIEW_FEATURE_NAME=Public Checkout Experience

API_PORT=4000
CORS_ORIGINS=http://localhost:3000
```

The defaults live in `backend/app/core/config.py`.

## Supabase Setup

The app expects tables for organizations, features, PM feature assignments, reviews, and review chunks. Review chunks store vectors in a pgvector column.

Run once in the Supabase SQL editor:

```sql
create extension if not exists vector;

alter table public.review_chunks
  add column if not exists embedding vector(1536);

create index if not exists review_chunks_embedding_hnsw_idx
  on public.review_chunks
  using hnsw (embedding vector_cosine_ops);
```

Current retrieval fetches up to `QUERY_SCAN_LIMIT` chunk rows for the selected org and feature, parses the stored vectors in Python, and computes cosine similarity in application code. The pgvector index is still useful if retrieval is later moved into SQL/RPC.

## Core API Endpoints

All authenticated write/query endpoints require:

```http
Authorization: Bearer <supabase_access_token>
```

Important endpoints:

- `POST /api/auth/signup`: create a Supabase user.
- `POST /api/auth/login`: log in and receive an access token.
- `GET /api/me/features`: list features assigned to the current PM.
- `POST /api/reviews`: create a review and immediately run chunking + embedding.
- `POST /api/reviews/{review_id}/chunk`: reprocess chunks and embeddings for an existing review.
- `POST /api/query`: ask a question for a specific `org_id` and `feature_id`.
- `POST /api/conversations/{conversation_id}/messages`: ask with conversation history.
- `POST /api/demo/seed-default-review`: seed a shared demo review.
- `POST /query`: public demo query endpoint backed by seeded public reviews.

Example query:

```bash
curl -sS -X POST http://127.0.0.1:4000/api/query \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "org_id": "ORG_ID",
    "feature_id": "FEATURE_ID",
    "question": "What pricing concerns are customers raising?"
  }'
```

## Review Ingestion

Review ingestion starts in `create_review_and_process` in `review_ingestion.py`.

1. The API inserts a row in `reviews` with status `pending`.
2. `process_review_chunks` changes the status to `chunking`.
3. The review body is normalized into a single-space string.
4. `_chunk_text` uses LangChain's `RecursiveCharacterTextSplitter`.
5. The splitter uses the configured `CHUNK_SIZE_CHARS` and `CHUNK_OVERLAP_CHARS` values.
6. Existing chunks for the review are deleted.
7. The review status changes to `embedding`.
8. `embed_texts` sends every chunk to OpenAI embeddings.
9. Each chunk is inserted into `review_chunks` with:
   - `review_id`
   - `org_id`
   - `feature_id`
   - `chunk_text`
   - `chunk_index`
   - `embedding_model`
   - `dimensions`
   - `embedding`
10. The review status changes to `ready`.

If any step fails, the review status becomes `failed` and the exception is raised.

### Why The Chunks Preserve Review Text

The code stores full review-text chunks instead of compact keyword-only chunks. For example, a sentence like:

```text
Customers say the pricing page hides seat limits and add-on costs until checkout.
```

stays available to retrieval and generation as natural-language evidence:

```text
Customers say the pricing page hides seat limits and add-on costs until checkout.
```

This gives generation more complete evidence snippets while keeping chunk size and overlap controlled by config. For rating queries, the app still uses full review bodies instead of semantic chunks.

## Embeddings

`backend/app/services/openai_embeddings.py` wraps OpenAI embeddings:

```python
response = await client.embeddings.create(
    model=settings.openai_embedding_model,
    input=texts,
)
```

The default embedding model is `text-embedding-3-small`, and the configured dimension is `1536`. The code warns if returned vectors do not match `EMBEDDING_DIMENSIONS`.

Embeddings are stored in Supabase as vector literals such as:

```text
[0.01234567,-0.02345678,...]
```

## Retrieval Flow

Retrieval starts in `generate_feature_answer` in `query_processing.py`.

1. The user profile id is read from the authenticated user.
2. `has_feature_assignment` checks that the PM is assigned to the requested `org_id` and `feature_id`.
3. `classify_query` routes the question into one of three intents:
   - `out_of_scope`
   - `review_rating`
   - `review_feedback`
4. Out-of-scope questions return a fixed refusal before embedding or retrieval.
5. Rating questions use `list_reviews_for_feature` sorted by rating.
6. Normal review-feedback questions embed the question and call `match_review_chunks`.

### Standard Semantic Retrieval

For normal review-feedback questions:

1. The question is embedded with `embed_texts([question])`.
2. `match_review_chunks` loads chunks for the selected org and feature.
3. Each stored vector is parsed back into floats.
4. Cosine similarity is calculated between the question vector and each chunk vector.
5. Matches are sorted descending by similarity.
6. The top `QUERY_MATCH_COUNT` matches are kept. The current default is `8`.
7. Review metadata is attached to each match:
   - title
   - rating
   - reviewer name
   - reviewed date
8. `generate_feature_answer` filters out weak matches below `QUERY_MIN_SIMILARITY`.
9. If no strong matches remain, the answer is:

```text
I do not have enough review evidence for that feature yet.
```

### Rating Retrieval

Questions containing terms like `worst`, `best`, `rating`, `lowest`, or `highest` are routed to `REVIEW_RATING`.

Instead of embedding the question, the backend calls `list_reviews_for_feature`:

- worst/lowest/bad queries sort ratings ascending
- best/highest queries sort ratings descending

Then it builds context from full review bodies.

### Guardrails

`query_guardrails.py` blocks obvious unrelated questions such as weather, sports, stocks, recipes, flights, and capitals. These are refused before embedding, retrieval, or generation.

The LLM prompt also tells the model to refuse questions that are outside the assigned feature, outside customer review feedback, ask for private data, or cannot be answered from the supplied context.

## Context Construction

`review_context.py` formats retrieved evidence as a list of strings. This is important: generation receives chunks as `list[str]`, not one giant context string.

For semantic retrieval, `build_chunk_context` creates entries like:

```text
- Title: Retrieval Eval 01 - Pricing | Rating: 7/10 | Reviewer: Eval Reviewer 01 | Reviewed at: 2026-05-01T00:00:00Z | Review excerpt: pricing page hides seat limits add-on costs checkout
```

For rating queries, `build_review_context` creates entries with full review bodies:

```text
- Title: Buggy Checkout | Rating: 2/10 | Reviewer: PM Customer | Reviewed at: 2026-05-27T00:00:00Z | Review body: Checkout failed twice with no clear error.
```

Both builders enforce the global `QUERY_MAX_CONTEXT_CHARS` budget.

## LLM Generation

Generation lives in `openai_answers.py`.

`build_answer_input` receives:

- `question: str`
- `chunks: list[str]`
- optional `history: str`

It clamps:

- question length to `QUERY_MAX_QUESTION_CHARS`
- history length to `QUERY_MAX_HISTORY_CHARS`
- context length to `QUERY_MAX_CONTEXT_CHARS`

Then it formats the chunks as source-labelled context:

```text
Question:
What pricing concerns are customers raising?

Review context:
[Source 1]
- Title: ... | Review excerpt: ...

[Source 2]
- Title: ... | Review excerpt: ...
```

The source labels are generated at answer-input time from the chunk order. They are not database ids; `[Source 1]` means the first chunk passed to the model for that answer.

`answer_from_review_context` calls the OpenAI Responses API:

```python
response = await client.responses.create(
    model=settings.openai_query_model,
    instructions=...,
    input=build_answer_input(question, chunks, history),
    max_output_tokens=settings.query_max_output_tokens,
)
```

The default query model is `gpt-4.1-mini`.

The instructions tell the model to:

- answer only from supplied customer review context
- consider all context chunks before answering
- be concise and specific
- cite factual review-backed claims with source labels like `[Source 1]`
- refuse out-of-scope or unsupported questions in one sentence

The endpoint returns only the stripped `response.output_text`.

## Conversations

Conversation messages use the same RAG path as one-off queries. `conversations.py` collects recent conversation history and passes it into `generate_feature_answer`.

The generation input includes history before the question:

```text
Conversation history:
PM: Earlier question
Assistant: Earlier answer

Question:
Follow up?

Review context:
[Source 1]
...
```

The history helps with follow-up questions, but retrieval is still performed against the current question.

## Public Demo Query Flow

`public_query.py` seeds a small public demo dataset for checkout-related feedback. It uses the same ingestion, retrieval, context building, and generation functions as the authenticated flow, but it is scoped to configured public org/feature slugs.

The public endpoint is useful for demos because it does not require creating a private PM feature assignment first.

## Evaluation Harness

The main eval script is:

```bash
PYTHONPATH=backend .venv/bin/python backend/scripts/evaluate_retrieval.py \
  --api-base http://127.0.0.1:4000 \
  --output /tmp/pm_rag_eval_results_generation.json
```

It does four things:

1. Creates or logs in as a fixed eval PM user.
2. Creates or reuses an eval organization and feature.
3. Seeds 50 synthetic PM reviews across themes:
   - pricing
   - onboarding
   - integrations
   - reporting
   - performance
   - permissions
   - mobile
   - notifications
   - billing
   - collaboration
4. Asks 15 questions through the live `/api/query` endpoint.

The eval reuses existing synthetic reviews by title unless `--force-post` is passed.

### Retrieval Metrics

The retrieval metrics are computed at review id level:

- `recall`: fraction of relevant review ids retrieved.
- `mean_average_precision`: average precision across answerable questions.
- `mrr`: reciprocal rank of the first relevant retrieved review.
- `freshness_rank`: rank of the newest relevant review. `0` means it was not retrieved.
- `source_diversity`: number of unique retrieved review ids.
- `hit_rate`: fraction of answerable questions with at least one relevant retrieved review.

### Generation Metrics

The script can also use the LLM as a judge. For each generated answer, it sends:

- question id
- question text
- whether the question is answerable
- generated answer
- retrieved context
- expected facts
- scoring rubric

The judge returns scores from 1 to 5:

- `faithfulness`: whether material claims are supported by retrieved context.
- `answer_relevance`: whether the answer directly addresses the question.
- `completeness`: whether the answer covers expected facts or refuses unanswerable questions.
- `conciseness`: whether the answer avoids padding and repetition.
- `overall`: mean of the four generation scores.

Use `--skip-generation-eval` to run retrieval-only evaluation.

### Source Usage Reporting

The eval report tracks source usage in two ways:

- `source_usage.cited_source_ranks`: source labels explicitly cited in the generated answer, such as `[Source 3]`.
- `source_usage.judged_used_source_ranks`: source ranks that the LLM judge believes materially support the answer.
- `source_usage.judged_used_sources`: full metadata for those judged-used sources.

This helps distinguish two problems:

- the answer used evidence but failed to cite it
- the answer cited or used the wrong evidence

### Low-Scoring Question Report

The report also includes `low_scoring_questions`. A question is listed when:

- answerable retrieval `recall` is below `0.75`
- answerable retrieval MAP is below `0.75`
- any generation score is `3` or lower

Each low-scoring entry includes:

- question id and text
- reasons
- retrieval metric details
- generation scores
- judged-used source ranks
- cited source ranks
- generated answer

## Running Tests

```bash
PYTHONPATH=backend .venv/bin/pytest backend/tests
```

The tests cover:

- query guardrails
- answer input formatting
- retrieval/generation eval helpers
- query processing behavior
- public query behavior
- review ingestion behavior
- conversation history wiring

## Current Design Tradeoffs

- Retrieval is feature-scoped and access-controlled before embeddings are generated.
- Semantic retrieval currently computes cosine similarity in Python over up to `QUERY_SCAN_LIMIT` chunks. This is simple and testable, but a SQL/RPC pgvector search would scale better.
- Chunk text preserves natural-language review evidence, which gives generation more detail than keyword-only chunks.
- Rating questions bypass embeddings and use structured review sorting.
- Source labels are generated per answer from retrieved chunk order. They are stable inside one answer but not globally stable ids.
- LLM generation is instructed to cite sources, and eval reports when citations are missing or sources differ from judge-detected usage.

## Useful Commands

Run backend:

```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 4000
```

Run tests:

```bash
PYTHONPATH=backend .venv/bin/pytest backend/tests
```

Run full RAG eval:

```bash
PYTHONPATH=backend .venv/bin/python backend/scripts/evaluate_retrieval.py \
  --api-base http://127.0.0.1:4000 \
  --output /tmp/pm_rag_eval_results_generation.json
```

Run retrieval-only eval:

```bash
PYTHONPATH=backend .venv/bin/python backend/scripts/evaluate_retrieval.py \
  --api-base http://127.0.0.1:4000 \
  --skip-generation-eval \
  --output /tmp/pm_rag_eval_results_retrieval_only.json
```
