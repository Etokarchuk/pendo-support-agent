"""
Golden-set eval runner.

This is deliberately not "does the response look good" — every assertion
below is a deterministic check against the structured `respond` output
(outcome, tools called, evidence sources, caveats, escalation fields) or a
substring match on the message. That's what makes it possible to run this in
CI-like fashion instead of eyeballing transcripts.

What this does NOT do, on purpose:
  - It runs each case once. LLM outputs are not fully deterministic even at
    low temperature-equivalent settings, so a single run is a prototype
    shortcut, not a quality bar. In production this would run each case N
    times and track a pass RATE per case, gated on a threshold, with flaky
    cases investigated rather than re-run until green.
  - It does not use an LLM judge for the pass/fail gate. Everything gated
    here has an objectively checkable answer (did it call this tool, does the
    outcome match, does a specific field exist). `--judge` adds a *reported,
    non-gating* qualitative score for cases where correctness isn't purely
    structural (e.g. "is this explanation actually clear") — see
    docs/DECISION_LOG.md for why that split, not everything, uses a judge.

Usage:
    python evals/run_evals.py
    python evals/run_evals.py --judge
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# Windows terminals default to a codepage (cp1252, etc.) that can't encode
# every character a model response might contain. Reconfigure stdout to
# UTF-8 defensively rather than restricting what the model or judge can say.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv

load_dotenv()

from app.agent import get_client, run_turn  # noqa: E402
from app.tools import load_fixtures  # noqa: E402

CASES_PATH = Path(__file__).parent / "golden_cases.json"


def _contains_any(text: str, terms: list[str]) -> bool:
    lowered = text.lower()
    return any(t.lower() in lowered for t in terms)


def check_case(case: dict, respond: dict, tools_called: list[str]) -> list[str]:
    """Return a list of failure descriptions; empty list means the case passed."""
    failures = []
    message = respond.get("message", "")
    outcome = respond.get("outcome")

    if outcome != case["expected_outcome"]:
        failures.append(f"outcome: expected '{case['expected_outcome']}', got '{outcome}'")

    for tool in case.get("tools_must_include", []):
        if tool not in tools_called:
            failures.append(f"tools_must_include: '{tool}' was not called (called: {tools_called})")

    for tool in case.get("tools_must_not_include", []):
        if tool in tools_called:
            failures.append(f"tools_must_not_include: '{tool}' was called (called: {tools_called})")

    for term in case.get("message_must_contain", []):
        if term.lower() not in message.lower():
            failures.append(f"message_must_contain: missing '{term}'")

    for group in case.get("message_must_contain_any", []):
        if not _contains_any(message, group):
            failures.append(f"message_must_contain_any: none of {group} present")

    for term in case.get("message_must_not_contain", []):
        if term.lower() in message.lower():
            failures.append(f"message_must_not_contain: found forbidden '{term}'")

    if case.get("must_cite_doc"):
        doc_id = case["must_cite_doc"]
        evidence = respond.get("evidence", [])
        cited = any(doc_id.lower() in e.get("source", "").lower() for e in evidence)
        if not cited:
            failures.append(f"must_cite_doc: no evidence entry cites '{doc_id}' (evidence: {evidence})")

    if case.get("caveats_required"):
        real_caveats = [c for c in respond.get("caveats", []) if not c.startswith("Internal:")]
        if not real_caveats:
            failures.append("caveats_required: caveats list is empty")

    if case.get("escalation_must_include"):
        draft = respond.get("escalation_draft") or {}
        for field_name in case["escalation_must_include"]:
            if not draft.get(field_name):
                failures.append(f"escalation_must_include: escalation_draft.{field_name} is missing/empty")

    if case.get("escalation_guide_id"):
        draft = respond.get("escalation_draft") or {}
        if draft.get("guide_id") != case["escalation_guide_id"]:
            failures.append(
                f"escalation_guide_id: expected '{case['escalation_guide_id']}', got '{draft.get('guide_id')}'"
            )

    return failures


JUDGE_PROMPT = """\
You are grading one turn of a customer support agent for a Pendo-like in-app guide product. \
Score the ASSISTANT MESSAGE on three dimensions, 1-5 each (5 = best):

- clarity: would a non-technical admin understand the diagnosis without follow-up questions?
- actionability: does it tell the customer what to actually do next (or correctly say a human will)?
- over_claiming: 5 = every claim is appropriately hedged/sourced given the evidence; 1 = it states \
things more confidently than the evidence supports.

Customer message: {customer_message}
Assistant message: {assistant_message}
Assistant's cited evidence: {evidence}

Respond with only the JSON."""

_SCORE_FIELD = {"type": "integer", "enum": [1, 2, 3, 4, 5]}

JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "clarity": _SCORE_FIELD,
        "actionability": _SCORE_FIELD,
        "over_claiming": _SCORE_FIELD,
        "rationale": {"type": "string"},
    },
    "required": ["clarity", "actionability", "over_claiming", "rationale"],
    "additionalProperties": False,
}


def judge_case(case: dict, respond: dict) -> dict:
    client = get_client()
    prompt = JUDGE_PROMPT.format(
        customer_message=case["message"],
        assistant_message=respond.get("message", ""),
        evidence=json.dumps(respond.get("evidence", [])),
    )
    response = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=1024,
        output_config={"format": {"type": "json_schema", "schema": JUDGE_SCHEMA}},
        messages=[{"role": "user", "content": prompt}],
    )
    text = next(b.text for b in response.content if b.type == "text")
    return json.loads(text)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--judge", action="store_true", help="Also run the non-gating LLM-judge quality score.")
    args = parser.parse_args()

    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    fixtures = load_fixtures()
    account_name, account_id = fixtures["account"]["name"], fixtures["account"]["id"]

    results = []
    for case in cases:
        turn = run_turn([], case["message"], account_name, account_id)
        failures = check_case(case, turn.respond_input, turn.tools_called)
        passed = not failures
        judge_scores = judge_case(case, turn.respond_input) if args.judge else None
        results.append(
            {
                "case": case,
                "respond": turn.respond_input,
                "tools_called": turn.tools_called,
                "failures": failures,
                "passed": passed,
                "judge": judge_scores,
            }
        )

    # --- report ---
    print(f"\n{'ID':<28} {'CATEGORY':<20} {'RESULT':<6}")
    print("-" * 60)
    for r in results:
        status = "PASS" if r["passed"] else "FAIL"
        print(f"{r['case']['id']:<28} {r['case']['category']:<20} {status:<6}")
        if not r["passed"]:
            for f in r["failures"]:
                print(f"    FAIL: {f}")
        if r["judge"]:
            j = r["judge"]
            print(f"    judge: clarity={j['clarity']} actionability={j['actionability']} over_claiming={j['over_claiming']}")

    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    print("-" * 60)
    print(f"{passed}/{total} passed\n")

    by_category: dict[str, list[bool]] = {}
    for r in results:
        by_category.setdefault(r["case"]["category"], []).append(r["passed"])
    for cat, outcomes in by_category.items():
        print(f"  {cat:<20} {sum(outcomes)}/{len(outcomes)}")

    if args.judge:
        avg = lambda key: sum(r["judge"][key] for r in results if r["judge"]) / sum(1 for r in results if r["judge"])
        print(f"\nJudge averages (reported, non-gating): clarity={avg('clarity'):.1f} "
              f"actionability={avg('actionability'):.1f} over_claiming={avg('over_claiming'):.1f}")

    print(
        "\nNote: single run per case. A production eval would run each case N times and "
        "track a pass RATE gated on a threshold — see docs/DECISION_LOG.md."
    )

    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
