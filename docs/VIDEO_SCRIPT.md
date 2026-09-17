# Video Script (4-5 minutes)

Tone: a senior PM explaining a product and its tradeoffs, not an engineer narrating a
codebase. Show code only when pointing at a specific decision.

---

### 0:00–0:35 — The problem

"I'm going to walk through a support agent I built for a Pendo-like product-experience
platform — the kind of product where an admin sets up an in-app guide, a walkthrough or
announcement, targeted at some segment of their users.

The support problem: 'my guide isn't showing.' There are about six independent things
that could be wrong — never published, the segment has nobody eligible right now, the
install snippet isn't active, the app stopped sending a metadata field the segment
depends on, a display-frequency limit was already hit. None of that is visible from the
guide editor. Today that's a slow back-and-forth: admin can't tell which one it is,
files a ticket, support asks the same triage questions, 1-3 days for something that's a
config issue most of the time."

### 0:35–1:20 — Product thesis and scope

"My thesis: an agent that can read the actual account data — not just search docs —
cross-reference it against product knowledge, and explain itself with evidence, resolves
most of these in one pass, and makes the rest arrive at a human pre-investigated.

I scoped this narrowly on purpose. I did not try to handle every kind of support
request — I picked this one family and went deep: multi-hop diagnosis, ambiguous
requests, conflicting data, real escalation. Breadth without a way to test correctness
is unfalsifiable. I'd rather show sixteen provably correct behaviors than ten
happy-path demos.

I explicitly did not build: any write action — this agent can diagnose and recommend,
never change a customer's configuration. No real Pendo integration — I don't have
access, so the account data is clearly simulated. No vector database — the doc corpus
is nine short docs I wrote myself; keyword search finds the right one every time. And
no agent framework — the whole loop is about a hundred lines, and I wanted every
decision in it to be something I wrote and can point to, not framework configuration."

### 1:20–1:50 — Architecture

[Show a simple diagram or the README architecture block]

"A static chat page talks to a small FastAPI server. The core is a hand-written agent
loop: Claude calls tools — read the guide, read its segment, check install status,
search docs — and I execute them against simulated account data. The only way the model
can produce a customer-facing message is a `respond` tool with a structured outcome,
evidence list, and a caveats field for uncertainty. That structure is what makes the
evidence panel and my evals possible — outcome and caveats are fields my code can check,
not adjectives buried in a paragraph."

### 1:50–2:50 — Demo 1: diagnosis with a data conflict

[Type or click]: *"The guide page says 1,250 eligible visitors for New User Onboarding,
so why does nobody see it?"*

"Watch what it checks: the guide — published, fine. The segment — live count is zero.
Install status — the app stopped sending a field called plan_tier five days ago, which
the segment rule depends on. It cites the doc that explains that pattern.

And here's the part I actually care about: two real numbers disagree — 1,250 from when
it was published, 0 right now — and it didn't just pick one. It explains why they
differ and flags it as a caveat instead of resolving the discrepancy silently. That's
not a guide-config quirk — that's the same problem an analytics agent has every single
day: two numbers describing 'the same' thing, and the product has to be honest about
which one is authoritative and why."

### 2:50–3:50 — Demo 2: ambiguity and escalation

[Type]: *"my onboarding guide isn't working"*

"Two guides match 'onboarding.' It doesn't guess — it asks which one."

[Confirm, or switch to a healthy guide]

"Now here's a guide where every check comes back clean — published, segment has
visitors, snippet installed. Correct behavior isn't inventing a cause — it's
escalating, with a packet: here's what I already checked, here's what's unresolved. I
confirm it, and that's the only state-changing action in the whole system — the model
drafted, I approved, code created the ticket. No model call in that path at all."

### 3:50–4:30 — Quality

[Run `python evals/run_evals.py` on screen, or show the output]

"A demo working isn't evidence a probabilistic system works. I built sixteen golden
cases with deterministic assertions — not 'does this look good,' but 'did it call the
right tools, cite the right doc, populate caveats when the data was actually stale or
conflicting.' Eight of the sixteen are specifically about ambiguous or conflicting
situations, not the happy path, because that's the harder and more important behavior
to get right. This runs once per case today — the honest next step, which I wrote down,
is running each case N times and gating on a pass rate, because a single run can't tell
you 'wrong' from 'unlucky.'"

### 4:30–5:00 — Production evolution

"What I'd build next, in order: a real client behind these same tool interfaces —
they're shaped so that's a contained swap, not a rewrite. A deterministic health-check
for the single most common cause, once trace data tells me what that actually is,
instead of guessing. And calibrating an LLM judge against human-labeled examples before
I'd trust it to gate anything, not just report a score.

The thing I most want this to demonstrate isn't that I can make an agent call tools —
it's that I know which parts of this needed to be probabilistic, which parts needed to
be a hard rule, and where the line between them actually has to sit."

---

## Recording notes

- Have the server running (`uvicorn server:app --reload`) and the page loaded before
  recording — use the example-prompt buttons for the two demo messages so there's no
  live typing risk.
- Keep the evals segment to a single terminal screenshot/run — don't narrate every line
  of output.
- If time is tight, cut the second half of Demo 2 (the escalation confirm click) rather
  than any of the "why" sections — the judgment is the deliverable, the click is just
  proof it works.
