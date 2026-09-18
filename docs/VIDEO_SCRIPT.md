# Video Script

Tone: a senior PM explaining a product and its tradeoffs, not an engineer narrating a
codebase. Show code only when pointing at a specific decision. Plain language over
jargon — if a line needs a technical term, explain what it does before using it.
Timestamps are guidance, not a strict script.

**Length note:** this version runs longer than the original 4-5 minute target — see
the bottom of this file for the actual estimate and where to cut if you need to land
closer to 5:00.

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

### 1:45–2:25 — Architecture, in plain terms

[Show the README architecture diagram]

"Here's the part that matters most: the model can't just reply with a paragraph of
text. Every answer has to come back in one fixed format — a label for what actually
happened: solved it, needs more info, or escalating. A list of the specific facts it
used, and exactly where each one came from. And a separate field for anything it's not
fully sure about.

Because that format is fixed, my code — and my tests — can actually check it: did it
cite a real source, did it flag when the data looked shaky. Not me reading a paragraph
and guessing whether it sounds trustworthy."

### 2:25–3:10 — Demo 1: diagnosis with a data conflict

[Click the example]: *"The guide page says 1,250 eligible visitors for New User
Onboarding, so why does nobody see it?"*

"Watch what it checks: guide published, fine. Segment live count, zero. Install
status — the app stopped sending `plan_tier` five days ago, which the segment rule
depends on. It cites the doc for that pattern.

Here's the part I care about: two numbers disagree — 1,250 at publish, 0 now — and it
doesn't just pick one, it explains why. This is the same problem an analytics agent
hits constantly: two numbers describing the same thing, and the product has to be
honest about which one's right, and why."

### 3:10–4:20 — Demo 2: trust and guardrails

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

### 4:20–4:55 — Quality

[Show `python evals/run_evals.py` output]

"A demo working isn't evidence a probabilistic system works. I built eighteen golden
cases with deterministic assertions — right tool, right doc, a caveat populated when
data was stale or conflicting. Eight are specifically about ambiguous or conflicting
situations, the harder behavior to get right. This runs once per case today; the
honest next step is running each N times and gating on a pass rate — a single run
can't tell 'wrong' from 'unlucky,' which I learned the hard way building this."

### 4:55–5:30 — Production evolution and close

"What I'd build next: a real client behind these tool interfaces, shaped so that's a
swap not a rewrite; a deterministic check for the top cause, once trace data tells me
what that is; and calibrating the judge against human labels before trusting it beyond
a score.

The real test here was knowing which parts needed to be probabilistic, which needed a
hard rule, and where that line actually sits — not whether I could make an agent call
tools."

---

## Length estimate and trim guide

**Narration alone is 788 words, about 5:15 at 150 words/minute — before adding the
demo click/wait time.** Demo 2 now has three separate exchanges (each a real API
call, roughly 5-15 seconds), Demo 1 has one, and the escalation confirm is a fourth
click — call it another 50-65 seconds of silent wait/click time. Realistic total
recorded time is closer to **6:00-6:20**, meaningfully past the "4-5 minutes" target.

If you want to land closer to 5:00, cut in this order (each keeps the video coherent
on its own):
1. **Drop the billing/out-of-scope beat from Demo 2** (saves ~20s narration + a full
   API call, ~30-45s total) — the ambiguous-question and escalation beats already
   carry the "it doesn't guess, and it knows its limits" story; billing is the most
   removable of the three since guardrail scope-declining is the least novel of the
   three behaviors.
2. **Trim the Scope Discipline beat** (1:15-1:45) down to one sentence — it's the
   most list-like section and the least costly to shorten.
3. **Cut the Production/close section to one paragraph** — pick either "what's next"
   or the closing line, not both.

Cutting #1 alone removes roughly 45-60s of real recorded time and gets you close to
5:30-5:45. Cutting all three lands you near 5:00.

## Recording notes

- Have the server running (`uvicorn server:app --reload`) and the page loaded before
  recording. The page opens with a short welcome message instead of blank — let it
  render before narrating over it, or narrate the problem while it's visible in the
  background.
- Every demo message in this script (1,250 eligible visitors / my onboarding guide
  isn't working / I want a refund / Dashboards Launch Announcement) is a clickable
  example button in the UI — no live typing risk.
- Keep the evals segment to a single terminal screenshot/run — don't narrate every
  line of output.
