# Video Script (4-5 minutes)

Tone: a senior PM explaining a product and its tradeoffs, not an engineer narrating a
codebase. Show code only when pointing at a specific decision. ~690 words total —
timestamps below are guidance, not a strict script; the priority is leading with the
customer's situation, not the artifact.

---

### 0:00–0:40 — The problem (lead with the customer, not the solution)

"Picture a product manager at a B2B SaaS company. She just built an in-app
walkthrough — a 'guide' — to onboard new trial users. A day later: nobody's using it,
why? She has no idea. It could be one of six things — never published, the target
audience is empty, a tracking snippet broke, the app stopped sending a field the
targeting depends on — and none of it is visible from the guide editor itself. So it
becomes a support ticket. Support asks her the same questions she can't answer. One to
three days to fix what's usually a five-minute config issue. That gap — between
'something's wrong' and 'here's specifically what and why' — is the problem I chose to
solve."

### 0:40–1:00 — Product thesis

"My bet: an agent that reads the actual account data, not just a help doc,
cross-references it against how the product actually works, and explains itself with
evidence — resolves most of these in one pass, and hands the rest to a human already
investigated."

### 1:00–1:30 — Scope discipline

"I scoped this narrowly on purpose — one request family, done deep, not ten kinds of
tickets done shallow, because breadth without a way to test correctness is
unfalsifiable. I also deliberately skipped: any write action, so it diagnoses but never
touches a customer's config; a real Pendo integration, since I don't have access — the
data here is clearly simulated; a vector database, since nine short docs don't need
one; and an agent framework, since the whole loop is about a hundred lines and I wanted
every decision in it to be mine, not configuration."

### 1:30–2:05 — Architecture

[Show the README architecture diagram]

"A chat page talks to a small FastAPI server running a hand-written agent loop. Claude
calls tools — read the guide, its segment, install status, search docs — against
simulated account data. The only way it can answer is one structured tool call: an
outcome, an evidence list, a caveats field for uncertainty. That structure is what
makes the evidence panel, and my evals, possible — code can check a field, not parse
adjectives out of a paragraph."

### 2:05–3:00 — Demo 1: diagnosis with a data conflict

[Click the example]: *"The guide page says 1,250 eligible visitors for New User
Onboarding, so why does nobody see it?"*

"Watch what it checks: guide — published, fine. Segment — live count, zero. Install
status — the app stopped sending a field called `plan_tier` five days ago, which the
segment rule depends on. It cites the doc that documents that exact pattern.

Here's the part I actually care about: two real numbers disagree — 1,250 at publish, 0
right now — and it doesn't just pick one. It explains why they differ instead of
resolving the discrepancy silently. That's not a guide quirk — it's the same problem an
analytics agent has every day: two numbers describing 'the same' thing, and the product
has to be honest about which one's authoritative, and why."

### 3:00–3:50 — Demo 2: ambiguity and escalation

[Click]: *"my onboarding guide isn't working"*

"Two guides match 'onboarding.' It doesn't guess — it asks which one."

[Click]: *"why isn't Dashboards Launch Announcement showing to more people?"*

"Here's a guide where every check comes back clean. Correct behavior isn't inventing a
cause — it's escalating, with a packet: what I already checked, what's unresolved. I
confirm it — the only state-changing action in the whole system. The model drafted, I
approved, code created the ticket. No model call in that step at all."

### 3:50–4:30 — Quality

[Show `python evals/run_evals.py` output]

"A demo working isn't evidence a probabilistic system works. I built eighteen golden
cases with deterministic assertions — did it call the right tool, cite the right doc,
populate a caveat when the data was actually stale or conflicting. Eight are
specifically about ambiguous or conflicting situations, because that's the harder
behavior to get right. This runs once per case today; the honest next step is running
each one N times and gating on a pass rate — a single run can't tell you 'wrong' from
'unlucky,' and I learned that the hard way while building this."

### 4:30–5:00 — Production evolution and close

"What I'd build next: a real client behind these same tool interfaces, since they're
shaped so that's a swap, not a rewrite; a deterministic check for the single most
common cause, once trace data tells me what that actually is; and calibrating the judge
against human labels before I'd trust it for anything beyond a reported score.

What I want this to show isn't that I can make an agent call tools. It's that I know
which parts of this needed to be probabilistic, which needed a hard rule, and where
that line actually has to sit."

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
- If you're over ~4:50 in a dry run, the Scope Discipline beat (1:00–1:30) is the
  safest place to trim further — it's the most list-like section and the least costly
  to shorten.
