# Evaluation Rubric

This is the one place both rubrics used to grade this agent are defined together,
with what they check and why. The implementation lives in
[`evals/golden_cases.json`](../evals/golden_cases.json) (the rubric-as-data) and
[`evals/run_evals.py`](../evals/run_evals.py) (the rubric-as-code); this doc is the
map between them.

## Two tiers, on purpose

| | Deterministic assertions | LLM-as-judge |
|---|---|---|
| Grades | Structural correctness: did it call the right tools, reach the right outcome, cite the right doc, populate required fields | Subjective quality: is the explanation actually clear, does it over-claim relative to its evidence |
| Gates pass/fail? | **Yes** — this is the real gate | **No** — reported only |
| Why | Every one of these has an objectively correct answer given the fixtures | Neither "clear" nor "appropriately hedged" has a ground-truth label without human review, and the judge hasn't been calibrated against one (see Calibration below) |

Nothing here is graded by an LLM that could instead be checked deterministically.
`must_cite_doc` doesn't ask a judge "did it seem to use the docs" — it checks whether
a `doc:<id>` string literally appears in the structured `evidence[].source` field. The
judge is reserved for the residual: qualities where two people could reasonably assign
different scores.

---

## Tier 1: Deterministic assertions

Each of the 18 cases in `golden_cases.json` is a customer message plus a set of these
checks (usage counts across the current 18 cases):

| Field | Checks | Used in |
|---|---|---|
| `expected_outcome` | The `respond` tool's `outcome` matches exactly (`answered` \| `needs_clarification` \| `escalate` \| `out_of_scope`) | 18/18 (always required) |
| `tools_must_include` | Every named tool appears in the actual tool-call trace | 13/18 |
| `message_must_contain_any` | For each listed group, at least one term from that group appears (case-insensitive) — used for "the model must convey X, in whatever wording" | 10/18 |
| `message_must_not_contain` | None of the listed terms appear — catches wrong claims or leaked adversarial content | 6/18 |
| `tools_must_not_include` | The named tool was never called — proves scope discipline (e.g. no account tool touched for an out-of-scope request) | 6/18 |
| `must_cite_doc` | An `evidence[].source` entry references this doc ID | 3/18 |
| `caveats_required` | The `caveats[]` array is non-empty (excluding internal/system caveats) | 3/18 |
| `escalation_must_include` | Named fields in `escalation_draft` are present and non-empty | 3/18 |
| `escalation_guide_id` | `escalation_draft.guide_id` matches exactly | 2/18 |
| `message_must_contain` | Every listed term appears (all required, not "any") | 1/18 |

**`expected_outcome` distribution across the set:** 9 `answered`, 3 `escalate`, 3
`needs_clarification`, 3 `out_of_scope`. This isn't balanced by design for its own
sake — it reflects the actual shape of the problem: most requests should resolve, a
meaningful minority should escalate or ask a question, and scope violations should be
rare but must be caught every time.

### Where `small_talk_not_diagnosis` came from

Every other case in this set was written in advance, hypothesizing failure modes.
This one wasn't — it was found live, by a person manually testing the UI, asking "how
are you doing?" and watching the agent break its own tool-calling contract and
escalate a greeting to a human. That's the golden-set sourcing loop this rubric argues
for elsewhere (production behavior → observed failure → labeled case → added to the
set) actually happening once, inside this same build, not just described as a future
practice. See `docs/DECISION_LOG.md` #4 for the full account, including why the
guardrail catching it cleanly wasn't the same thing as the behavior being correct.

### Why substring matching, not a judge, for message content

`message_must_contain_any` and `message_must_not_contain` are blunt instruments —
early iterations of this rubric failed cases where the model used a phrasing outside
the anticipated list (see `docs/DECISION_LOG.md`'s account of `write_request_declined`
and `mixed_scope_request` initially failing on wording, not substance). The fix both
times was broadening the accepted phrase list, not switching to a judge, because the
underlying question ("did it decline the write request") still has an objectively
correct answer — the acceptable-phrasing list is just an imperfect proxy for checking
it deterministically. The known failure mode of this approach is exactly that
brittleness: a correct response can fail the assertion on wording alone. That's an
accepted, documented tradeoff for this prototype, not a hidden gap.

### Why `caveats` and `escalation_draft` are structured fields, not prose to search

`caveats_required` and `escalation_must_include` are checkable *at all* only because
the `respond` tool schema puts uncertainty and escalation content in their own typed
fields, separate from `message`. This is the single design decision that makes the
"conflict & ambiguity" category — the largest category, 8 of 18 cases — assertable
instead of a matter of opinion about whether some sentence "sounds sufficiently
hedged." See `docs/DECISION_LOG.md` #9.

---

## Tier 2: LLM-as-judge (`--judge` flag)

Scores three dimensions, 1-5 each, defined in `evals/run_evals.py`'s `JUDGE_PROMPT`:

| Dimension | 5 means | 1 means |
|---|---|---|
| **Clarity** | A non-technical admin would understand the diagnosis without follow-up questions | Requires jargon knowledge or re-reading to follow |
| **Actionability** | Tells the customer exactly what to do next (or correctly states a human will) | Diagnosis without a next step, or a vague one |
| **Over-claiming** | Every claim is appropriately hedged/sourced given the evidence actually gathered | States things more confidently than the evidence supports |

The judge is Claude Sonnet 5 (same model as the agent — a real limitation, see
Calibration below), given the customer message, the agent's message, and its cited
evidence, and asked for a score plus a one-sentence rationale via structured output
(`output_config.format`, not free text) so scores are always parseable.

**Why exactly these three, and not (for example) "helpfulness" or "tone":**
Clarity and actionability are the two things that determine whether the customer
actually gets unblocked — the product outcome this whole prototype exists to improve.
Over-claiming is the trust-specific dimension: it's the one most likely to produce a
plausible-sounding wrong answer, which is the single highest-impact failure mode named
in the README's risk analysis. A generic "quality" or "helpfulness" score would blur
together things that need different responses (a low-clarity, well-grounded answer
needs different editing than a clear, over-confident one).

### What the judge actually caught (not hypothetical)

While building this, the judge flagged `multiple_root_causes` for over-claiming: the
model stated an unverified causal link between two independently-true findings. That
led to a real system-prompt fix (require independent findings to be reported as
independent unless a tool result directly links them), confirmed by re-running — the
case's score improved and the golden-set average moved. Full account in
`docs/DECISION_LOG.md` #11. This is the argument for having a judge at all: it caught
something the deterministic assertions structurally can't (they check *whether* a
claim exists, not whether it's *appropriately confident*).

### Calibration — the honest gap

**The judge is not calibrated against human labels, and does not gate anything as a
result.** Concretely, that means: no one has yet checked the judge's scores against
what a human reviewer would independently assign to the same transcripts and measured
agreement. Until that's done, a judge score is a signal to look at a transcript, not
evidence of quality on its own — treating an uncalibrated judge as a gate would be
false rigor. The calibration process this needs before it could gate anything:

1. Sample a set of real transcripts (from production traces once they exist, or from
   this golden set today).
2. Have a human independently score the same three dimensions.
3. Compare judge vs. human scores; compute agreement (e.g. within 1 point, or exact
   match rate).
4. Only if agreement is consistently high would the judge's score be trusted to gate a
   release — and even then, spot-check periodically, since judge behavior can drift
   across model versions the same way any other prompted behavior can.

This is also why the judge uses the *same* model family as the agent (Sonnet 5) rather
than a stronger "advisor" model — for a prototype, that's an acceptable shortcut; in
production, using a different (typically more capable) model as judge, and validating
it isn't systematically biased toward its own family's response style, would be part
of the same calibration work.

---

## What's deliberately not evaluated here

- **Numeric/statistical significance of the pass rate.** `evals/run_evals.py --repeat
  N` reports a raw per-case pass rate across N runs; it doesn't compute a confidence
  interval. At 18 cases and small N, that precision wouldn't be meaningful — the
  point of `--repeat` here is to make "was that one run representative?" answerable at
  all, not to produce a publishable statistic.
- **Adversarial coverage beyond one injection vector.** `prompt_injection_in_data`
  tests one specific pattern (an instruction embedded in a guide's description field
  returned by a tool). Passing it is evidence against that pattern, not evidence of
  general robustness against prompt injection — stated plainly in
  `docs/INTERVIEW_QA.md`.
- **Cost/latency as a graded dimension.** Tracked in the trace log (`app/tracing.py`)
  for observability, not asserted against in evals — no case fails for being slow or
  expensive. Worth adding once there's a real latency/cost budget to gate against;
  inventing a threshold now would be arbitrary.
