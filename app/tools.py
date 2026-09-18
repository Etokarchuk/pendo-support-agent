"""
Tool schemas and executors for the guide-diagnosis agent.

Every account-data tool here is READ-ONLY and backed by data/fixtures.json — a
simulated dataset modeled on Pendo's concepts (guides, segments, install
snippet, visitor metadata). There is no real Pendo account behind this; see
README.md "What's real vs. simulated". The shape of each tool (inputs,
outputs, error modes) is deliberately close to what a real client for such an
API would look like, so swapping the fixture-backed functions below for real
HTTP calls would not require changing the agent loop or the tool schemas.

There is no write tool. That is a product decision (see docs/DECISION_LOG.md),
not an oversight — the agent can diagnose and recommend, never change a
customer's configuration.
"""

import json
from pathlib import Path

FIXTURES_PATH = Path(__file__).parent.parent / "data" / "fixtures.json"

_fixtures_cache = None


def load_fixtures() -> dict:
    global _fixtures_cache
    if _fixtures_cache is None:
        with open(FIXTURES_PATH, "r", encoding="utf-8") as f:
            _fixtures_cache = json.load(f)
    return _fixtures_cache


# ---------------------------------------------------------------------------
# Tool executors
#
# Each returns a plain dict. On failure they return {"error": ..., "message":
# ...} rather than raising — the caller (app/agent.py) is responsible for
# marking the tool_result as is_error=True so the model sees it as a failed
# lookup, not as a fact to reason from.
# ---------------------------------------------------------------------------


def get_guide(name_or_id: str) -> dict:
    """Look up guide(s) by exact ID or a case-insensitive substring of the name.

    Returns every match. The caller is expected to ask a clarifying question
    when more than one guide matches — this tool does not pick one for you.
    """
    fixtures = load_fixtures()
    query = name_or_id.strip().lower()
    matches = [
        g
        for g in fixtures["guides"]
        if g["id"].lower() == query or query in g["name"].lower()
    ]
    if not matches:
        return {
            "error": "not_found",
            "message": f"No guide found matching '{name_or_id}'.",
        }
    return {"matches": matches}


def get_segment(segment_id: str) -> dict:
    """Look up a segment's live eligibility rule and estimated visitor count."""
    fixtures = load_fixtures()
    segment = next((s for s in fixtures["segments"] if s["id"] == segment_id), None)
    if segment is None:
        return {"error": "not_found", "message": f"No segment found with id '{segment_id}'."}
    if segment.get("unavailable"):
        return {
            "error": segment.get("error_code", "unavailable"),
            "message": segment.get("error_message", "Segment data is unavailable."),
        }
    return segment


def get_install_status(app_id: str) -> dict:
    """Look up whether the install snippet is active for an app and which
    visitor metadata fields it is currently sending."""
    fixtures = load_fixtures()
    app = next((a for a in fixtures["apps"] if a["id"] == app_id), None)
    if app is None:
        return {"error": "not_found", "message": f"No app found with id '{app_id}'."}
    return app


def list_guides() -> dict:
    """List all guides on the account (id, name, status only) — used to help
    the agent ask a useful clarifying question rather than a generic one."""
    fixtures = load_fixtures()
    return {
        "guides": [
            {"id": g["id"], "name": g["name"], "status": g["status"]}
            for g in fixtures["guides"]
        ]
    }


# ---------------------------------------------------------------------------
# Tool schemas (Anthropic Messages API format)
#
# All use strict:true — the model's arguments are guaranteed to validate
# against the schema, which matters here because tool inputs (e.g. which
# segment_id to look up) come from the model's own multi-hop reasoning and
# feed directly into the next tool call.
# ---------------------------------------------------------------------------

TOOL_SCHEMAS = [
    {
        "name": "get_guide",
        "description": (
            "Look up one or more guides by exact guide ID (e.g. 'G-1001') or by a "
            "substring of the guide's name (case-insensitive). Guide names are not "
            "unique — if this returns more than one match, do not guess which one "
            "the customer means; ask them to confirm."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "name_or_id": {
                    "type": "string",
                    "description": "A guide ID or a name/partial name to search for.",
                }
            },
            "required": ["name_or_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_segment",
        "description": (
            "Look up a segment's targeting rule and current live estimated visitor "
            "count by segment ID. Use this after get_guide to check whether the "
            "guide's assigned segment actually has any eligible visitors right now."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "segment_id": {"type": "string", "description": "A segment ID, e.g. 'SEG-20'."}
            },
            "required": ["segment_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_install_status",
        "description": (
            "Look up whether the Pendo install snippet is active for an app, when it "
            "last sent an event, and which visitor metadata fields it currently "
            "sends. Use this to check whether a segment's missing visitors are "
            "explained by a metadata field the app has stopped sending, or by the "
            "snippet not being installed at all."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "app_id": {"type": "string", "description": "An app ID, e.g. 'APP-1'."}
            },
            "required": ["app_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "list_guides",
        "description": (
            "List every guide on the account with its ID, name, and status. Use this "
            "only when a customer's request is too vague to search for a specific "
            "guide (e.g. 'my guides are broken' with no guide named) and you need to "
            "ask a useful clarifying question."
        ),
        "strict": True,
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "search_docs",
        "description": (
            "Search Acme's product documentation for guidance on how guides, "
            "segments, and install work. Use this for how-to questions and to find "
            "the doc that explains a diagnosis you're making, so you can cite it."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "A search query."}},
            "required": ["query"],
            "additionalProperties": False,
        },
    },
    {
        "name": "respond",
        "description": (
            "Send the final answer to the customer. This is the ONLY way to send a "
            "message — call it exactly once, as your last action, to end the turn. "
            "Never write your answer as plain text instead of calling this tool."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "evidence": {
                    "type": "array",
                    "description": (
                        "Every factual claim in `summary`, `checks`, or `fix` that came from "
                        "a tool or doc result, with its source. Empty array only for "
                        "needs_clarification or out_of_scope, where no facts were used. Every "
                        "`source` and `fact` must be a real, specific value from an actual "
                        "tool result you received this turn (an ID, a status, a count, a "
                        "doc's real content), never a placeholder, a generic label, or filler "
                        "text of any kind. If you cannot name the real source and fact for a "
                        "claim, do not state that claim elsewhere either."
                    ),
                    "items": {
                        "type": "object",
                        "properties": {
                            "source": {
                                "type": "string",
                                "description": "The exact tool call or doc this came from, e.g. 'get_guide(G-1001)', 'get_segment(SEG-20)', 'doc:segments-and-eligibility' — never a placeholder.",
                            },
                            "fact": {"type": "string", "description": "The specific real fact taken from that source (an actual value, not a placeholder)."},
                        },
                        "required": ["source", "fact"],
                        "additionalProperties": False,
                    },
                },
                "caveats": {
                    "type": "array",
                    "description": (
                        "Explicit data-quality flags: a stale or pre-rule-change segment "
                        "estimate, two sources that disagree, or a check that could not be "
                        "completed. Empty array if the evidence has no such issues — do not "
                        "put ordinary explanation here, only genuine uncertainty about the data."
                    ),
                    "items": {"type": "string"},
                },
                "escalation_draft": {
                    "type": ["object", "null"],
                    "description": "Required (non-null) when outcome is 'escalate'; null otherwise.",
                    "properties": {
                        "summary": {"type": "string", "description": "One or two sentences: what the customer reported."},
                        "guide_id": {"type": ["string", "null"], "description": "The guide ID involved, if any."},
                        "checks_performed": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Each check already run and its result, so a human doesn't repeat it.",
                        },
                        "unresolved_reason": {
                            "type": "string",
                            "description": "Specifically what remains unexplained or unverifiable.",
                        },
                    },
                    "required": ["summary", "guide_id", "checks_performed", "unresolved_reason"],
                    "additionalProperties": False,
                },
                "summary": {
                    "type": "string",
                    "description": (
                        "One or two plain sentences, in everyday language a non-technical "
                        "admin can follow with zero re-reading. For needs_clarification and "
                        "out_of_scope, this is the ENTIRE customer-facing message — the "
                        "question or the decline, nothing else. For answered/escalate, this is "
                        "just the headline (e.g. 'Nobody sees this guide because its segment "
                        "has 0 eligible visitors right now.') — the detail goes in `checks` "
                        "and `fix` below, not here."
                    ),
                },
                "checks": {
                    "type": ["array", "null"],
                    "description": (
                        "Required (a non-empty array) for answered and escalate; null for "
                        "needs_clarification and out_of_scope. One short, plain-English item "
                        "per thing you checked and what you found — 'Guide status: published, "
                        "not the issue', not a paragraph. Never show raw code, a rule "
                        "expression, or a field name as syntax (no `visitor.region == 'EU'`) — "
                        "translate it: 'targets EU visitors on a trial plan', not the boolean "
                        "expression. A non-technical admin must be able to read every item "
                        "without knowing what a boolean or a metadata field is."
                    ),
                    "items": {"type": "string"},
                },
                "fix": {
                    "type": ["string", "null"],
                    "description": (
                        "Required (non-null) for answered when you found a customer-fixable "
                        "cause. Null for needs_clarification, out_of_scope, and escalate (the "
                        "escalate case's next step is `escalation_draft.unresolved_reason`, not "
                        "this field — don't duplicate it here). Plain language, one or two "
                        "sentences: what to actually do next."
                    ),
                },
                "outcome": {
                    "type": "string",
                    "enum": ["answered", "needs_clarification", "escalate", "out_of_scope"],
                    "description": (
                        "Fill this in LAST, after everything else above — it must be a "
                        "faithful summary of what you just wrote, not a decision made before "
                        "working through the rest. If escalation_draft is non-null, outcome "
                        "must be 'escalate'; they can never disagree. If `fix` is non-null, "
                        "outcome must be 'answered'. "
                        "answered: you diagnosed the issue or answered a how-to question. Use "
                        "this even when the customer ALSO asked something out-of-scope (billing, "
                        "or a request to change a setting) as long as they asked a real "
                        "diagnostic question too — do the diagnosis, decline the rest inline in "
                        "`fix` or `summary`. "
                        "needs_clarification: the request is ambiguous or under-specified — "
                        "you asked a question instead of guessing. "
                        "escalate: you could not resolve this with the tools available "
                        "(everything checked out healthy, or a required check failed) and "
                        "a human needs to take it. "
                        "out_of_scope: the ENTIRE request is something this agent doesn't "
                        "handle — billing/refunds, or asking only to change a setting with no "
                        "diagnostic question attached. If there's no diagnosis to do, don't "
                        "call any account-data tool first."
                    ),
                },
            },
            "required": ["evidence", "caveats", "escalation_draft", "summary", "checks", "fix", "outcome"],
            "additionalProperties": False,
        },
    },
]
