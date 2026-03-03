import logging
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from livekit.agents import JobContext, WorkerOptions, cli, AutoSubscribe, Agent, AgentSession
from livekit.plugins import google, silero

from config import load_config
from repositories import InMemoryAppointmentRepository
from tools import build_tool_registry

_repo = InMemoryAppointmentRepository()
ALL_TOOLS = build_tool_registry(_repo)

# Use absolute path so the subprocess always finds .env regardless of cwd
load_dotenv(Path(__file__).parent / ".env")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("aloware.agent")


async def entrypoint(ctx: JobContext):
    # Reload config fresh for every incoming call/session
    config = load_config()

    agent_name = config.get("agent_name", "Agent")
    voice_id = config.get("voice_id") or "Puck"

    # Only expose tools that are listed in enabled_tools
    enabled = set(config.get("enabled_tools", []))
    active_tools = [fn for name, fn in ALL_TOOLS.items() if name in enabled]

    # Resolve {{agent_name}} placeholder in both text fields
    greeting = config["greeting"].replace("{{agent_name}}", agent_name)
    system_prompt = config["system_prompt"].replace("{{agent_name}}", agent_name)

    # Append the live tool list so the LLM knows its exact boundaries
    tool_lines = "\n".join(f"- {name}" for name in sorted(enabled)) or "- (no tools enabled)"
    system_prompt += f"\n\nACTIVE TOOLS (you may ONLY use these):\n{tool_lines}"

    # Explicitly forbid disabled tools so the LLM cannot hallucinate their outcome
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
    logger.info("GOOGLE_API_KEY loaded (len=%d)", len(api_key))

    assistant = Agent(instructions=system_prompt)
    await assistant.update_tools(active_tools)

    session = AgentSession(
        vad=silero.VAD.load(),
        llm=google.realtime.RealtimeModel(
            model="gemini-2.5-flash-native-audio-latest",
            voice=voice_id,
        ),
    )

    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)
    await session.start(room=ctx.room, agent=assistant)

    logger.info("Agent started in room: %s", ctx.room.name)

    _t: list[float] = [0.0]

    @session.on("agent_state_changed")
    def _on_state_changed(ev) -> None:
        if ev.old_state == "listening" and ev.new_state == "thinking":
            _t[0] = time.perf_counter()
        elif ev.new_state == "speaking" and _t[0]:
            ping_ms = round((time.perf_counter() - _t[0]) * 1000)
            logger.info("PING %d ms", ping_ms)
            _t[0] = 0.0

    await session.generate_reply(instructions=f"Greet the user with this exact phrase: '{greeting}'")


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, agent_name="aloware-agent"))
