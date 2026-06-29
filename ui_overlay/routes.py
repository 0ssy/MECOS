"""
UI Overlay FastAPI Routes
Extends the existing dashboard server with overlay endpoints.
Provides transcript SSE, suggestion endpoint, and settings toggle.
"""

from __future__ import annotations

import json
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

from loguru import logger


router = APIRouter(prefix="/api/overlay")

overlay_state = {
    "visible": False,
    "transcript": [],
    "suggestion": None,
    "code": None,
    "meeting_active": False,
}


class OverlayStatus(BaseModel):
    visible: bool = False
    meeting_active: bool = False
    transcript_length: int = 0
    last_transcript: Optional[str] = None
    suggestion: Optional[str] = None


@router.get("/")
async def overlay_index():
    html_path = Path(__file__).parent / "templates" / "overlay.html"
    if html_path.exists():
        html = html_path.read_text(encoding="utf-8")
        return HTMLResponse(content=html)
    return HTMLResponse(content="<h1>Overlay not configured</h1>")


@router.get("/status")
async def overlay_status():
    return OverlayStatus(
        visible=overlay_state["visible"],
        meeting_active=overlay_state["meeting_active"],
        transcript_length=len(overlay_state["transcript"]),
        last_transcript=overlay_state["transcript"][-1] if overlay_state["transcript"] else None,
        suggestion=overlay_state["suggestion"],
    )


@router.post("/toggle")
async def overlay_toggle(visible: bool = True):
    overlay_state["visible"] = visible
    return {"visible": overlay_state["visible"], "timestamp": datetime.utcnow().isoformat()}


@router.post("/hide")
async def overlay_hide():
    overlay_state["visible"] = False
    return {"visible": False, "timestamp": datetime.utcnow().isoformat()}


@router.get("/transcript")
async def overlay_transcript():
    async def event_stream():
        last_idx = 0
        while True:
            while last_idx < len(overlay_state["transcript"]):
                yield f"data: {json.dumps({'transcript': overlay_state['transcript'][last_idx]})}\n\n"
                last_idx += 1
            await asyncio.sleep(0.1)
    return StreamingResponse(event_stream(), media_type="text/event-stream")


def add_transcript_segment(text: str):
    if text:
        overlay_state["transcript"].append(text)
        if len(overlay_state["transcript"]) > 100:
            overlay_state["transcript"] = overlay_state["transcript"][-100:]


def set_suggestion(text: str):
    overlay_state["suggestion"] = text


def set_code(text: str):
    overlay_state["code"] = text


def set_meeting_active(active: bool):
    overlay_state["meeting_active"] = active
    if active:
        overlay_state["visible"] = True


def get_router():
    return router