# Public Review Chat Implementation

This document explains the public review chat that was added to the PM Review RAG project.

## What Was Built

The app now has a public chat experience at:

```bash
http://127.0.0.1:3000/demo
```

Anyone can ask questions about a public set of customer reviews. The public chat is intentionally separate from the authenticated PM query flow.

There are now two query paths:

- `POST /api/query`
  - Authenticated PM flow.
  - Requires bearer auth.
  - Checks feature assignment before retrieval.

- `POST /api/public/query`
  - Public review chat flow.
  - Does not require login.
  - Only searches backend-controlled public review data.
  - Does not accept `org_id` or `feature_id` from the browser.

## Backend Flow

The public endpoint is defined in:

```bash
backend/app/api/public.py
```

Request:

```json
{
  "question": "What should we improve first?"
}
```

Response:

```json
{
  "answer": "We should improve providing better status updates during the order placement first."
}
```

The endpoint calls:

```bash
backend/app/services/public_query.py
```

That service does four things:

1. Ensures the public demo organization exists.
2. Ensures the public demo feature exists.
3. Seeds public reviews if they are missing.
4. Embeds the question, retrieves matching chunks, and asks the LLM to answer from that context.

The public reviews are hardcoded in `public_query.py` for the demo. They are inserted through the existing ingestion path, so they still become normal `reviews` and `review_chunks` rows.

## Public Data Scope

The browser never chooses the organization or feature for public chat.

The backend always uses these config values from:

```bash
backend/app/core/config.py
```

```python
public_review_org_slug = "public-review-demo"
public_review_org_name = "Public Review Demo"
public_review_feature_slug = "public-checkout-experience"
public_review_feature_name = "Public Checkout Experience"
```

This keeps public chat scoped to one known public review dataset.

## Retrieval

The project originally planned to use a Supabase RPC function named `match_review_chunks`.

For local reliability, the current implementation does not require that RPC. Instead:

1. The backend fetches recent chunks for the configured public feature from `review_chunks`.
2. It parses stored vectors.
3. It computes cosine similarity in Python.
4. It returns the top matching chunks.

That logic lives in:

```bash
backend/app/services/vector_store.py
```

The main helper is:

```python
match_review_chunks(...)
```

This is simpler for local development. Later, you can move matching back into Postgres/pgvector for better production performance.

## LLM Answering

Answer generation is handled in:

```bash
backend/app/services/openai_answers.py
```

The model is instructed to answer only from supplied customer review context. If the context is not enough, it should politely decline.

The answer token budget is configured in:

```python
query_max_output_tokens = 180
```

This keeps public responses short and cheap.

## Frontend Flow

The public chat UI is implemented in:

```bash
frontend/app/demo/page.js
```

It includes:

- message bubbles
- assistant welcome message
- example prompt buttons
- loading state
- error state
- disabled empty submit
- 5-question limit

The frontend API helper is in:

```bash
frontend/lib/api.js
```

The public chat calls:

```javascript
publicQuery(question)
```

which sends:

```javascript
POST /api/public/query
```

## 5-Question Limit

The public demo has a browser-side limit of 5 successful questions.

It uses:

```javascript
localStorage
```

with this key:

```javascript
publicReviewQueryCount
```

This is enough for a demo, but it is not abuse-proof. A user can reset it by clearing browser storage or using another browser.

For production, move the limit server-side with either:

- anonymous session IDs
- IP-based rate limiting
- authenticated accounts
- Supabase table-backed usage tracking

## Local Run Steps

Start the backend:

```bash
.venv/bin/uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 4000
```

Start the frontend:

```bash
cd frontend
npm run dev
```

Open:

```bash
http://127.0.0.1:3000/demo
```

## Environment Variables

The backend still needs:

```bash
SUPABASE_URL=...
SUPABASE_ANON_KEY=...
SUPABASE_SERVICE_ROLE_KEY=...
OPENAI_API_KEY=...
```

The public chat uses the same OpenAI embedding and answer model config as the rest of the backend.

## Tests

Backend tests were added for the public query path:

```bash
backend/tests/test_public_query.py
```

Run all backend tests:

```bash
PYTHONPATH=backend .venv/bin/python -m pytest backend/tests
```

Current expected result:

```bash
7 passed
```

Build the frontend:

```bash
cd frontend
npm run build
```

## Files Added Or Updated

Backend:

- `backend/app/api/public.py`
- `backend/app/api/query.py`
- `backend/app/schemas/query.py`
- `backend/app/services/public_query.py`
- `backend/app/services/query_processing.py`
- `backend/app/services/openai_answers.py`
- `backend/app/services/vector_store.py`
- `backend/app/core/config.py`
- `backend/app/main.py`
- `backend/tests/test_public_query.py`
- `backend/tests/test_query_processing.py`

Frontend:

- `frontend/app/demo/page.js`
- `frontend/lib/api.js`

## Important Design Choice

The public chat and PM chat are intentionally separate.

Public chat:

- no login
- public review data only
- frontend-enforced 5-question limit

PM chat:

- login required
- feature assignment required
- private org/feature-scoped retrieval

This separation keeps the demo easy to use without weakening the authorization rules for the real PM workflow.
