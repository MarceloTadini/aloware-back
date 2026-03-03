import json
import logging
import os
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from livekit import api as lk_api

from config import read_config, write_config
from repositories import JsonAppointmentRepository

_appointments_repo = JsonAppointmentRepository()

load_dotenv()

logger = logging.getLogger("aloware.api")

app = FastAPI(title="Aloware Health — Agent Config API", version="1.0.0")

# Allow requests from the React dev server (adjust origins for production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AgentConfig(BaseModel):
    agent_name: Optional[str] = Field(None, description="Display name of the agent")
    greeting: Optional[str] = Field(None, description="First message spoken to callers")
    voice_id: Optional[str] = Field(None, description="Cartesia voice ID")
    system_prompt: Optional[str] = Field(None, description="Full system prompt with guardrails")
    enabled_tools: Optional[list[str]] = Field(
        None, description="List of tool names to expose to the LLM"
    )


@app.get("/config", response_model=dict, summary="Get current agent configuration")
async def get_config() -> dict[str, Any]:
    """Return the current contents of config.json."""
    try:
        return read_config()
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/config", response_model=dict, summary="Replace agent configuration")
async def set_config(payload: AgentConfig) -> dict[str, Any]:
    """Fully replace config.json with the provided values.

    Fields omitted from the request body are removed from the config.
    Use PATCH /config to keep existing fields.
    """
    new_config = payload.model_dump(exclude_none=True)
    if not new_config:
        raise HTTPException(status_code=422, detail="Request body must contain at least one field")
    write_config(new_config)
    return {"status": "ok", "config": new_config}


@app.patch("/config", response_model=dict, summary="Partially update agent configuration")
async def patch_config(payload: AgentConfig) -> dict[str, Any]:
    """Merge the provided fields into the existing config.json.

    Only the fields included in the request body are updated; others are preserved.
    """
    updates = payload.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=422, detail="Request body must contain at least one field")

    try:
        current = read_config()
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    current.update(updates)
    write_config(current)
    return {"status": "ok", "config": current}


@app.get("/token", summary="Generate a LiveKit JWT for browser test calls")
async def generate_token(room: str = "test-room", identity: str = "admin") -> dict[str, str]:
    """Return a short-lived LiveKit token so the React widget can join the room."""
    api_key = os.environ.get("LIVEKIT_API_KEY")
    api_secret = os.environ.get("LIVEKIT_API_SECRET")
    livekit_url = os.environ.get("LIVEKIT_URL")
    if not (api_key and api_secret and livekit_url):
        raise HTTPException(status_code=500, detail="LiveKit credentials not configured")

    token = lk_api.AccessToken(api_key=api_key, api_secret=api_secret)
    token.with_grants(lk_api.VideoGrants(room_join=True, room=room))
    token.with_identity(identity)
    token.with_room_config(
        lk_api.RoomConfiguration(
            agents=[lk_api.RoomAgentDispatch(agent_name="aloware-agent")]
        )
    )
    return {"token": token.to_jwt(), "url": livekit_url}


@app.get("/appointments", summary="List booked appointments")
async def list_appointments(date: str | None = None) -> dict[str, Any]:
    """Return all booked appointments, optionally filtered by date (YYYY-MM-DD)."""
    appointments = _appointments_repo.list_appointments(date)
    return {"appointments": appointments, "count": len(appointments)}


@app.get("/metrics", summary="Agent response latency metrics")
async def get_metrics() -> dict[str, Any]:
    """Return aggregated ping statistics written by the agent worker after each turn."""
    metrics_path = Path(__file__).parent / "metrics.json"
    if not metrics_path.exists():
        return {"message": "No calls recorded yet. Make a test call first."}
    with open(metrics_path) as f:
        return json.load(f)


@app.get("/health", summary="Health check")
async def health() -> dict[str, str]:
    return {"status": "healthy"}
