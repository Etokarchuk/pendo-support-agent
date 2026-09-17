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
quality collapses to vibes. Depth lets me write 17 assertable golden cases instead of
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

## 4. Forced `tool_choice: "any"`, strict schemas, a `respond` tool — reversed from `"auto"` based on real testing

**Decision:** Every model call forces `tool_choice: {"type": "any"}` — the model must
call some tool every turn, ending with `respond`. This is a reversal from the initial
design (`"auto"` plus a prompt instruction), made because real testing, not
speculation, showed `"auto"` wasn't reliable enough.

**Why the initial choice, and why it changed:** `"auto"` was chosen first specifically
to avoid depending on forced-tool-choice behavior being available and stable across
model versions (a real, documented constraint on some models). The theory was that
`strict: true` schemas plus an explicit system-prompt instruction ("call `respond`
exactly once, as your last action") would be enough, backed by a code-level guardrail
for the rare case it wasn't.

That guardrail then did its job for real, twice, during manual UI testing — and both
times revealed the same underlying problem. A customer typed "how are you doing?" and
the model replied in plain text instead of calling `respond`; another typed "My guide
is not showing" and the model wrote its clarifying question ("which guide do you
mean?") as plain conversational text instead of calling `respond(outcome=
"needs_clarification", ...)`. In both cases the guardrail caught the contract
violation and returned a clean fail-closed `escalate` response instead of a crash or
raw ungoverned text — but "escalating a greeting to a human" is a jarring, wrong
product outcome, not just an internal near-miss. A caught contract violation isn't the
same thing as correct behavior.

The first instinct was to patch the prompt for each scenario as it was found (and that
did work for both, confirmed by repeated re-testing) — but finding the *same*
underlying failure via two unrelated conversational patterns in one afternoon of
manual testing was the signal that this was systemic, not two unrelated edge cases:
whenever the model's natural inclination was to produce something that felt like an
ordinary conversational reply, it sometimes skipped the tool-call contract regardless
of how the prompt was worded. At that point, continuing to patch prompt wording for
each new "feels conversational" scenario as it was discovered would have been chasing
a symptom. Forcing `tool_choice: "any"` removes the failure mode at its source instead
of only catching it after the fact — verified empirically that Sonnet 5 supports
forced tool choice without error before switching (the model-compatibility concern
that motivated "auto" in the first place applies to a narrower set of newer models,
not this one).

**Alternative considered:** keep `"auto"` and keep patching the prompt per scenario.
Rejected once the pattern repeated — see above. Two golden cases now exist
specifically because of this (`small_talk_not_diagnosis`, `clarifying_question_not_
diagnosis`), both re-verified clean under forced `tool_choice`.

**Tradeoff:** forcing tool use removes the model's ability to ever answer with a bare
`end_turn` — which is exactly the point, since this agent should never do that — at
the cost of one degree of flexibility a more open-ended assistant might want. The
fail-closed guardrail (`_contract_violation_result`) stays regardless: forcing tool
choice doesn't protect against an API failure, a step-cap timeout, or a future model
swap that doesn't support forced tool choice the same way — it removes one specific,
now-verified failure mode, not the entire category.

**Production implication:** keep the guardrail regardless of `tool_choice` strategy —
it's cheap insurance for a customer-facing surface, and this incident is exactly why:
even the "fixed" version needs a safety net for whatever the *next* undiscovered
pattern turns out to be. Re-verify forced tool_choice support explicitly on any future
model swap rather than assuming it carries over — this skill's own documentation notes
newer model families (Claude Fable 5.1 at the time of writing) have already dropped
support for it.

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

*(See [`EVAL_RUBRIC.md`](EVAL_RUBRIC.md) for the full rubric definition — what each
assertion type checks, the complete judge criteria, and the calibration gap. This
entry covers the decision to split evaluation this way; that doc covers the rubric
itself.)*

**Decision:** `evals/run_evals.py` runs each of 17 golden cases once, asserts
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
hypothetical, and building this surfaced two distinct real examples of it:

1. **Generation and judge variance.** The judge's `over_claiming` score for the same
   case (`empty_segment_diagnosis`, unchanged code and fixtures) swung 4 → 2 → 5 across
   three consecutive clean runs. The 2 led me to inspect the transcript and led to a
   real fix: the judge separately flagged `multiple_root_causes` for an unverified
   causal link the model stated between two independently-true findings ("the empty
   segment is consistent with the snippet outage... may resolve itself"), which the
   tool data never actually established. I tightened the system prompt to require
   independent findings be reported as independent unless a tool result directly links
   them, and confirmed with a re-run (16/16 still passed, that case's judge score
   improved, golden-set average `over_claiming` moved 4.1 → 4.4). That's the intended
   quality loop actually happening, not just a passing score. Separately, the swing
   back to 5 on identical inputs is the N=1 problem in its purest form — and it's not
   only generation variance, the *judge's own scoring* is probabilistic too, which a
   production eval would need to account for (e.g. averaging judge scores per case).
2. **A real external failure, not generation noise.** Later in the same session, the
   API key's credit balance ran out mid-testing. Pass rate degraded gradually (16/16 →
   13/16 → 14/16 → 15/16) as calls started intermittently failing before failing
   outright — which looked exactly like generation variance until I inspected the
   actual failures and found `anthropic.APIError: ...credit balance is too low...`. I
   don't want to conflate these two things: the judge-score swing above is real
   sampling variance in the model and the judge; the later degradation was an
   unrelated infrastructure failure. Both are real, and a single pass/fail number
   can't tell them apart — which is exactly the point. This also ended up being an
   unplanned, successful stress test of the fail-closed API-error guardrail added
   after this section was first written (#4's contract-violation path, extended to
   cover the API call itself): every failed call degraded to a clean `escalate`
   outcome with the real cause in an internal caveat, never a raw 500 to the customer.

`evals/run_evals.py --repeat N` exists specifically to make this measurable instead of
argued about — it runs the whole golden set N times and reports a per-case pass rate,
rather than the single-run pass/fail default. It's a small addition, not the full
production version (no threshold gate, no run history), but it's real and running,
not just described.

**Production implication:** run each case N times, track a pass **rate**, gate on a
threshold, investigate flaky cases individually rather than re-running until green.
Source the golden set on an ongoing basis from production escalations, support-agent
feedback on wrong answers, and known failure modes — not just hand-authored cases like
this one.

---

## 12. `respond` schema field order, and a worked example, to fix an outcome/content decoupling

**Decision:** the `respond` tool's JSON schema generates `evidence`, `caveats`, and
`escalation_draft` before `outcome` (previously `outcome` was first); the escalation
rule in the system prompt now includes one concrete worked example, not just the
abstract rule.

**Why:** live testing found a precise, reproducible bug — the model would correctly
recognize a case needed escalation (filling `escalation_draft` completely and
accurately) while leaving `outcome` set to `"answered"`. Since tool-call JSON is
generated as one continuous token stream with no revision, and `outcome` was the
*first* field in the schema, the model was committing to a label before it had
articulated the reasoning that would have changed that label. Moving `outcome` to be
generated last measurably fixed one case (`tool_error_no_guess`: unreliable → 100%
correct across repeated testing) but only partially fixed another
(`healthy_guide_escalate`: went from 0/2 to 4/6). The remaining gap closed after
adding one concrete worked example mirroring that exact scenario (6/6 after). The
abstract rule alone wasn't enough for a judgment this inferential — no crisp signal
like a tool error to hang the decision on, and the customer's own words ("everything
looks fine on our end") plausibly nudged the model toward a reassuring framing.

**Alternative considered:** keep iterating on rule wording alone. Rejected once field
order was identified as a likely mechanistic cause — a structural fix beats another
round of prompt-wording tweaks when there's a concrete reason to expect it will
generalize better.

**Tradeoff:** none identified — this is a pure reliability improvement with no
observed downside, verified by re-running the full golden set (no regressions).

**Production implication:** field order in a structured-output schema is a real,
underappreciated lever for output reliability, not just a stylistic choice — put
fields that inform a judgment before the field that states the judgment.

---

## 13. Prompt caching on the system prompt + tool schemas

**Decision:** the system prompt (rendered together with the static `TOOL_SCHEMAS`,
per the API's tools → system → messages render order) carries a `cache_control:
{"type": "ephemeral"}` breakpoint.

**Why:** both are fully static within this single-account prototype — the system
prompt only varies by account name/ID, and there's one account. Every multi-step
customer turn (typically 2-5 model calls) was paying full input-token price for the
same ~2K-token prefix on every step. This wasn't in the original build because a
single quick manual test doesn't surface a caching gap — it took a real cost
concern (see below) to prompt checking for it.

**Verified, not assumed:** a single live call showed the pattern directly — step 1 of
a 3-step turn wrote ~5,000 tokens to cache; steps 2 and 3 read that same ~5,000 tokens
from cache instead of paying input price for them again.

**Production implication:** this is the correct, minimal caching strategy for this
prototype's shape (one account, static prompt/tools). Production would extend it if
the system prompt ever varies per request (e.g., per-tenant instructions) — the fix
there is a stable *shared* prefix with cache_control, with per-tenant content appended
after the breakpoint, not caching abandoned altogether.
