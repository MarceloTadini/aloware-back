# Aloware Health — Voice Agent Backend

A real-time voice AI agent for a medical clinic receptionist, built with [LiveKit Agents](https://docs.livekit.io/agents/). The agent handles appointment scheduling, availability checks, and call transfers over voice — all configurable at runtime via a REST API.

---

## Architecture

```
Caller
  │
  ▼ (WebRTC / SIP via LiveKit)
┌─────────────────────────────────────┐
│            agent.py                 │
│  VAD → LLM (native audio)           │
│  (Silero) (Google Gemini 2.5 Flash) │
│                                     │
│  tools.py  ←  LLM function calls   │
│  ┌─────────────────────────────┐   │
│  │ check_availability          │   │
│  │ book_appointment            │   │
│  │ transfer_to_human           │   │
│  └─────────────────────────────┘   │
└─────────────────────────────────────┘
         ▲ reads on every call
         │
     config.json  ←──  PATCH /config  ←── React Frontend
```

The agent **reloads `config.json` on every incoming call**, so any change made through the API takes effect on the next call without restarting the worker.

---

## Project Structure

```
backend/
├── agent.py             # LiveKit worker — voice pipeline entrypoint
├── tools.py             # LLM-callable clinic tools (factory functions)
├── repositories.py      # AppointmentRepository ABC + InMemoryAppointmentRepository
├── api.py               # FastAPI server — config sync for the frontend
├── config.py            # CONFIG_PATH, load_config(), read_config(), write_config()
├── config.json          # Runtime agent configuration
├── requirements.txt     # Python dependencies
├── .env.example         # Environment variable template
└── .env                 # API keys (not committed)
```

---

## Setup

### 1. Prerequisites

- Python 3.10+
- A LiveKit Cloud project (or self-hosted server)
- API keys for: Google (Gemini), LiveKit

### 2. Create and activate a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Copy the template and fill in your keys:

```bash
cp .env.example .env
```

```env
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=your_livekit_api_key
LIVEKIT_API_SECRET=your_livekit_api_secret
GOOGLE_API_KEY=your_google_api_key
```

### 5. Run the services

Open two terminals with the virtual environment active:

```bash
# Terminal 1 — Voice agent worker
source venv/bin/activate
python agent.py

# Terminal 2 — Config sync API
source venv/bin/activate
uvicorn api:app --reload --port 8000
```

---

## Config API Reference

Base URL: `http://localhost:8000`

Interactive docs available at `http://localhost:8000/docs` (Swagger UI).

---

### `GET /config`

Returns the current agent configuration.

**Response `200 OK`**
```json
{
  "agent_name": "Ana",
  "greeting": "Hello! I'm Ana, Aloware Health's virtual receptionist. How can I help you today?",
  "voice_id": "a0e99841-438c-4a64-b679-ae501e7d6091",
  "enabled_tools": ["check_availability", "book_appointment", "transfer_to_human"],
  "system_prompt": "You are Ana..."
}
```

---

### `POST /config`

**Fully replaces** the configuration. Any field not included in the request body is removed from `config.json`.

**Request body** (all fields optional, but at least one required):
```json
{
  "agent_name": "string",
  "greeting": "string",
  "voice_id": "string",
  "system_prompt": "string",
  "enabled_tools": ["check_availability", "book_appointment", "transfer_to_human"]
}
```

**Response `200 OK`**
```json
{
  "status": "ok",
  "config": { "...updated config..." }
}
```

**Example — change the greeting:**
```bash
curl -X POST http://localhost:8000/config \
  -H "Content-Type: application/json" \
  -d '{
    "agent_name": "Ana",
    "greeting": "Good morning! Aloware Health, how may I help you?",
    "voice_id": "a0e99841-438c-4a64-b679-ae501e7d6091",
    "enabled_tools": ["check_availability", "book_appointment", "transfer_to_human"],
    "system_prompt": "You are Ana..."
  }'
```

---

### `PATCH /config`

**Merges** the provided fields into the existing config. Fields not included in the request body are preserved as-is.

**Request body** (at least one field required):
```json
{
  "greeting": "Good afternoon! How can I help?",
  "enabled_tools": ["check_availability", "transfer_to_human"]
}
```

**Response `200 OK`**
```json
{
  "status": "ok",
  "config": { "...full merged config..." }
}
```

**Example — disable the booking tool:**
```bash
curl -X PATCH http://localhost:8000/config \
  -H "Content-Type: application/json" \
  -d '{"enabled_tools": ["check_availability", "transfer_to_human"]}'
```

---

### `GET /health`

Simple liveness check.

**Response `200 OK`**
```json
{ "status": "healthy" }
```

---

## Config Fields Reference

| Field | Type | Description |
|---|---|---|
| `agent_name` | `string` | Display name of the agent (e.g. `"Ana"`) |
| `greeting` | `string` | First sentence spoken to every caller |
| `voice_id` | `string` | Cartesia voice ID for TTS synthesis |
| `system_prompt` | `string` | Full LLM system prompt, including guardrails |
| `enabled_tools` | `string[]` | Tools exposed to the LLM (see below) |

### Available tools

| Tool name | What it does |
|---|---|
| `check_availability` | Returns mock open slots for a given date |
| `book_appointment` | Logs and confirms an appointment booking |
| `transfer_to_human` | Simulates transferring the call to a human agent |

Remove a tool name from `enabled_tools` to hide it from the LLM entirely.

---

## Guardrails

The default `system_prompt` enforces strict content boundaries. The agent will never:

- Provide medical diagnoses or interpret test results
- Suggest treatments or medication dosages
- Discuss health conditions in a clinical way

If a patient asks about any of these topics the agent responds:

> *"I am not authorized to address that subject. I can schedule an appointment with our physicians so they can help you."*

To adjust the guardrails, update `system_prompt` via `PATCH /config`.

---

## Voice Pipeline

```
User speaks → VAD (Silero) detects speech end
           → LLM (Google Gemini 2.5 Flash — native audio) generates a response / calls a tool
           → Audio streamed back to the user
```

The agent uses Gemini's native audio mode, which handles speech understanding and synthesis end-to-end — no separate STT or TTS service is required. Silero VAD detects when the user has finished speaking before the audio is sent for processing.
