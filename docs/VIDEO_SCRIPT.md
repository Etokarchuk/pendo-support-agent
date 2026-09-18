# Video Script (4-5 minutes)

Tone: a senior PM explaining a product and its tradeoffs, not an engineer narrating a
codebase. Show code only when pointing at a specific decision. ~725 words / ~4:50 of
narration — timestamps below are guidance, not a strict script; the priority is
leading with the customer's situation, not the artifact. The two demo sections
involve real API calls (5-15s each), so actual recorded runtime will land a bit past
the pure-narration estimate — that's expected, not a sign to cut more.

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

"My bet: an agent that reads the actual account data, not just a help doc,
cross-references it against how the product actually works, and explains itself with
evidence — resolves most of these in one pass, and hands the rest to a human already
investigated."

### 1:15–1:45 — Scope discipline

"I scoped this narrowly — one request family, deep, not ten done shallow, since
breadth without a way to test correctness is unfalsifiable. I also skipped: any write
action, a real Pendo integration I don't have access to, a vector database for nine
short docs, and an agent framework — the loop's about a hundred lines, every decision
in it mine."

### 1:45–2:15 — Architecture

[Show the README architecture diagram]

"A chat page talks to a small FastAPI server running a hand-written agent loop. Claude
calls tools — read the guide, its segment, install status, search docs — against
simulated account data. The only way it can answer is one structured tool call: an
outcome, an evidence list, a caveats field. That's what makes the evidence panel, and
my evals, possible — code can check a field, not parse adjectives."

### 2:15–3:00 — Demo 1: diagnosis with a data conflict

[Click the example]: *"The guide page says 1,250 eligible visitors for New User
Onboarding, so why does nobody see it?"*

"Watch what it checks: guide published, fine. Segment live count, zero. Install
status — the app stopped sending `plan_tier` five days ago, which the segment rule
depends on. It cites the doc for that pattern.

Here's the part I care about: two numbers disagree — 1,250 at publish, 0 now — and it
doesn't just pick one, it explains why. That's not a guide quirk — it's the same
problem an analytics agent has every day: two numbers for 'the same' thing, and the
product has to be honest about which one's authoritative."

### 3:00–3:35 — Demo 2: ambiguity and escalation

[Click]: *"my onboarding guide isn't working"*

"Two guides match 'onboarding.' It doesn't guess — it asks which one."

[Click]: *"why isn't Dashboards Launch Announcement showing to more people?"*

"Here's a guide where every check comes back clean. Correct behavior isn't inventing a
cause — it's escalating, with a packet: what I already checked, what's unresolved. I
confirm it — the only state-changing action in the whole system. The model drafted, I
approved, code created the ticket. No model call in that step at all."

### 3:35–4:10 — Quality

[Show `python evals/run_evals.py` output]

"A demo working isn't evidence a probabilistic system works. I built eighteen golden
cases with deterministic assertions — right tool, right doc, a caveat populated when
data was stale or conflicting. Eight are specifically about ambiguous or conflicting
situations, the harder behavior to get right. This runs once per case today; the
honest next step is running each N times and gating on a pass rate — a single run
can't tell 'wrong' from 'unlucky,' which I learned the hard way building this."

### 4:10–4:45 — Production evolution and close

"What I'd build next: a real client behind these tool interfaces, shaped so that's a
swap not a rewrite; a deterministic check for the top cause, once trace data tells me
what that is; and calibrating the judge against human labels before trusting it
beyond a score.

What I want this to show isn't that I can make an agent call tools — it's knowing
which parts needed to be probabilistic, which needed a hard rule, and where that line
sits."

---

## Recording notes

- Have the server running (`uvicorn server:app --reload`) and the page loaded before
  recording. The page now opens with a short welcome message instead of blank — let it
  render before you start narrating over it, or narrate the problem while it's visible
  in the background.
- Use the example-prompt buttons for all three demo messages (1,250 eligible visitors /
  my onboarding guide isn't working / Dashboards Launch Announcement) so there's no live
  typing risk.
- Keep the evals segment to a single terminal screenshot/run — don't narrate every line
  of output.
- If time is tight, cut the second half of Demo 2 (the escalation confirm click) rather
  than any of the "why" sections — the judgment is the deliverable, the click is just
  proof it works.
- If you're over ~5:15 in a dry run, the Scope Discipline beat (1:15–1:45) is the
  safest place to trim further — it's the most list-like section and the least costly
  to shorten.
