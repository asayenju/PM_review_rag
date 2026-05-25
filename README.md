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
