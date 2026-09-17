"""
The agent loop. This file is the whole "agent" — everything else is tools,
data, and prompt text. Deliberately hand-written rather than a framework or
the SDK's beta tool runner: every product decision (tool_choice strategy,
what happens when the model breaks the response contract, the step cap) is a
few visible lines here instead of framework configuration. See
docs/DECISION_LOG.md for the tradeoff.

Design choices worth noting on first read:

- tool_choice is forced ("any"), not "auto". This started as "auto" plus a
  prompt instruction, on the theory that forcing tool use might not be
  portable across model versions. Real testing falsified that theory faster
  than it justified it: with "auto", the model twice produced a plain-text
  reply instead of calling `respond` — once for small talk ("how are you
  doing?"), once for a clarifying question ("which guide do you mean?") —
  both caught by the fail-closed guardrail below, but a caught contract
  violation isn't the same as correct behavior. Forcing tool_choice removes
  the failure mode at its source instead of only catching it after the fact.
  The guardrail (_contract_violation_result) stays regardless — an API
  failure or an empty tool_use list from a future model swap still needs
  somewhere to fail closed to. See docs/DECISION_LOG.md #4 for the full
  before/after account.
- Thinking is left on (adaptive, the model's default) but never displayed —
  we never read or store `thinking` blocks. The requirement from the product
  brief is "never store hidden chain-of-thought," not "never think"; adaptive
  thinking measurably helps the multi-hop diagnosis this agent does.
- The loop has a hard step cap. An agent that can call tools has to have a
  bound on how long it's allowed to try before something (a bug, a confusing
  fixture, a model getting stuck) forces a human decision instead of an
  unbounded bill.
"""

import json
import time
from dataclasses import dataclass, field

import anthropic

from app.knowledge import search_docs
from app.prompts import build_system_prompt
from app.tools import TOOL_SCHEMAS, get_guide, get_install_status, get_segment, list_guides

MODEL = "claude-sonnet-5"
MAX_TOKENS = 8000
MAX_STEPS = 8  # hard cap on tool-call rounds per customer turn
EFFORT = "medium"  # multi-hop diagnosis benefits from thinking; "medium" balances cost/latency for a chat UI

TOOL_EXECUTORS = {
    "get_guide": lambda **kw: get_guide(**kw),
    "get_segment": lambda **kw: get_segment(**kw),
    "get_install_status": lambda **kw: get_install_status(**kw),
    "list_guides": lambda **kw: list_guides(),
    "search_docs": lambda **kw: search_docs(**kw),
}

_client = None


def get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


@dataclass
class TurnResult:
    """Everything one customer turn produced, for the server to render and
    the trace log to record. `respond_input` is the validated dict the model
    passed to the `respond` tool (or the synthetic fail-closed one)."""

    respond_input: dict
    messages: list  # full message history including this turn, for the next turn
    steps: list = field(default_factory=list)  # per-model-call trace records
    tools_called: list = field(default_factory=list)  # flat list of tool names, in order


def _contract_violation_result(reason: str, partial_text: str = "") -> dict:
    """Build the fail-closed response used whenever the model doesn't honor
    the response contract (no tool call, or the step cap was hit). This is a
    deliberate product behavior, not an error path we forgot to handle: an
    ungoverned model turn must never reach the customer as a bare answer."""
    return {
        "outcome": "escalate",
        "message": (
            "I wasn't able to finish diagnosing this within my normal steps, so I'm "
            "handing it to a person rather than guess. Sorry for the detour — they'll "
            "have what I found so far."
        ),
        "evidence": [],
        "caveats": [f"Internal: {reason}"],
        "escalation_draft": {
            "summary": "Agent did not produce a valid response within its step/format limits.",
            "guide_id": None,
            "checks_performed": [],
            "unresolved_reason": reason + (f" Partial model output: {partial_text[:500]}" if partial_text else ""),
        },
    }


def _execute_tool(name: str, tool_input: dict) -> tuple[dict, bool]:
    """Run one tool call. Returns (result_dict, is_error)."""
    executor = TOOL_EXECUTORS.get(name)
    if executor is None:
        return {"error": "unknown_tool", "message": f"No such tool: {name}"}, True
    try:
        result = executor(**tool_input)
    except Exception as exc:  # a tool bug should surface as a failed lookup, not crash the turn
        return {"error": "tool_exception", "message": str(exc)}, True
    return result, bool(isinstance(result, dict) and result.get("error"))


def _fix_double_escaped_whitespace(value):
    """The model occasionally double-escapes whitespace inside a tool call's
    JSON arguments — writing the literal two characters '\n' instead of an
    actual newline (confirmed via character-code inspection, not guessed: the
    string contains chars 92,110 — backslash, 'n' — not char 10). This is a
    known artifact of LLM-generated tool-call JSON, not something the prompt
    controls. By the time a value reaches here, the API's own JSON parser has
    already correctly unescaped everything once — a literal backslash-n
    substring surviving that can only be this artifact, never a customer's or
    our own intentional text, so normalizing it is safe. Applied to every
    string in the model's `respond` input (recursively, since `evidence` and
    `escalation_draft` nest further strings) so the UI, the trace log, and
    eval substring assertions all see clean text, not just one consumer."""
    if isinstance(value, str):
        return value.replace("\\n", "\n").replace("\\t", "\t")
    if isinstance(value, list):
        return [_fix_double_escaped_whitespace(v) for v in value]
    if isinstance(value, dict):
        return {k: _fix_double_escaped_whitespace(v) for k, v in value.items()}
    return value


def run_turn(history: list, user_message: str, account_name: str, account_id: str) -> TurnResult:
    """Run one customer turn to completion: send the message, execute any
    tool calls the model makes, and keep going until it calls `respond` (or a
    guardrail below ends the turn instead)."""
    client = get_client()
    system = build_system_prompt(account_name=account_name, account_id=account_id)
    messages = history + [{"role": "user", "content": user_message}]

    steps = []
    tools_called = []

    for step in range(1, MAX_STEPS + 1):
        started = time.monotonic()
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                # Cached: render order is tools -> system -> messages, so a
                # breakpoint on the system block covers both the (static)
                # tool schemas and the (static, single-account) system prompt
                # in one cached prefix. Only `messages` varies per call. This
                # cuts the repeated-prefix cost by ~90% on cache hits — see
                # docs/DECISION_LOG.md for why this wasn't in the original
                # build (a single-account demo has no session-reuse pattern
                # a prototype naturally exercises) and what surfaced the gap.
                system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
                tools=TOOL_SCHEMAS,
                tool_choice={"type": "any"},
                output_config={"effort": EFFORT},
                messages=messages,
            )
        except anthropic.APIError as exc:
            # The SDK already retries transient failures (429/5xx/connection
            # errors) with backoff before raising — by the time we see this,
            # that budget is exhausted. One broad except is deliberate here,
            # not the "catch a chain of specific types" pattern used
            # elsewhere: every subtype gets the identical response (fail
            # closed to a human) because a customer-facing chat turn
            # shouldn't hang on our own additional retries for what should be
            # a quick reply. `messages` is unchanged — nothing was appended
            # for a call that never returned a response.
            return TurnResult(
                respond_input=_contract_violation_result(f"Anthropic API error: {exc}"),
                messages=messages,
                steps=steps,
                tools_called=tools_called,
            )
        latency_ms = round((time.monotonic() - started) * 1000)

        tool_use_blocks = [b for b in response.content if b.type == "tool_use"]
        step_tool_names = [b.name for b in tool_use_blocks]
        steps.append(
            {
                "step": step,
                "stop_reason": response.stop_reason,
                "tools": step_tool_names,
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
                "cache_read_tokens": response.usage.cache_read_input_tokens or 0,
                "cache_creation_tokens": response.usage.cache_creation_input_tokens or 0,
                "latency_ms": latency_ms,
            }
        )
        tools_called.extend(step_tool_names)

        # Contract violation: the model ended the turn without calling `respond`.
        if not tool_use_blocks:
            text = "".join(b.text for b in response.content if b.type == "text")
            messages.append({"role": "assistant", "content": response.content})
            return TurnResult(
                respond_input=_contract_violation_result(
                    "Model ended its turn without calling any tool (expected at least `respond`).",
                    partial_text=text,
                ),
                messages=messages,
                steps=steps,
                tools_called=tools_called,
            )

        messages.append({"role": "assistant", "content": response.content})

        # Execute every tool call in this message and answer every one of
        # them with a tool_result — including `respond` itself. This matters
        # even though the model is instructed to call `respond` alone as its
        # last action: parallel tool use is on by default, so if it ever
        # calls `respond` alongside an information tool in the same message,
        # every tool_use block still needs a matching tool_result or the
        # conversation transcript becomes invalid for the session's next
        # turn (the API requires a result for every pending tool_use before
        # generating another assistant turn).
        respond_input = None
        tool_results = []
        for block in tool_use_blocks:
            if block.name == "respond":
                respond_input = _fix_double_escaped_whitespace(block.input)
                tool_results.append(
                    {"type": "tool_result", "tool_use_id": block.id, "content": "Sent to customer."}
                )
                continue
            result, is_error = _execute_tool(block.name, block.input)
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result),
                    "is_error": is_error,
                }
            )
        messages.append({"role": "user", "content": tool_results})

        if respond_input is not None:
            return TurnResult(respond_input=respond_input, messages=messages, steps=steps, tools_called=tools_called)

    # Step cap reached without a `respond` call.
    return TurnResult(
        respond_input=_contract_violation_result(
            f"Hit the {MAX_STEPS}-step tool-call limit without reaching a final response."
        ),
        messages=messages,
        steps=steps,
        tools_called=tools_called,
    )
