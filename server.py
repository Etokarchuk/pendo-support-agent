"""
Thin FastAPI server: two endpoints that matter, plus the static demo page.

Sessions are in-memory (a dict keyed by session_id) and tickets are a local
JSON file. Both are prototype shortcuts, not "we didn't know better" —
see docs/DECISION_LOG.md for why no database is used here and what would
replace this at production scale.
"""

import json
import uuid
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

load_dotenv()

from app.agent import run_turn  # noqa: E402  (import after load_dotenv so ANTHROPIC_API_KEY is set)
from app.tracing import log_turn  # noqa: E402
from app.tools import load_fixtures  # noqa: E402

app = FastAPI(title="Acme Support Assistant (prototype)")

TICKETS_PATH = Path(__file__).parent / "data" / "tickets.json"

# session_id -> {"history": [...]}  — cleared on server restart. See README
# "What's real vs. simulated" for why this is fine for a demo and what a
# production session store would need (persistence, expiry, per-tenant scoping).
_sessions: dict[str, dict] = {}


class ChatRequest(BaseModel):
    session_id: str | None = None
    message: str


class EscalateRequest(BaseModel):
    session_id: str
    escalation_draft: dict


def _account():
    fixtures = load_fixtures()
    return fixtures["account"]["name"], fixtures["account"]["id"]


@app.post("/chat")
def chat(req: ChatRequest):
    session_id = req.session_id or str(uuid.uuid4())
    session = _sessions.setdefault(session_id, {"history": []})

    account_name, account_id = _account()
    result = run_turn(session["history"], req.message, account_name, account_id)
    session["history"] = result.messages

    log_turn(session_id, req.message, result, account_id)

    return {
        "session_id": session_id,
        **result.respond_input,
        "tools_called": result.tools_called,
    }


@app.post("/escalate")
def escalate(req: EscalateRequest):
    """Deterministic ticket commit. The model only ever *drafts* an escalation
    (in the `respond` tool's escalation_draft field) — this endpoint is the
    one place a ticket actually gets created, and it runs no model call at
    all. The human in the loop is the person clicking "confirm" in the UI."""
    if not req.escalation_draft:
        raise HTTPException(400, "escalation_draft is required")

    TICKETS_PATH.parent.mkdir(exist_ok=True)
    tickets = []
    if TICKETS_PATH.exists():
        tickets = json.loads(TICKETS_PATH.read_text(encoding="utf-8"))

    ticket_id = f"TICKET-{len(tickets) + 1001}"
    tickets.append(
        {
            "ticket_id": ticket_id,
            "session_id": req.session_id,
            "escalation_draft": req.escalation_draft,
        }
    )
    TICKETS_PATH.write_text(json.dumps(tickets, indent=2), encoding="utf-8")

    return {"ticket_id": ticket_id}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def index():
    return FileResponse(Path(__file__).parent / "static" / "index.html")
