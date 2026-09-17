# Acme Support Assistant (prototype)

A support agent that diagnoses why an in-app guide isn't showing, for a Pendo-like
product-experience platform. Built for Klaviyo's take-home technical assessment
(Senior PM, Analytics AI) — the deliverable is the product and architecture
judgment, not the line count.

**This is a prototype, not a demo of "AI can answer anything."** It deliberately does
one thing — diagnose one family of support requests using real account data — and
does it with visible evidence, explicit uncertainty, and a real escalation path. See
[Non-goals](#non-goals) for what was cut on purpose and why.

## What's real vs. simulated

- **The LLM is real** — Claude Sonnet 5 via the Anthropic API. The reasoning,
  tool selection, and evidence-grounded diagnosis you see are genuinely produced by
  the model, not scripted.
- **The account data is simulated.** [`data/fixtures.json`](data/fixtures.json) models
  the concepts of a real Pendo-like product (guides, segments, install snippet,
  visitor metadata) but is not connected to Pendo, and no Pendo account was used to
  build it. I don't have Pendo access for this assessment — see
  [`docs/DECISION_LOG.md`](docs/DECISION_LOG.md) for why fixtures were the right
  choice here rather than a liability.
- **The product docs in [`knowledge/`](knowledge/)** are written by me for this
  prototype, modeled on how a real help-center article for this kind of product
  would read.
- **Ticket creation is a local JSON file** ([`data/tickets.json`](data/tickets.json)),
  not a real ticketing system integration.

## The problem

An admin at a company using this platform sets up an in-app "guide" (a walkthrough,
tooltip, or announcement) targeted at a segment of their users. A day later: "nobody's
seeing it." There are roughly six independent things that could be wrong — the guide
was never actually published, the target segment currently has zero eligible visitors,
the install snippet isn't active in that app, the app stopped sending a metadata field
the segment rule depends on, a display-frequency limit was already hit, or the guide's
active date window hasn't started. None of these are visible from the guide editor
itself, and they can compound (two things can be wrong at once).

Today this is a slow, repetitive support loop: admin can't tell which of six things is
wrong → files a ticket → support asks "which guide, which app, what does the debugger
show" → 1-3 day round trip for something that's a config issue most of the time.

## Product hypothesis

An agent that can (1) read the specific guide/segment/install data for this account,
(2) cross-reference it against product knowledge, (3) explain its reasoning with cited
evidence, and (4) say plainly when it doesn't have enough evidence — resolves most of
these in one conversation, and makes the ones it can't resolve arrive at a human
pre-investigated instead of cold.

Why this needs an LLM and not just a script: the six causes interact in ways a fixed
decision tree handles badly (two causes at once, an ambiguous guide name, a customer
citing a stale number as evidence, a request that mixes a real question with an
out-of-scope one). A keyword search over docs can't check the customer's actual
config. A static FAQ can't reason about which config to check next based on what it
just found. See [`docs/DECISION_LOG.md`](docs/DECISION_LOG.md) for the fuller argument,
including the concession: for the single most common cause (draft status), a
deterministic check genuinely would be more reliable — that's the planned first
production optimization, not a flaw in choosing an agent for the rest.

## Scope

**Must demonstrate** (and does):
1. Multi-hop diagnosis using read-only tools, with every account-specific claim traced
   to a tool result.
2. Visible evidence — the UI shows exactly which tool/doc result backs each claim.
3. Refusal to guess — ambiguous guide name → asks; a failed check → says so, doesn't
   invent a fact to fill the gap.
4. Escalation as a real workflow — a structured packet the model drafts, a human
   confirms, and only then does code create a ticket.
5. A 16-case golden set with deterministic assertions on outcome, tool selection, and
   groundedness — including 8 cases specifically about ambiguous or conflicting data,
   not just the happy path.

**Nice to have** (included): an optional LLM-as-judge quality score (non-gating), a
prompt-injection-in-tool-data case, a per-turn JSONL trace log.

### Non-goals

Excluded on purpose, with the reason:

- **Any write action** (republish a guide, edit a segment) — the cost of a wrong write
  is customer-visible; a support agent should earn autonomy over reads before writes.
- **Analytics questions** ("why did usage drop 40%") — this is a different, harder
  trust problem (numeric consistency across the product) that deserves its own design,
  not a bolt-on to this prototype.
- **A real Pendo integration** — no access, and integration plumbing wouldn't change
  any of the product decisions being evaluated here.
- **Vector retrieval / a vector database** — the doc corpus is 9 short, hand-curated
  articles; keyword scoring over title/tags/body finds the right one every time at
  this size, and adds no dependency.
- **A database** — sessions are in-memory, tickets are a JSON file. No demo behavior
  needs persistence across restarts or multi-instance sharing.
- **Multi-agent orchestration** — one prompt and five tools is enough reasoning surface
  for this scope; more agents would add latency and failure modes without adding
  capability.
- **An agent framework** (LangChain/LangGraph/Claude Agent SDK/AI SDK) — the loop is
  ~100 lines and every line is a decision I want to be able to point at. See the
  decision log for when I *would* reach for one.
- **Streaming responses, auth, multi-tenant, feedback UI** — polish, not the thesis.

## Architecture

```
Browser (static/index.html — chat, evidence panel, caveats, escalation card)
   │  POST /chat            POST /escalate
   ▼
FastAPI (server.py) — in-memory sessions, JSONL trace log
   │
   ▼
Agent loop (app/agent.py, hand-written, ~100 lines)
  Claude Sonnet 5 · tool_choice: auto · strict tool schemas · adaptive thinking
  (never displayed/stored) · hard 8-step cap
   │
   ├─ get_guide(name_or_id)        ┐
   ├─ get_segment(segment_id)      │  read-only, backed by data/fixtures.json
   ├─ get_install_status(app_id)   │  (app/tools.py)
   ├─ list_guides()                ┘
   ├─ search_docs(query)  ← keyword scoring over knowledge/*.md (app/knowledge.py)
   └─ respond(outcome, message, evidence[], caveats[], escalation_draft?)
        outcome ∈ {answered, needs_clarification, escalate, out_of_scope}
        — the ONLY way the model can produce a customer-facing message

Escalation commit: POST /escalate writes data/tickets.json. No model call in
this path — the model only ever drafts; a human confirms; code commits.
```

**Why `respond` is a tool, not free text:** it's the mechanism that makes the UI's
evidence panel and the eval's deterministic assertions possible. `outcome` and
`caveats` are structured fields the code can branch on and the evals can assert
against, not adjectives the code would have to parse out of prose.

**Why `tool_choice: "auto"` and not a forced `"any"`:** avoids any dependency on
forced-tool-choice model-specific behavior, at the cost of needing a code-level
guardrail: if the model ever ends a turn without calling a tool (breaking the
contract), the agent loop treats that as a failure and returns a synthetic
`escalate` response rather than surfacing raw, ungoverned model text to the customer.
See `_contract_violation_result` in [`app/agent.py`](app/agent.py).

## Trust and grounding

| What | Mode | Why |
|---|---|---|
| Interpreting the request, deciding what to check | Probabilistic (LLM) | The reason to use an LLM at all |
| Facts about this account (guide status, segment count, install status) | Tool-backed only, never generated | The one rule that can't bend |
| Product knowledge | Retrieval (keyword search), cited | Paraphrase is fine; the claim must be traceable |
| Which source wins when two numbers disagree | Deterministic rule in the prompt: live tool result > publish-time snapshot > customer's stated belief | The model decides *whether* there's a conflict; the rule decides *which wins*, so this doesn't vary run to run |
| Uncertainty (stale data, unverifiable check, disagreeing sources) | Structured `caveats[]` field | Assertable in evals and visibly rendered, not buried in hedging prose |
| Scope boundary (billing, write requests) | No tool exists for the action + prompt instruction | Enforced by what's absent, not just by asking nicely |
| Escalation commit | Deterministic code, human-confirmed | The only state-changing action in the whole system |
| Runaway tool use | Hard step cap (8) | An agent needs a bound on how long it tries before a human decides, not an unbounded bill |
| Anthropic API itself failing (rate limit, outage, timeout) | Fail closed to escalate, after the SDK's own retry budget is exhausted | A customer-facing chat turn shouldn't hang on more retries or surface a raw 500 — hand to a human fast |

If you only read one part of this repo to understand the trust design, read
[`app/prompts.py`](app/prompts.py)'s "Grounding rules" and "When data sources
disagree" sections, then golden cases `conflicting_counts`, `stale_segment_estimate`,
and `tool_error_no_guess` in [`evals/golden_cases.json`](evals/golden_cases.json) —
those three exist specifically to make "what happens when the data is unclear"
checkable rather than a claim I make in a video.

## Evaluation

```bash
python evals/run_evals.py            # deterministic assertions, single run per case
python evals/run_evals.py --judge    # + non-gating LLM-judge quality score
python evals/run_evals.py --repeat 5 # run every case 5x, report a per-case PASS RATE
```

`--repeat` isn't a hypothetical "production would do this" — it's a real, working measurement of run-to-run variance, because that variance showed up empirically while building this (see Decision Log #11) and a single pass/fail was the wrong way to report it.

16 golden cases across four categories:

- **Diagnosis (4)** — the core value: multi-hop reasoning that actually resolves the
  ticket.
- **Conflict & ambiguity (8)** — the trust story: two guides matching one name, a
  customer citing a stale number, two independent root causes at once, a segment
  estimate that predates a rule change, a mixed diagnostic-and-write-request message.
  This is deliberately the largest category — "does it behave correctly when the
  situation *isn't* clean" is a stronger quality signal than another happy-path case.
- **Escalation (1)** and **scope & safety (3)** — correct escalation with a useful
  packet, refusing billing/write requests, and resisting an instruction injected into
  guide data returned by a tool.

Each case makes deterministic assertions: expected `outcome`, which tools must (or
must not) be called, required substrings, whether a specific doc must be cited, and
whether `caveats`/`escalation_draft` are populated. See
[`docs/DECISION_LOG.md`](docs/DECISION_LOG.md) for what a production version of this
would add (N runs per case with a pass-rate gate, a real golden-set sourcing pipeline,
calibrating the judge against human labels).

## Setup

```bash
python -m venv venv
./venv/Scripts/activate        # Windows; use `source venv/bin/activate` on macOS/Linux
pip install -r requirements.txt
cp .env.example .env           # then paste your ANTHROPIC_API_KEY into .env
uvicorn server:app --reload
```

Open http://localhost:8000 — the page has clickable example prompts covering the
happy path, an ambiguous guide, a how-to question, and an out-of-scope request.

## Production evolution

What I'd invest in next, roughly in order:

1. **A deterministic health-check for the single most common cause** (draft status),
   informed by the trace log's actual symptom distribution rather than a guess. This
   is a case where a script genuinely beats the agent — see the decision log.
2. **A real client behind the same tool interfaces** — the tool signatures
   (`get_guide(name_or_id)`, `get_segment(segment_id)`, `get_install_status(app_id)`)
   are shaped so swapping fixtures for a real API is a contained change, not a rewrite.
3. **N-run evals with a pass-rate gate**, and a real golden-set pipeline sourced from
   production escalations and support-agent feedback, not just hand-authored cases.
4. **Tenant-scoped auth** — right now the account is a constant in the system prompt;
   in production, tool calls must be scoped to the authenticated account server-side,
   not trusted from the prompt.
5. **A judge calibrated against human labels** before trusting it for anything gating.

## Repository layout

```
app/tools.py       tool schemas + read-only executors over data/fixtures.json
app/knowledge.py   keyword search over knowledge/*.md
app/prompts.py     the system prompt (grounding rules, escalation criteria, scope)
app/agent.py       the agent loop
app/tracing.py     per-turn JSONL trace log
server.py          FastAPI: /chat, /escalate, static file serving
static/index.html  chat UI with evidence panel, caveats, escalation card
data/fixtures.json simulated account data (labeled as such)
knowledge/*.md     9 curated product docs
evals/             golden_cases.json + run_evals.py
docs/              decision log, interview Q&A, video script
```
