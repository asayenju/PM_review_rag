from fastapi import FastAPI

app = FastAPI(title="Startup Backend")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/message")
def message():
    return {"message": "Backend Ready"}
