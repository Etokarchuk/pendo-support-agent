# Video Script

Tone: a senior PM explaining a product and its tradeoffs, not an engineer narrating a
codebase. Show code only when pointing at a specific decision. Plain language over
jargon — if a line needs a technical term, explain what it does before using it.
Timestamps are guidance, not a strict script.

**Length note:** this version runs ~7:35-7:50, longer than the original 4-5 minute
target. All four demo interactions are a deliberate, final decision to keep live —
see the bottom of this file for the actual estimate and remaining narration-only
trim options, which now land closer to 6:00-6:30 than 5:00.

---

### 0:00–1:00 — The problem (lead with the customer — mine)

"I picked this problem because I've lived it. I use Pendo, and more than once I've set
up an in-app guide that just didn't show up, with no idea why — ending in a support
ticket and a call with one of their engineers just to track down the config issue.
Real time spent on what turned out to be a five-minute fix.

I also stayed in this domain because it's the same product from my product-sense
interview for this role — a real continuation, not a random pick.

Now generalize that: imagine you're a PM or admin at a B2B SaaS company, and you just
built an in-app guide to onboard new trial users. A day later — nobody's using it,
why? There are roughly six reasons a guide might not show — unpublished, an empty
audience, a broken snippet, a missing metadata field — none visible from the guide
editor. It becomes a ticket, support asks what you can't answer, and days pass to fix
a five-minute issue. That gap is what I chose to solve."

### 1:00–1:15 — Product thesis

"My bet: an agent that reads the specific guide, its segment, its install status,
cross-references that against how the product actually works, and explains itself
with evidence — resolves most of these in one pass, and hands the rest to a human
already investigated."

### 1:15–2:00 — Scope discipline

"I scoped this narrowly — one request family, deep, not ten done shallow, since
breadth without a way to test correctness is unfalsifiable. I also skipped a real
Pendo integration, since I don't have access, and a vector database, since nine short
docs don't need one.

One more deliberate choice: no LangChain, no LangGraph, no agent framework at all.
The whole loop is about a hundred lines of plain code calling the Anthropic API
directly. Every decision in it — how tool calls get forced, what happens when the
model breaks its own contract — is something I wrote and can point to, not framework
configuration I'd have to explain secondhand. I'd reach for a framework at real
operational complexity — durable sessions, a team sharing conventions — neither of
which exists at this scale."

### 2:00–2:55 — Architecture, in plain terms

[Show the README architecture diagram]

"First, the data. Everything the agent reads about an account is simulated — I don't
have Pendo access, so I built a fixture file modeled on Pendo's real concepts. Guides,
each with a publish status and a segment they're targeted to. Segments, each with a
targeting rule and a live visitor count. Install status — whether the tracking
snippet is active in an app, and which visitor fields it's actually sending. The
agent reads this through a handful of read-only tools: look up a guide, look up its
segment, check install status, search the product docs. There's no write tool at
all — it can diagnose, but it can never touch a customer's actual configuration.

Now the answer side. The model can't just reply with a paragraph of text — every
answer comes back in one fixed format: a label for what happened, the specific facts
it used and where each came from, and a field for anything it's not fully sure about.
Because that format is fixed, my code and my tests can actually check it — did it
cite a real source, did it flag shaky data — not me reading a paragraph and guessing
whether it sounds trustworthy."

### 2:55–3:40 — Demo 1: diagnosis with a data conflict

[Click the example]: *"The guide page says 1,250 eligible visitors for New User
Onboarding, so why does nobody see it?"*

"Watch what it checks: guide published, fine. Segment live count, zero. Install
status — the app stopped sending `plan_tier` five days ago, which the segment rule
depends on. It cites the doc for that pattern.

Here's the part I care about: two numbers disagree — 1,250 at publish, 0 now — and it
explains why instead of picking one. This is the same problem an analytics agent
hits constantly: two numbers describing the same thing, and the product has to be
honest about which one's right, and why."

### 3:40–4:50 — Demo 2: trust and guardrails

"Three more behaviors matter as much as the diagnosis: an ambiguous question, an
out-of-scope one, and a real dead end.

[Click]: *"my onboarding guide isn't working"* — two guides match. It asks which one
instead of guessing.

[Click]: *"I want a refund for this month"* — billing isn't something this agent
touches. It says so, without touching any account data.

[Click]: *"why isn't Dashboards Launch Announcement showing to more people?"* — every
check comes back clean on this one. So it escalates, with a packet of what's already
been checked and what's still unresolved. I confirm it — the only state-changing
action in the whole system. The model drafted, I approved, code created the ticket."

### 4:50–5:25 — Quality

[No live run — stay on the ticket-confirmation screen from Demo 2, or cut to a quick
shot of `evals/golden_cases.json` in an editor. Not shown on screen: narrate only and
point to the repo, per the decision to save the live eval run for the repo docs
rather than screen time.]

"A demo working isn't evidence a probabilistic system works. I built eighteen golden
cases with deterministic assertions — right tool, right doc, a caveat populated when
data was stale or conflicting — they're in `evals/golden_cases.json` if you want the
exact transcripts. Eight are specifically about ambiguous or conflicting situations,
the harder behavior to get right. This runs once per case today; the honest next step
is running each N times and gating on a pass rate — a single run can't tell 'wrong'
from 'unlucky,' which I learned the hard way building this. Full rubric's in
`docs/EVAL_RUBRIC.md`.

One more honest note: I also built an optional LLM judge, to score things like
clarity and over-claiming that don't have a single correct answer. At eighteen cases
I didn't actually need it — reading the transcripts myself would have caught the same
issues for free. I kept it because it's non-gating, and it's how I'd approach this at
real production scale, once reading every conversation by hand stops being possible."

### 5:45–6:20 — Production evolution and close

"What I'd build next: a real client behind these tool interfaces, shaped so that's a
swap not a rewrite; a deterministic check for the top cause, once trace data tells me
what that is; and calibrating the judge against human labels before trusting it beyond
a score.

The real test here was knowing which parts needed to be probabilistic, which needed a
hard rule, and where that line actually sits — not whether I could make an agent call
tools."

---

## Length estimate and trim guide

**Spoken narration is 1,011 words, about 6:44 at 150 words/minute** — before adding
demo click/wait time. Demo 2 has three exchanges, Demo 1 has one, and the escalation
confirm is a fourth click — each a real API call (5-15s) — call it another 50-65
seconds of silent wait/click time. Realistic total recorded time is **~7:35-7:50**.

**Decision made: all four demo interactions stay live** — that's the actual proof
this works, and it's the right call to protect. The evals section was moved from a
live/screenshotted run to narration-only, pointing at `docs/EVAL_RUBRIC.md` and
`evals/golden_cases.json` for anyone who wants the detail — the repo carries what the
video doesn't have to.

With demos off the table, the only remaining lever is narration length in the
non-demo sections:
1. **Architecture** (201 spoken words) is now the longest non-demo section. Both
   halves — what the data is, and the response-format explanation — could lose
   roughly a third each without losing the point, since the full detail is already
   in the README.
2. **Quality** (168 spoken words) — the judge caveat and the golden-set breakdown
   could tighten, pointing harder at the repo instead of narrating the detail live.
3. **Scope discipline** (135 spoken words) — the LangChain paragraph could drop to
   one sentence: "No LangChain or agent framework — the loop's about a hundred
   lines, every decision in it mine to explain, not framework config."

Trimming those three by roughly a third each saves somewhere around 60-90 seconds of
narration — landing near **6:15-6:30** rather than 5:00. Given the demos alone (4
live interactions, ~50-65s of wait time plus their narration) already account for a
meaningful chunk of the runtime, 5:00 flat may no longer be realistic without cutting
a demo — worth deciding whether ~6:00-6:30 is an acceptable final target instead of
continuing to chase 5:00 exactly.

## Recording notes

- Have the server running (`uvicorn server:app --reload`) and the page loaded before
  recording. The page opens with a short welcome message instead of blank — let it
  render before narrating over it, or narrate the problem while it's visible in the
  background.
- Every demo message in this script (1,250 eligible visitors / my onboarding guide
  isn't working / I want a refund / Dashboards Launch Announcement) is a clickable
  example button in the UI — no live typing risk. All four are shown live, on
  purpose — nothing in the demo sections is narrate-only.
- The evals section is narrate-only, deliberately — no terminal run, no screenshot.
  Stay on the previous screen (the ticket confirmation) while narrating it, or cut to
  a quick shot of `evals/golden_cases.json`. The depth lives in `docs/EVAL_RUBRIC.md`
  and `docs/DECISION_LOG.md`, not on screen.
