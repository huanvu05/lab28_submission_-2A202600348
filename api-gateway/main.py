# api-gateway/main.py
from fastapi import FastAPI, Request
from pydantic import BaseModel
from prometheus_fastapi_instrumentator import Instrumentator
import httpx, os, time

app = FastAPI(title="AI Platform API Gateway")
Instrumentator().instrument(app).expose(app)

VLLM_URL = os.environ["VLLM_URL"]
QDRANT_URL = os.environ.get("QDRANT_URL", "http://qdrant:6333")

class ChatRequest(BaseModel):
    query: str
    embedding: list[float] = [0.0] * 384

@app.post("/api/v1/chat")
async def chat(request: ChatRequest):
    start = time.time()

    # 1. Vector search
    context = []
    try:
        async with httpx.AsyncClient() as client:
            search_resp = await client.post(
                f"{QDRANT_URL}/collections/documents/points/search",
                json={"vector": request.embedding, "limit": 3},
                timeout=5
            )
            if search_resp.status_code == 200:
                context = search_resp.json().get("result", [])
    except Exception:
        pass  # Graceful degradation if Qdrant unavailable

    # 2. LLM inference
    prompt = f"Context: {context}\n\nQuery: {request.query}"
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            llm_resp = await client.post(f"{VLLM_URL}/v1/chat/completions", json={
                "model": "Qwen/Qwen2.5-7B-Instruct-GPTQ-Int4",
                "messages": [{"role": "user", "content": prompt}]
            })
        result = llm_resp.json()
        answer = result["choices"][0]["message"]["content"]
        model = result["model"]
    except Exception:
        answer = "LLM service unavailable"
        model = "fallback"

    latency = (time.time() - start) * 1000
    return {
        "answer": answer,
        "latency_ms": round(latency, 2),
        "model": model
    }

@app.get("/health")
def health():
    return {"status": "ok"}
