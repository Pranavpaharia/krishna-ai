"""FastAPI app: /health, /chat, and the static chat page (Task 13).

Run:  python -m krsna_ai.app   (serves http://127.0.0.1:8123; override with KRSNA_PORT)
"""
from __future__ import annotations

from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from krsna_ai.core import audit
from krsna_ai.core.engine import answer_question
from krsna_ai.core.llm import GatewayError
from krsna_ai.core.store import Store

WEB_INDEX = Path(__file__).resolve().parent / "web" / "index.html"

app = FastAPI(title="Krishna AI Assistant")
_store: Store | None = None


def get_store() -> Store:
    global _store
    if _store is None:
        _store = Store.load()
    return _store


class HistoryItem(BaseModel):
    role: str
    content: str = Field(max_length=4000)


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    history: list[HistoryItem] = Field(default_factory=list, max_length=12)


@app.get("/health")
async def health() -> dict:
    store = get_store()
    return {"status": "ok", "verses": len(store.records)}


@app.post("/chat")
async def chat(req: ChatRequest) -> dict:
    history = [item.model_dump() for item in req.history]
    try:
        return await answer_question(get_store(), req.question, history=history)
    except GatewayError as exc:
        # answer_question audits only after a successful call, so a gateway failure would
        # otherwise leave no trace in the log — which is why this one was hard to see.
        audit.record({"question": req.question, "error": str(exc)})
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/verse/{verse_id}")
async def verse(verse_id: str) -> dict:
    """Return one stored verse for the UI's clickable reference cards."""
    rec = get_store().get(verse_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="Verse not found")
    return {
        "id": rec["id"],
        "book": rec["book"],
        "chapter": rec["chapter"],
        "verse": rec["verse"],
        "ref": rec["ref"],
        "chapter_title": rec.get("chapter_title", ""),
        "transliteration": rec.get("transliteration", ""),
        "translation": rec["translation"],
        "purport": rec.get("purport", ""),
        "pdf_page": rec["pdf_page"],
        "quality": rec.get("quality", ""),
    }


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(WEB_INDEX)


if __name__ == "__main__":
    import os

    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("KRSNA_PORT", "8123")))
