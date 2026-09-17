# Decision Log

Major decisions, in the order they'd come up if you were building this. Each one
states what I chose, why, what I considered instead, what it cost, and whether it
survives to production.

---

## 1. Scenario: diagnostic support for a Pendo-like in-app guide product

**Decision:** Build a support agent for "why isn't my guide showing," not a generic
customer-service bot, and not a Klaviyo-specific scenario.

**Why:** The assignment rewards a narrow, real problem over broad coverage. This one
has the same shape as the role's actual problem — reasoning over authoritative,
fetched account data rather than being a chat skin over an FAQ — which is the
strongest signal I can send about fit.

**Alternative considered:** DTC post-purchase support (order lookup / returns /
refunds). Also a real problem, more universally legible in a 5-minute video, but the
central interesting decision there is autonomy over money-adjacent writes, and most of
the flow is deterministic policy — the LLM's marginal value is lower.

**Tradeoff:** costs ~15 seconds of domain framing in the video for an audience that
may not know Pendo. Buys a problem where multi-hop tool reasoning and "what happens
when the model doesn't have enough evidence" are the actual central questions, not an
afterthought.

**Production implication:** N/A — this decision is about what to build for the
assessment, not a production tradeoff.

---

## 2. Narrow request family, not "any customer service request"

**Decision:** The agent handles guide-diagnosis requests deeply (multi-hop, ambiguity,
conflicting data, escalation) rather than a shallow slice of many request types.

**Why:** "Handles customer service requests" invites breadth; breadth without a
golden set is unfalsifiable — you can't define "correct" for an open-ended bot, so
quality collapses to vibes. Depth lets me write 16 assertable golden cases instead of
demoing ten happy paths. It also mirrors the real tradeoff a support product has to
make: a broad agent at 60% accuracy is worse than a narrow one at 95%, because one
confidently wrong answer costs more trust than ten correct "I can't help with that."

**Alternative considered:** A shallower agent covering guide diagnosis + billing FAQ +
account settings how-to. Would look more like "handles customer service" on the
surface. Rejected because none of those would get more than a couple of untestable
happy-path turns in a 2-hour build, and the trust/evidence/escalation machinery — the
actual point — would be thin everywhere instead of solid somewhere.

**Tradeoff:** the demo needs ~15 seconds explaining why the scope is narrow. Buys a
system where every claimed behavior has a golden case behind it.

**Production implication:** the architecture (tools, `respond` contract, evidence
panel, eval runner) doesn't change to add the next request family — it's a new tool,
new fixtures, a couple of new docs, and new golden cases. The marginal cost of breadth
is data, not architecture. Real breadth in production should be sequenced by traced
symptom frequency, not guessed upfront.

---

## 3. Hand-written agent loop, no framework

**Decision:** `app/agent.py` is a plain `for` loop calling the Anthropic Messages API
directly — no LangChain, LangGraph, Claude Agent SDK, Vercel AI SDK, or even the
Anthropic SDK's own beta tool-runner helper.

**Why:** every product decision I want to defend — tool_choice strategy, the
fail-closed behavior when the model breaks the response contract, the step cap, how
tool errors are surfaced — is a few lines of this loop. In a framework those become
configuration and callbacks spread across layers; I'd be explaining the framework's
design instead of mine. The loop is ~100 lines; this is squarely in "reasonably fits
in scratch" territory per the recruiter's guidance, unlike re-implementing the HTTP
client or JSON schema validation, which the Anthropic SDK already provides and which I
did *not* rebuild.

**Alternative considered:** the Anthropic SDK's `tool_runner` (beta) — much smaller
concession than a full framework, since it's still "your tools, your logic," just
without hand-writing the `while` loop. I stayed manual anyway because the two
behaviors I most wanted visible — the fail-closed contract-violation handling and the
step cap — are exactly the code the runner would have absorbed.

**Tradeoff:** no streaming, no built-in retries/checkpointing, no tracing UI. I
accepted a synchronous request/response chat and a hand-rolled JSONL trace instead.

**Production implication:** would reconsider at real operational complexity —
durable/resumable sessions, human-in-the-loop across many tools, or a team of
engineers who benefit from shared framework conventions more than from a bespoke loop.
None of that exists at this scale. See Q&A doc for the deeper version of this
argument, including "why not LangGraph specifically."

---

## 4. `tool_choice: "auto"` + strict schemas + a `respond` tool, not forced `"any"`

**Decision:** Every tool call is optional per the API (`tool_choice: auto`); the
contract "always end by calling `respond`" is enforced by the system prompt and by
code that treats a tool-less turn as a failure, not by forcing tool use at the API
level.

**Why:** this avoids depending on forced-tool-choice semantics being available and
stable across models, while `strict: true` on every schema still guarantees
schema-valid arguments whenever a tool *is* called. The cost is a code-level guardrail
requiring a fallback path — which I wanted anyway, because "the model didn't follow
instructions" needs to fail closed for a customer-facing agent regardless of how tool
choice is configured.

**Alternative considered:** forcing tool use every turn. Simpler in principle, but
makes the fallback path (`_contract_violation_result`) untested by construction, which
is exactly the path I most want to have proven out for a trust-sensitive prototype.

**Tradeoff:** a small amount of possible waste if the model occasionally ends a turn
without a tool call for a benign reason — in practice this hasn't been observed in
testing, and the fallback (escalate, not a broken UI) is an acceptable failure mode
either way.

**Production implication:** keep the guardrail regardless of `tool_choice` strategy —
it's cheap insurance for a customer-facing surface.

---

## 5. Fixtures instead of a real Pendo integration

**Decision:** `data/fixtures.json` is hand-authored, simulated account data modeled on
Pendo's public concepts (guides, segments, install snippet, visitor metadata), clearly
labeled as such throughout the repo and UI.

**Why:** no Pendo account was available for this assessment, and — more importantly —
fixtures let me *construct* the exact failure scenarios the golden set needs (a
segment that errors, one that's stale relative to a rule change, two guides with
overlapping names) on demand. A real account wouldn't reliably produce these states
for a demo, and building a real integration would spend the 2-hour budget on plumbing
that doesn't change any of the decisions being evaluated.

**Alternative considered:** skip account-specific data and build a doc-only Q&A bot.
Rejected — it would remove exactly the part of the problem (authoritative data
grounding, conflicting sources, escalation with evidence) that mirrors the real role.

**Tradeoff:** the diagnosis quality shown is only as good as fixture design, and can't
show real-world data messiness (partial records, latency, rate limits) beyond what I
hand-authored.

**Production implication:** the tool function signatures (`get_guide(name_or_id)`,
`get_segment(segment_id)`, `get_install_status(app_id)`) are written the way a real
API client's methods would look, specifically so replacing the fixture-backed bodies
with real HTTP calls is a contained change to `app/tools.py`, not a rewrite of
`app/agent.py` or the tool schemas.

---

## 6. Read-only tools; no write actions

**Decision:** there is no tool that can publish a guide, edit a segment, or change any
account setting. This isn't a missing feature — the system prompt explicitly instructs
the model to decline and explain when asked.

**Why:** the cost of a wrong read is a wasted API call; the cost of a wrong write is a
customer-visible, possibly hard-to-notice change to their live configuration made
without their review. Given real budget constraints and no ability to validate write
safety within a 2-hour build, the answer is to not build write capability at all,
rather than build it and hope the guardrails hold.

**Alternative considered:** a "propose a fix" tool that stages a change for the
customer to approve (not applies it directly). Genuinely reasonable for a future
iteration, but adds a state-changing surface and its own trust design (staged-change
review UX, expiry, audit trail) that would have consumed the time better spent on the
diagnosis and evaluation quality that's actually being evaluated here.

**Tradeoff:** the agent can't close the loop by itself even for a guide it's certain is
in draft — the customer or an admin has to take the last step.

**Production implication:** the natural next increment is exactly the "propose, don't
apply" tool above, gated by role/permission checks that don't exist yet.

---

## 7. Keyword search over the doc corpus, not embeddings/a vector DB

**Decision:** `app/knowledge.py` scores docs by term overlap against title, tags, and
body — no embeddings, no vector store.

**Why:** the corpus is 9 short, hand-curated docs I wrote myself, so I control the
vocabulary overlap between how customers phrase questions and how the docs are
written. At this size and this level of curation, keyword scoring finds the right doc
every time and is trivially inspectable — you can read the whole scoring function in
30 seconds.

**Alternative considered:** semantic/vector search. Would matter once the corpus is
large, not written by the same person who wrote the queries, or covers a broader
vocabulary than customers use — none of which is true here. Adding it now would be
technology for its own sake, not a response to an actual retrieval failure.

**Tradeoff:** would degrade if the corpus grew to hundreds of docs with more varied
terminology, or if customer phrasing diverged further from doc language.

**Production implication:** replace `search_docs`'s body with a call to the real
help-center search API (which Pendo, like most support products, already has) or a
semantic index once the corpus outgrows curation — the tool's interface to the agent
loop doesn't need to change either way.

---

## 8. No database; in-memory sessions, a JSON ticket file

**Decision:** session state lives in a process-local dict; tickets are appended to
`data/tickets.json`. Nothing survives a server restart except tickets.

**Why:** no demonstrated product behavior in this prototype needs state to survive a
restart or be shared across instances. A hosted DB would be infrastructure with no
behavior it enables here — the honest test is "what would break in the demo without
it," and the answer is nothing.

**Alternative considered:** Supabase/Postgres for sessions and tickets. Would matter
for multi-instance deployment, session durability across restarts, or querying
historical tickets — none of which this prototype needs to show.

**Tradeoff:** a server restart loses in-flight conversations (acceptable for a local
demo) — tickets persist across restarts since they're a file, but not across
environments.

**Production implication:** first real infrastructure investment, ahead of most other
items on this list, because production literally cannot lose a customer's
conversation mid-diagnosis or a support ticket. Straightforward swap: a real datastore
behind the same session/ticket read/write calls.

---

## 9. Structured `caveats[]` field for uncertainty, not prose hedging

**Decision:** the `respond` tool schema has a dedicated `caveats` array, separate from
`message`, for data-quality flags (stale estimate, conflicting sources, an unverifiable
check).

**Why:** "communicate uncertainty" is easy to claim and hard to verify if it just means
the model sometimes writes "it's possible that..." in prose. Making it a structured
field means the eval runner can assert it's non-empty exactly when it should be
(`caveats_required` on 3 golden cases), and the UI can render it as a visually distinct
block instead of it disappearing into paragraph text.

**Alternative considered:** rely on prompt instructions alone and grade hedging
language with an LLM judge. Rejected as the primary mechanism — it would make the
single most safety-relevant behavior in this whole system the one thing evals can't
check deterministically.

**Tradeoff:** one more field for the model to fill in correctly every turn; occasional
over- or under-population is possible and is exactly what the golden set is designed to
catch.

**Production implication:** this pattern — safety-relevant behavior as a structured,
assertable field rather than free text — is the single idea from this prototype I'd
most want to carry into a production analytics agent, where "is this number stale/
partial/estimated" is at least as important as it is here.

---

## 10. Deterministic source-of-truth precedence when data disagrees

**Decision:** the system prompt states a fixed rule — a live tool result outranks a
publish-time snapshot, which outranks the customer's stated belief — rather than
leaving it to the model to decide case by case which source to trust.

**Why:** *whether* two sources disagree is exactly the kind of judgment an LLM should
make (it requires reading and comparing specific values). *Which one wins* should not
vary run to run for the same conflict — that would make the product feel arbitrary in
exactly the situation where it most needs to feel trustworthy. So the precedence rule
is deterministic policy; only the detection of the conflict and the explanation of it
are left to the model.

**Alternative considered:** let the model reason about precedence freely per situation.
Rejected — it's the kind of decision that should be consistent by design, not by luck,
especially because it's directly analogous to the real Analytics Agent problem
(multiple numbers describing "the same" metric, needing a consistent story about which
one is authoritative and why).

**Tradeoff:** the precedence rule is a blunt instrument — real disagreements might
occasionally warrant a different resolution than "live beats snapshot beats customer
belief." I judged consistency more valuable than per-case optimality for a first
version.

**Production implication:** this precedence policy would need product review (which
source really should win, in which situations) the same way a real Analytics Agent's
"which number does the UI show" logic would.

---

## 11. Single eval run per case, deterministic assertions, non-gating judge

**Decision:** `evals/run_evals.py` runs each of 16 golden cases once, asserts
structured outcomes deterministically, and only optionally adds an LLM-judge quality
score that never gates pass/fail.

**Why:** "it worked in my demo" isn't evidence a probabilistic system works — a fixed,
versioned golden set that asserts on structured fields (outcome, tools called,
evidence citations, caveat presence) is the minimum credible substitute inside a 2-hour
build. The judge is reported, not gating, because judge calibration against human
labels hasn't happened yet — an uncalibrated judge deciding pass/fail would be false
confidence dressed as rigor.

**Alternative considered:** LLM-judge-as-primary-gate for response quality. Rejected
for this prototype specifically because none of the golden cases actually need
subjective grading — every one of them has an objectively checkable answer (an
outcome, a tool call, a cited doc, a non-empty caveat list). Reserve the judge for
what's genuinely subjective (is the explanation clear).

**Tradeoff:** a single run can't distinguish "the model is wrong" from "the model got
unlucky this run" — real non-determinism is invisible with N=1. This isn't
hypothetical: while building this, the judge's `over_claiming` score for the same case
(`empty_segment_diagnosis`, unchanged code and fixtures) swung 4 → 2 → 5 across three
consecutive runs. The 2 led me to a real fix (see below) — but the swing back to 5 on
identical inputs is exactly the N=1 problem, and it's not only generation variance;
the *judge's own scoring* is probabilistic too, which a production eval would need to
account for (e.g. averaging judge scores per case, not trusting a single judge call).
One genuine finding this did surface: the judge flagged a case (`multiple_root_causes`)
where the model stated an unverified causal link between two independently-true
findings ("the empty segment is consistent with the snippet outage... may resolve
itself"), which the tool data never actually established. I tightened the system
prompt to require independent findings be reported as independent unless a tool result
directly links them, and confirmed the fix with a re-run (16/16 still passed, that
case's score improved and the golden-set average over_claiming moved from 4.1 to 4.4)
— a small, real example of the intended quality loop, not just a passing score.

**Production implication:** run each case N times, track a pass **rate**, gate on a
threshold, investigate flaky cases individually rather than re-running until green.
Source the golden set on an ongoing basis from production escalations, support-agent
feedback on wrong answers, and known failure modes — not just hand-authored cases like
this one.
