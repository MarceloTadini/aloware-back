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
                                              │
                                     appointments.json  ←── book_appointment tool
```

The agent **reloads `config.json` on every incoming call**, so any change made through the API takes effect on the next call without restarting the worker. Every confirmed appointment is **persisted to `appointments.json`** and survives process restarts.

---

## Project Structure

```
backend/
├── agent.py              # LiveKit worker — voice pipeline entrypoint
├── tools.py              # LLM-callable clinic tools (factory functions)
├── repositories.py       # AppointmentRepository ABC + JsonAppointmentRepository
├── api.py                # FastAPI server — config, appointments, metrics, token
├── config.py             # CONFIG_PATH, load_config(), read_config(), write_config()
├── config.json           # Runtime agent configuration
├── appointments.json     # Persisted bookings (auto-created on first booking)
├── metrics.json          # Latency stats (auto-created on first call)
├── requirements.txt      # Python dependencies
├── .env.example          # Environment variable template
└── .env                  # API keys (not committed)
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

## How Appointment Booking Works (Step by Step)

When a caller asks to book an appointment, the following sequence happens:

**1. Patient expresses intent**
> *"I'd like to schedule an appointment."*

The agent recognises the intent and knows it must collect four pieces of information before it can confirm anything.

**2. Agent collects the date**
> *"Of course! What date would you like?"*

The patient says a date (e.g. "next Tuesday" or "March 10th"). The agent converts it to `YYYY-MM-DD` format internally.

**3. Agent checks availability (optional but recommended)**

The agent calls `check_availability` for that date. It reads `appointments.json` to find already-taken slots and returns the remaining open times to the patient.

> *"For March 10th we have: 09:00, 10:00, 14:30, 15:00. Which time works best for you?"*

**4. Patient chooses a time**
> *"14:30, please."*

**5. Agent collects the patient's full name**
> *"And your full name, please?"*

**6. Agent collects the patient's phone number**
> *"What is the best phone number to reach you?"*

**7. Agent calls `book_appointment`**

Once all four fields are collected (`date`, `time`, `patient_name`, `phone_number`), the agent calls the `book_appointment` function tool. The tool:

- Reads `appointments.json`
- Checks that the slot is still free (conflict prevention)
- Appends the new entry and overwrites the file
- Returns a confirmation string to the LLM

**8. Agent confirms verbally**
> *"Your appointment has been confirmed for [Name] on March 10th at 14:30. We will contact you at [phone] if needed. Is there anything else I can help you with?"*

**9. Entry saved in `appointments.json`**

```json
{
  "date": "2026-03-10",
  "time": "14:30",
  "patient": "João Silva",
  "phone": "+55 11 91234-5678",
  "created_at": "2026-03-03T14:31:07"
}
```

The entry persists across agent restarts. On the next call, `check_availability` will correctly exclude that slot.

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
  "greeting": "Hello! I'm {{agent_name}}, Aloware Health's virtual receptionist. How can I help you today?",
  "voice_id": "Kore",
  "enabled_tools": ["check_availability", "book_appointment", "transfer_to_human"],
  "system_prompt": "You are {{agent_name}}..."
}
```

---

### `PATCH /config`

**Merges** the provided fields into the existing config. Fields not included are preserved.

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

### `POST /config`

**Fully replaces** the configuration. Any field not included is removed from `config.json`.

```bash
curl -X POST http://localhost:8000/config \
  -H "Content-Type: application/json" \
  -d '{
    "agent_name": "Ana",
    "greeting": "Good morning! Aloware Health, how may I help you?",
    "voice_id": "Kore",
    "enabled_tools": ["check_availability", "book_appointment", "transfer_to_human"],
    "system_prompt": "You are {{agent_name}}..."
  }'
```

---

### `GET /appointments`

Returns all booked appointments, optionally filtered by date.

```bash
# All appointments
curl http://localhost:8000/appointments

# Filtered by date
curl "http://localhost:8000/appointments?date=2026-03-10"
```

**Response `200 OK`**
```json
{
  "count": 2,
  "appointments": [
    {
      "date": "2026-03-10",
      "time": "09:00",
      "patient": "João Silva",
      "phone": "+55 11 91234-5678",
      "created_at": "2026-03-03T14:05:22"
    }
  ]
}
```

---

### `GET /metrics`

Returns aggregated response latency statistics collected during the current agent session.

```bash
curl http://localhost:8000/metrics
```

**Response `200 OK`**
```json
{
  "count": 7,
  "last_ms": 312,
  "mean_ms": 389,
  "min_ms": 271,
  "max_ms": 601,
  "p50_ms": 350,
  "p95_ms": 580,
  "last_updated": "2026-03-03T14:22:01Z"
}
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
| `agent_name` | `string` | Display name of the agent — use `{{agent_name}}` as placeholder in `greeting` and `system_prompt` |
| `greeting` | `string` | First sentence spoken to every caller |
| `voice_id` | `string` | Google / LiveKit voice ID for audio synthesis |
| `system_prompt` | `string` | Full LLM system prompt, including guardrails |
| `enabled_tools` | `string[]` | Tools exposed to the LLM (see below) |

### Available tools

| Tool name | What it does |
|---|---|
| `check_availability` | Returns open time slots for a given date, excluding already-booked ones |
| `book_appointment` | Collects name, phone, date and time — saves to `appointments.json` |
| `transfer_to_human` | Transfers the call to a human agent |

Remove a tool name from `enabled_tools` to hide it from the LLM entirely. Disabled tools are also explicitly listed in the system prompt so the model cannot hallucinate their outcome.

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
           → LLM (Google Gemini 2.5 Flash — native audio) generates response / calls a tool
           → Audio streamed back to the user
```

The agent uses Gemini's native audio mode, which handles speech understanding and synthesis end-to-end — no separate STT or TTS service is required. Silero VAD detects when the user has finished speaking before audio is sent for processing.

---

## Reconnection Behaviour

The agent uses `ctx.add_participant_entrypoint()` so a **fresh session is started automatically every time a participant joins** — including reconnects. There is no need to restart the worker process between calls. Each reconnection reloads `config.json`, so any configuration change takes effect immediately on the next call.
