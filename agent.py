import json
import logging
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import JobContext, WorkerOptions, cli, AutoSubscribe, Agent, AgentSession
from livekit.plugins import google, silero

from config import load_config
from repositories import JsonAppointmentRepository
from tools import build_tool_registry

_repo = JsonAppointmentRepository()
ALL_TOOLS = build_tool_registry(_repo)

_METRICS_PATH = Path(__file__).parent / "metrics.json"
_ping_history: list[float] = []


def _record_ping(ping_ms: float) -> None:
    _ping_history.append(ping_ms)
    if len(_ping_history) > 1000:
        _ping_history.pop(0)

    h = sorted(_ping_history)
    n = len(h)
    stats = {
        "count": n,
        "last_ms": round(ping_ms),
        "mean_ms": round(sum(h) / n),
        "min_ms": round(h[0]),
        "max_ms": round(h[-1]),
        "p50_ms": round(h[(n - 1) // 2]),
        "p95_ms": round(h[int((n - 1) * 0.95)]),
        "last_updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    try:
        with open(_METRICS_PATH, "w") as f:
            json.dump(stats, f, indent=2)
    except OSError as e:
        logger.warning("Could not write metrics.json: %s", e)


load_dotenv(Path(__file__).parent / ".env")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("aloware.agent")


async def _handle_participant(ctx: JobContext, participant: rtc.RemoteParticipant) -> None:
    """Called every time a human participant joins — including reconnects."""
    logger.info("Participant connected: %s", participant.identity)

    config = load_config()

    agent_name = config.get("agent_name", "Agent")
    voice_id = config.get("voice_id") or "Puck"

    enabled = set(config.get("enabled_tools", []))
    active_tools = [fn for name, fn in ALL_TOOLS.items() if name in enabled]

   
    greeting = config["greeting"].replace("{{agent_name}}", agent_name)
    system_prompt = config["system_prompt"].replace("{{agent_name}}", agent_name)

    
    tool_lines = "\n".join(f"- {name}" for name in sorted(enabled)) or "- (no tools enabled)"
    system_prompt += f"\n\nACTIVE TOOLS (you may ONLY use these):\n{tool_lines}"

    disabled = set(ALL_TOOLS.keys()) - enabled
    if disabled:
        disabled_lines = "\n".join(f"- {name}" for name in sorted(disabled))
        system_prompt += (
            f"\n\nDISABLED TOOLS — these actions are NOT available in this session."
            f" Never offer, simulate, or verbally confirm them. "
            f"If asked, say the service is currently unavailable and offer an active alternative:\n{disabled_lines}"
        )

    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY is not set — check your .env file")

    assistant = Agent(instructions=system_prompt)
    await assistant.update_tools(active_tools)

    session = AgentSession(
        vad=silero.VAD.load(),
        llm=google.realtime.RealtimeModel(
            model="gemini-2.5-flash-native-audio-latest",
            voice=voice_id,
        ),
    )

    await session.start(room=ctx.room, agent=assistant)
    logger.info("Session started in room: %s", ctx.room.name)

    _t: list[float] = [0.0]

    @session.on("agent_state_changed")
    def _on_state_changed(ev) -> None:
        if ev.old_state == "listening" and ev.new_state == "thinking":
            _t[0] = time.perf_counter()
        elif ev.new_state == "speaking" and _t[0]:
            ping_ms = round((time.perf_counter() - _t[0]) * 1000)
            logger.info("PING %d ms", ping_ms)
            _record_ping(ping_ms)
            _t[0] = 0.0

    await session.generate_reply(instructions=f"Greet the user with this exact phrase: '{greeting}'")


async def entrypoint(ctx: JobContext):
    ctx.add_participant_entrypoint(_handle_participant)
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, agent_name="aloware-agent"))
