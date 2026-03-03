# UNDERSTAND AND MEMORIZE HOW MY FRONTEND WORKS

# Aloware Health — Voice Agent Admin UI

A React admin dashboard to configure and test the **Aloware Health** AI voice receptionist in real time, without restarting the backend.

---

## Overview

The system has two independent pieces:

| Layer | Tech | Role |
|---|---|---|
| **Backend** | Python · LiveKit Agents · FastAPI | Runs the live voice pipeline and exposes a config API |
| **Frontend** | React 19 · TypeScript · Vite · Tailwind CSS | Admin UI to edit the agent config and test calls |

Changes saved in the UI are written to `config.json` on the backend. The agent picks them up on the next incoming call — no restart required.

---

## Architecture

```
┌─────────────────────────────────────────┐
│  Browser (localhost:5173)               │
│  AdminDashboard.tsx                     │
│    └─ api.ts  ──── PATCH /config ──────►│
│    └─ TestCallWidget.tsx ── GET /token ─►│
└───────────────────┬─────────────────────┘
                    │ HTTP
┌───────────────────▼─────────────────────┐
│  FastAPI  (localhost:8000)              │
│  api.py — /config, /token, /health      │
│    └─ reads/writes config.json          │
└───────────────────┬─────────────────────┘
                    │ LiveKit SDK
┌───────────────────▼─────────────────────┐
│  LiveKit Agents worker                  │
│  agent.py                               │
│    VAD (OpenAI) → STT (Deepgram)        │
│    → LLM (GPT-4o) → TTS (Cartesia)     │
│    → tools.py (clinic tools)            │
└─────────────────────────────────────────┘
```

---

## Frontend — Source structure

```
src/
├── main.tsx                  # React entry point
├── App.tsx                   # Renders <AdminDashboard>
├── api.ts                    # HTTP service layer (getConfig, patchConfig, getToken)
├── index.css                 # Tailwind base + .input component + toast animation
└── components/
    ├── AdminDashboard.tsx    # Main page: settings form, tools, sidebar
    └── TestCallWidget.tsx    # LiveKit browser call widget (Start / End Call)
```

### `api.ts`

Three exported functions, all targeting `http://localhost:8000`:

| Function | Method | Endpoint | Purpose |
|---|---|---|---|
| `getConfig()` | GET | `/config` | Load the current agent config on mount |
| `patchConfig(data)` | PATCH | `/config` | Save partial or full config updates |
| `getToken(room, identity)` | GET | `/token` | Get a LiveKit JWT for test calls |

### `AdminDashboard.tsx`

Single-page form with:
- **General section** — Agent Name, Voice Persona (dropdown + custom UUID field), Greeting
- **System Prompt section** — full-height monospace textarea for LLM instructions
- **Enabled Tools section** — checkboxes for `check_availability`, `book_appointment`, `transfer_to_human`
- **Save Changes** button in the sticky header — sends a `PATCH /config` request
- **Toast notifications** — green on success, red on failure, auto-dismiss after 4 s
- **Test Call widget** in the sidebar (see below)

### `TestCallWidget.tsx`

Connects the browser microphone to the LiveKit room where the agent is running:
1. Calls `GET /token` to obtain a JWT and the LiveKit server URL
2. Opens a `livekit-client` `Room` and enables the microphone
3. Shows a pulsing indicator while speaking
4. "End Call" disconnects cleanly

---

## Frontend setup

### Prerequisites

- Node.js 18+ and Yarn

### 1 — Install dependencies

```bash
cd frontend/aloware
yarn install
```

### 2 — Start the dev server

```bash
yarn run dev
```

Open [http://localhost:5173](http://localhost:5173).

### Available scripts

```bash
yarn run dev       # Development server with HMR
yarn run build     # Type-check (tsc) then bundle (Vite)
yarn run lint      # ESLint
yarn run preview   # Serve the production build locally
```

---

## Backend setup

The frontend is useless without the Python backend. Full details live in `backend/`, but here is the short version.

### Prerequisites

- Python 3.11+
- A LiveKit Cloud project (or self-hosted server)
- API keys for OpenAI, Deepgram, and Cartesia

### 1 — Create the virtual environment and install packages

```bash
cd backend
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2 — Create the `.env` file

```env
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=your_api_key
LIVEKIT_API_SECRET=your_api_secret

OPENAI_API_KEY=sk-...
DEEPGRAM_API_KEY=...
CARTESIA_API_KEY=...
```

### 3 — Run both backend processes

```bash
# Terminal 1 — voice agent worker
python agent.py

# Terminal 2 — config + token API
uvicorn api:app --reload --port 8000
```

### 4 — Add the `/token` endpoint (required for Test Call)

The Test Call widget calls `GET /token`. Add this to `api.py` if it is not already present:

```python
import os
from livekit import api as lk_api

@app.get("/token")
async def generate_token(room: str = "test-room", identity: str = "admin"):
    token = lk_api.AccessToken(
        api_key=os.environ["LIVEKIT_API_KEY"],
        api_secret=os.environ["LIVEKIT_API_SECRET"],
    )
    token.with_grants(lk_api.VideoGrants(room_join=True, room=room))
    token.with_identity(identity)
    return {
        "token": token.to_jwt(),
        "url": os.environ["LIVEKIT_URL"],
    }
```

---

## Backend API reference

Base URL: `http://localhost:8000`

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Returns `{"status": "healthy"}` |
| `GET` | `/config` | Returns the current agent config |
| `POST` | `/config` | Fully replaces the config |
| `PATCH` | `/config` | Merges provided fields into the config |
| `GET` | `/token` | Returns a LiveKit JWT for browser test calls |

### Config schema

```json
{
  "agent_name": "Ana",
  "greeting": "Hello! I'm Ana, how can I help you today?",
  "voice_id": "a0e99841-438c-4a64-b679-ae501e7d6091",
  "system_prompt": "You are Ana, a medical receptionist...",
  "enabled_tools": ["check_availability", "book_appointment", "transfer_to_human"]
}
```

### Available tools

| Tool key | Description |
|---|---|
| `check_availability` | Returns mock open appointment slots for a given date |
| `book_appointment` | Logs and confirms an appointment booking |
| `transfer_to_human` | Simulates a call transfer to a live agent |

Remove a key from `enabled_tools` to hide that capability from the LLM entirely.

---

## How config changes propagate

```
Admin saves form in UI
        │
        ▼
  PATCH /config
        │
        ▼
  api.py writes config.json
        │
        ▼
  agent.py reads config.json
  on the next incoming call
  (no restart required)
```

---

## Tech stack

| Concern | Library / Tool |
|---|---|
| UI framework | React 19 |
| Language | TypeScript (strict mode) |
| Build tool | Vite 7 |
| Styling | Tailwind CSS v4 (via `@tailwindcss/vite`) |
| Browser calls | `livekit-client` v2 |
| Linting | ESLint 9 flat config + typescript-eslint |
| Voice pipeline | LiveKit Agents, OpenAI GPT-4o, Deepgram STT, Cartesia TTS |


