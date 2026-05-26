# PM Review RAG

## Project Structure
- `frontend`: Next.js app
- `backend`: FastAPI app

## Run Frontend
```bash
cd frontend
npm install
npm run dev
```

## Run Backend
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload --host 0.0.0.0 --port 4000
```

## Backend Environment (`backend/.env`)
Add these variables for review ingestion + embeddings:

```bash
SUPABASE_URL=...
SUPABASE_ANON_KEY=...
SUPABASE_SERVICE_ROLE_KEY=...
OPENAI_API_KEY=...
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSIONS=1536
CHUNK_SIZE_CHARS=900
CHUNK_OVERLAP_CHARS=150
DEMO_FEATURE_SLUG=default-demo-feature
DEMO_FEATURE_NAME=Default Demo Feature
DEMO_REVIEW_TITLE=Default Shared Demo Review
```

## Supabase pgvector Setup (run once in SQL editor)
```sql
create extension if not exists vector;

alter table public.review_chunks
  add column if not exists embedding vector(1536);

create index if not exists review_chunks_embedding_hnsw_idx
  on public.review_chunks
  using hnsw (embedding vector_cosine_ops);
```

## New APIs
- `POST /api/reviews` creates a review and runs chunking + embedding + vector insert.
- `POST /api/reviews/{review_id}/chunk` reprocesses chunks/embeddings for an existing review.
- `POST /api/demo/seed-default-review` seeds one shared default demo review.

All write endpoints require `Authorization: Bearer <supabase_access_token>`.

### Quick demo seed test
```bash
TOKEN="<your-supabase-access-token>"
ORG_ID="<existing-org-id>"

curl -sS -X POST http://127.0.0.1:4000/api/demo/seed-default-review \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d "{\"org_id\":\"$ORG_ID\"}"
```
