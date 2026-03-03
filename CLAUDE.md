# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A minimal real-time voice AI agent built on the [LiveKit Agents](https://docs.livekit.io/agents/) framework. The agent acts as a Portuguese-language voice assistant for Aloware Health, orchestrating a pipeline of cloud AI services.

## Running the Agent

Activate the virtual environment first:
```bash
source venv/bin/activate
```

Run the agent (connects to LiveKit as a worker):
```bash
python agent.py
```

## Required Environment Variables

Create a `.env` file with these keys before running:
```
LIVEKIT_URL=wss://...
LIVEKIT_API_KEY=...
LIVEKIT_API_SECRET=...
OPEN_AI_KEY=...
```

The agent also needs credentials for Deepgram (STT) and Cartesia (TTS) — check whether their SDKs pick these up from the environment automatically or require additional keys.

## Architecture

All application logic lives in `agent.py` (27 lines). There is no database, no REST API, and no persistent state.

**Voice pipeline** (per room session):
```
User speech → VAD (OpenAI) → STT (Deepgram) → LLM (OpenAI) → TTS (Cartesia) → Audio out
```

The `entrypoint(ctx: JobContext)` function is the single entry point. It is called by the LiveKit worker runtime for each incoming job (room session). The agent is stateless — it lives for the duration of a room session only.

**Key design note**: A comment in the code (`# Aqui você conectará com o config.json que o seu React vai editar`) indicates the `initial_ctx` system prompt is intended to be driven by a React-editable `config.json` — this is a planned but not yet implemented integration.

## Tech Stack

| Component | Library |
|-----------|---------|
| Agent framework | `livekit-agents` 1.4.4 |
| VAD | `livekit-plugins-openai` |
| STT | `livekit-plugins-deepgram` |
| LLM | `livekit-plugins-openai` |
| TTS | `livekit-plugins-cartesia` |
| Env config | `python-dotenv` |

Python version: 3.10.12 (isolated venv).
