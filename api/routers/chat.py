import os
from typing import Generator

import ollama
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from api.deps import get_current_user

router = APIRouter(tags=["chat"])

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
MODEL_NAME = os.environ.get("MODEL_NAME", "gemma4:e2b")


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = []


def _token_stream(messages: list[dict]) -> Generator[str, None, None]:
    client = ollama.Client(host=os.environ.get("OLLAMA_HOST", "http://localhost:11434"))
    model = os.environ.get("MODEL_NAME", "gemma4:e2b")
    try:
        stream = client.chat(model=model, messages=messages, stream=True)
        for chunk in stream:
            token = chunk["message"]["content"]
            if token:
                yield f"data: {token}\n\n"
    except Exception as e:
        yield f"data: [ERROR] {e}\n\n"


@router.post("/")
def chat(body: ChatRequest, _user: dict = Depends(get_current_user)):
    messages = [{"role": m.role, "content": m.content} for m in body.history]
    messages.append({"role": "user", "content": body.message})
    return StreamingResponse(
        _token_stream(messages),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
