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

That service does five things:

1. Ensures the public demo organization exists.
2. Ensures the public demo feature exists.
3. Seeds public reviews if they are missing.
4. Classifies the question before retrieval.
5. Retrieves the right review context and asks the LLM to answer from that context.

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

Retrieval is the part of RAG that decides which review evidence the LLM is allowed to see.

The important idea is:

```text
The LLM does not search the database.
The backend searches first, builds a small evidence packet, then sends only that packet to the LLM.
```

### Ingestion-Time Embeddings

When a review is created through `POST /api/reviews`, the backend:

1. Saves a row in `reviews`.
2. Splits the review body into smaller text chunks.
3. Sends each chunk to the OpenAI embeddings API.
4. Stores each chunk in `review_chunks` with:
   - `review_id`
   - `org_id`
   - `feature_id`
   - `chunk_text`
   - `embedding`
   - chunk metadata like model and dimensions

The embedding is just a vector representation of the chunk. It is useful for similarity search, but it is not human-readable context and should not be sent to the LLM.

### Query-Time Routing

Before doing embeddings or retrieval, the backend classifies the user question in:

```bash
backend/app/services/query_guardrails.py
```

There are three query categories:

- `review_feedback`
  - Example: "What are customers complaining about?"
  - Uses vector search over review chunks.

- `review_rating`
  - Example: "What is the worst rating review?"
  - Uses structured review lookup ordered by rating.

- `out_of_scope`
  - Example: "What is the weather today?"
  - Returns a polite refusal before embeddings, retrieval, or LLM answering.

This matters because not every question should use vector search. Rating questions are better answered from structured metadata like `reviews.rating`.

### Vector Search For Feedback Questions

For normal review-feedback questions, the backend:

1. Fetches recent chunks for the configured public feature from `review_chunks`.
2. It embeds the current user question.
3. It parses the stored chunk vectors.
4. It computes cosine similarity between the question vector and each chunk vector.
5. It sorts chunks by similarity.
6. It keeps the top matches.
7. It fetches review metadata for those matched chunks.

The current local implementation computes similarity in Python inside:

```bash
backend/app/services/vector_store.py
```

The main helper is:

```python
match_review_chunks(...)
```

For each matched chunk, the backend enriches the context with review metadata:

- title
- rating
- reviewer name
- reviewed date
- chunk text

That means the LLM sees evidence like:

```text
- Title: Payment Failure Confusion | Rating: 2/10 | Reviewer: Morgan Tester | Review excerpt: payment fails customers cannot tell whether card billing address network merchant processor caused failure
```

The project originally planned to use a Supabase RPC function named `match_review_chunks`. For local reliability, the current implementation does not require that RPC. Later, you can move matching back into Postgres/pgvector for better production performance.

### Structured Lookup For Rating Questions

For rating/ranking questions, the backend does not use vector search.

Instead, it queries the `reviews` table directly:

```text
lowest/worst rating  -> order by rating asc
highest/best rating  -> order by rating desc
```

This is why a question like:

```text
What is the worst rating review?
```

can correctly answer from `reviews.rating`, `reviews.title`, and `reviews.body`.

This avoids a common RAG mistake: trying to answer structured data questions using only semantic chunk similarity.

## What The LLM Sees

```bash
backend/app/services/openai_answers.py
```

The final prompt input is built by:

```python
build_answer_input(...)
```

The LLM receives three possible pieces of text:

1. Conversation history, if this is the authenticated PM chat.
2. The current user question.
3. Retrieved review context.

For public chat, there is no conversation history. The shape is:

```text
Question:
What should we improve first?

Review context:
- Title: ... | Rating: ... | Review excerpt: ...
- Title: ... | Rating: ... | Review excerpt: ...
```

For authenticated PM chat, the shape can include history:

```text
Conversation history:
PM: What are customers complaining about?
Assistant: Customers mention coupon errors and mobile cart resets.

Question:
Which issue should we prioritize?

Review context:
- Title: ... | Rating: ... | Review excerpt: ...
```

The LLM does not receive:

- raw embeddings
- full database rows
- every review in the database
- chunks from unassigned/private features
- unrelated external information

The model is instructed to answer only from supplied customer review context. If the context is not enough, or the question is outside the review scope, it should politely decline.

The answer-input limits are configured in:

```python
query_max_context_chars = 3000
query_max_history_chars = 2000
query_max_question_chars = 1000
query_max_output_tokens = 180
```

This keeps the prompt small and prevents accidentally sending huge context to the LLM.

## Why This Design Works

This design separates the responsibilities clearly:

- Guardrails decide whether the question is allowed.
- Retrieval decides which review evidence is relevant.
- Structured lookup handles rating/ranking questions.
- The LLM explains the answer using only bounded review context.

For example:

```text
What is the weather today?
```

This is blocked before embeddings or retrieval.

```text
What are customers complaining about?
```

This uses vector search over `review_chunks`.

```text
What is the worst rating review?
```

This uses the structured `reviews.rating` field, not vector search.

That hybrid approach is better than pure vector search because product review questions often mix semantic questions and structured metadata questions.

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
19 passed
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
- `backend/app/services/query_guardrails.py`
- `backend/app/services/review_context.py`
- `backend/app/core/config.py`
- `backend/app/main.py`
- `backend/tests/test_public_query.py`
- `backend/tests/test_query_processing.py`
- `backend/tests/test_query_guardrails.py`
- `backend/tests/test_openai_answers.py`

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
