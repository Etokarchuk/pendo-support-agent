"""
Append-only JSONL trace of every customer turn. This is the observability
surface a real version of this product would build on: request category
(outcome), which tools ran, latency, token cost, and whether the model kept
its response contract. No chain-of-thought is ever written here — we never
read `thinking` blocks in agent.py, so there is nothing hidden to leak.

One line per turn, so a trace file is greppable and diffable without any
tooling — deliberately not a database (see docs/DECISION_LOG.md).
"""

import json
import time
import uuid
from pathlib import Path

TRACE_DIR = Path(__file__).parent.parent / "traces"


def log_turn(session_id: str, user_message: str, turn_result, account_id: str) -> None:
    TRACE_DIR.mkdir(exist_ok=True)
    trace_file = TRACE_DIR / f"{time.strftime('%Y-%m-%d')}.jsonl"

    record = {
        "trace_id": str(uuid.uuid4()),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "session_id": session_id,
        "account_id": account_id,
        "user_message": user_message,
        "outcome": turn_result.respond_input.get("outcome"),
        "tools_called": turn_result.tools_called,
        "num_steps": len(turn_result.steps),
        "steps": turn_result.steps,  # per-call latency/tokens/stop_reason — no reasoning text
        "escalated": turn_result.respond_input.get("outcome") == "escalate",
        "contract_violation": any("Internal:" in c for c in turn_result.respond_input.get("caveats", [])),
    }

    with open(trace_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
