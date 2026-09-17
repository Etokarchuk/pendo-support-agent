# Likely Interview Questions

Concise, defensible answers grounded in what's actually in this repo. Cross-references
point at [`DECISION_LOG.md`](DECISION_LOG.md) for the fuller argument.

---

**Why does this need an LLM at all? Why not a health-check function?**

For the single most common cause (draft status), a script would in fact be more
reliable and cheaper — I say so directly in the decision log (#1, #6 area). The LLM
earns its place everywhere a fixed decision tree breaks down: interpreting an
ambiguous natural-language request, recognizing when a customer's stated belief
conflicts with the account data, handling two independent root causes in one guide,
and explaining a diagnosis in plain language with cited evidence. A rules engine can't
do the first three without becoming an ever-growing pile of special cases; it can't do
the fourth at all.

**Why is this scoped to one request family instead of general customer service?**

Breadth without a golden set is unfalsifiable — you can't define "correct" for an
open-ended bot. Depth let me write 18 assertable cases instead of demoing happy paths.
It also mirrors a real product tradeoff: a broad agent at 60% accuracy is worse than a
narrow one at 95%, because one confidently wrong answer costs more trust than ten
correct refusals. See Decision Log #2.

**Why read-only? Isn't an agent that can fix the guide more useful?**

More useful, and more dangerous, in that order. The cost of a wrong read is a wasted
tool call; the cost of a wrong write is a customer-visible change to their live
configuration made without their review. I had no way to validate write-safety inside
this timebox, so the answer was to not build write capability rather than build it and
hope. The natural next increment is a *propose*, not *apply*, tool — see Decision Log
#6.

**What stops the model from asserting a config fact the tool didn't return?**

Three layers: (1) the system prompt states the rule explicitly ("every factual claim
about this account must come from a tool result"); (2) the `respond` schema requires an
`evidence[]` array with a `source` for each fact, which the eval runner checks against
which tools were actually called; (3) the golden set has cases built specifically to
catch violations (`tool_error_no_guess` fails if the model claims a segment is healthy
when the lookup errored). None of these make it impossible, which is exactly why the
evals exist — probabilistic systems need continuous checking, not a single clever
prompt.

**Why a hand-written loop instead of a framework (LangChain/LangGraph/Claude Agent
SDK)?**

The loop is ~100 lines, and every one of those lines is a product decision (the
tool_choice strategy, what happens when the model breaks the response contract, the
step cap). In a framework those become configuration and callbacks spread across
layers — I'd be defending the framework's design instead of mine. See Decision Log #3
for the fuller version, including why even the SDK's own lightweight tool-runner
helper was more abstraction than this specific set of decisions needed.

**What would make you switch to a framework?**

Real operational complexity: durable/resumable sessions across process restarts,
human-in-the-loop approval spanning many tools as a general pattern (not the one
escalation step this has), or a team of engineers who'd benefit more from shared
framework conventions than from a bespoke loop they all have to learn. None of that
exists at this scale.

**Why keyword search instead of embeddings or a vector database?**

9 short docs, written by me, for questions I can anticipate the vocabulary of. At that
size, keyword scoring against title/tags/body finds the right doc every time and the
whole scoring function is readable in 30 seconds. A vector index would be solving a
retrieval-quality problem I don't have, at the cost of a dependency I'd then have to
explain. It becomes the right call once the corpus is large, not written by whoever
wrote the queries, or covers vocabulary customers don't share with the docs — see
Decision Log #7.

**Why a forced `tool_choice` and a `respond` tool instead of just letting it answer in
free text?**

`respond` as a tool is what makes the evidence panel and the deterministic evals
possible — `outcome` and `caveats` become structured fields the code and the eval
runner can check, not adjectives buried in prose. Tool choice is forced (`"any"`), not
`"auto"` — that wasn't the first design: `"auto"` plus a prompt instruction was tried
first specifically to avoid depending on forced-tool-choice behavior, but manual
testing found the model breaking that contract twice, in two unrelated ways (small
talk, then a clarifying question), both caught by a fail-closed guardrail but not
actually correct — "escalating" a greeting to a human is a bad outcome even when
nothing crashes. Forcing tool choice removes the failure at its source; I verified
Sonnet 5 supports it before switching. The guardrail stays regardless — it's insurance
against whatever the next undiscovered pattern turns out to be, not a fix for this one
specifically. See Decision Log #4 for the full before/after account.

**What happens when `get_segment` times out or the tool call fails?**

The executor returns a structured error dict instead of raising; the agent loop marks
the corresponding `tool_result` as `is_error: true`. The system prompt instructs the
model to state plainly what it couldn't verify rather than guess, and reflect that in
`caveats`. The golden case `tool_error_no_guess` (segment SEG-99, simulated timeout)
asserts exactly this: the model must not claim the segment is empty or healthy, and
must escalate with the failed check named. What it does *not* do yet: retries or
circuit-breaking at the tool layer — a single simulated failure is enough to prove the
behavior, not to prove resilience under real failure rates.

**What happens when the tool returns wrong data (not an error, just incorrect)?**

Not something this prototype can detect — a tool result is trusted as ground truth once
it returns successfully. In production this is exactly why the *source* of that data
(a real Pendo-like backend) needs its own reliability guarantees; the agent's grounding
discipline only protects against the model inventing facts, not against the system of
record itself being wrong.

**Your evals ran once — how do you handle non-determinism?**

I don't, yet, and I say so directly in the decision log (#11) and the eval runner's own
docstring. A single run can't distinguish "actually wrong" from "unlucky this run." The
honest next step is running each case N times, tracking a pass *rate*, and gating on a
threshold — investigating flaky cases individually instead of re-running until green.

**What goes in the golden set, and where would it come from in production?**

Here: hand-authored, covering the diagnosis paths, the ambiguous/conflicting-data
cases, escalation, and scope/safety. In production: frequent request patterns from the
trace log, cases built from actual wrong answers once observed, high-cost mistake
categories, and adversarial cases from support-agent feedback — the loop is production
behavior → a failure gets noticed → it's labeled and added to the set → future changes
are evaluated against it before release → observe again.

**When would you use LLM-as-judge, and how do you know the judge is right?**

For exactly the things that don't have an objectively checkable answer — here, that's
explanation clarity and whether the model over-claims relative to its evidence, which
is why `--judge` scores those and nothing else. It's non-gating in this prototype
because I haven't calibrated it against human labels; an uncalibrated judge deciding
pass/fail is false confidence dressed as rigor. I'd calibrate by having a person score a
sample the judge also scored, checking agreement, and only trusting it for gating once
that agreement is established and monitored over time.

**What's your biggest customer risk?**

A confidently wrong diagnosis — the model asserting something false about the
customer's specific account with enough authority that they act on it or stop trusting
the system. Every major design choice (tool-only facts, evidence citations, the
precedence rule, the caveats field, the golden set) exists to suppress this one risk
specifically, because it's the one that's both plausible and expensive.

**What's your biggest technical risk?**

Prompt-driven behavior (the grounding rules, the precedence rule, the escalation
criteria) is enforced by instructions the model could in principle drift from as models
change or under adversarial pressure — the golden set is the safety net, but it's 18
cases, not exhaustive. The `prompt_injection_in_data` case tests one specific
adversarial vector (an instruction embedded in a guide's own description field) and
passes today; I wouldn't claim it generalizes to every injection strategy.

**What assumption in your prototype are you least confident about?**

That keyword search stays sufficient — it's the piece most likely to look
under-engineered to an ML-fluent reviewer even though I think it's the right call at
this corpus size. Close second: that a single fixed precedence rule ("live beats
snapshot beats customer belief") is the right call for every kind of data conflict this
system will ever see, rather than just the ones I designed fixtures for.

**How does this change at 100x scale?**

Real backend behind the same tool interfaces (contained change per Decision Log #5); a
database for sessions/tickets (#8, the first infra investment, ahead of most others,
because production can't lose an in-flight conversation); N-run evals with a
pass-rate gate and an ongoing golden-set pipeline (#11); tenant-scoped auth so tool
calls can't be tricked into crossing accounts; likely the deterministic health-check
for the top symptom once trace data shows its actual frequency (#1).

**What would you build with one more week?**

The deterministic top-symptom health-check informed by real trace data, tenant-scoped
auth, and calibrating the LLM judge against a small set of human-labeled transcripts so
it could start gating on explanation quality, not just structural correctness.

**What would you absolutely not build next?**

A second agent, or a framework migration. Neither addresses the actual remaining risk
(evaluation rigor and a real data source), and both would add coordination and failure
surface for a system that's still single-purpose enough not to need them.

**How does this relate to the actual Analytics Agent problem?**

Directly — "two numbers describing the same thing disagree, which one does the customer
see, and how do we explain the discrepancy instead of picking one silently" is the same
shape as the `conflicting_counts` and `stale_segment_estimate` cases here, just in a
guide-config domain instead of a metrics domain. The mechanism I'd carry over most
directly is the structured `caveats[]` field and the deterministic precedence rule
(Decision Log #9, #10) — treating "is this number stale/partial/estimated" as a
first-class, assertable field rather than something buried in a sentence of hedging.
