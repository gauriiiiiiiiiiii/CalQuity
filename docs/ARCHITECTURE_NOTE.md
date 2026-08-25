# Architecture Note

## What I built

* One agent serving two roles, customer and ops, chosen at a mock login.
* One agent rather than two apps, because the interesting requirement is access control,
  and the cleanest way to show it is the same tools behaving differently per caller.
* Ops additionally gets a proactive Radar view, which is the extra problem I picked.
* Python, Streamlit UI, and an OpenAI-compatible LLM endpoint (tested on Groq's
  `openai/gpt-oss-120b`). Keeping the client OpenAI-compatible makes the provider a config
  change, not a rewrite.

## Agent design

* A plain tool-calling loop in `core/agent.py`, no framework.
* Framework-free on purpose: the control flow is readable and there is nothing hidden
  between the model and the tools.
* Each turn sends the conversation plus tool schemas, runs whatever tools the model asks
  for, feeds results back, and repeats until it answers or proposes an action.
* A step cap so it escalates rather than looping, and retry-with-backoff for the free-tier
  rate limit.
* The system prompt in `core/prompts.py` carries the role, account scope, snapshot time,
  authority order and escalation rules.
* Two behaviours are pushed hard: cite the source you actually used, and never do
  fee/credit/SLA math in your head, call the tool.

## Tool design

Three families, which the model chooses between:

1. **Document search** (`search_documents`). Returns ranked passages, each tagged with
   authority tier, status and effective date. Deprecated docs excluded unless asked for.
2. **Structured lookup and calculation.** `get_order`, `get_ticket`, `list_orders`,
   `list_tickets`, `get_account`, plus the calculators `assess_cancellation`,
   `assess_service_credit` and `assess_sla`. The calculators return the rule they applied
   and the numbers behind it, not just an answer.
3. **State-changing action** (`prepare_action`). Escalations, ticket updates, follow-up
   tasks. It only ever prepares a proposal.

Two things enforced in the dispatcher rather than the prompt:

* The write for a prepared action happens only after the user confirms in the UI, so
  confirmation does not depend on the model remembering to ask.
* Ops-only tools (`scan_issues`) are gated on the session, not requested politely.

## Document and structured-data handling

* Documents are parsed once (`data_layer/ingest.py`) into chunks carrying authority
  metadata, stored as a JSON index that ships with the repo, so the app starts without
  re-parsing.
* Retrieval (`data_layer/docstore.py`) is BM25. For six short documents a lexical ranker is
  accurate and needs no embedding service; embeddings would be a small change if the corpus
  grew.
* The workbook loads with openpyxl into plain dictionaries (`data_layer/datastore.py`).
* The snapshot time comes from the workbook's README sheet and is used everywhere time
  matters.
* The calculators are pure functions, unit-tested against `ANALYSIS.md`. Keeping the math in
  tested code, out of the model, is the main reason the numbers are reliable.

## Source reliability and conflict handling

* Support Policy v3 states the precedence rule itself, so I encoded that rule as numeric
  tiers in `core/authority.py` and attached a tier to every document.
* The resolver drops deprecated and out-of-scope sources, takes the highest tier, and flags
  a conflict when two equal-authority sources disagree, which is a case for a human rather
  than a guess.
* Old ticket resolutions come back with a warning and are never treated as authority.
* In practice this is what makes the agent answer "no fee" for Northstar's cancellation
  while ignoring the historical ticket that says a fee applies.

## Access control

* Enforcement sits in the tool functions, keyed off a server-side `Session`
  (`core/session.py`), never off anything the model says.
* A customer query is forced to their own account. Asking for another account's order
  returns a denial at the data layer, so the model never receives the row.
* Ticket free text is treated as data, not instructions, which also defuses prompt
  injection planted in a ticket body.

## Technical trade-offs

* Auth and roles are mocked, which the brief allows. The enforcement boundary is real, so
  swapping in real SSO only changes how the session is filled.
* Actions write to a local JSON file rather than a real ticketing system.
* Contract terms (Northstar's fee waiver, LumenWorks' credit) are parsed once into a small
  table with citations. A production version would have the agent extract them with a human
  approving, which is what scales past a handful of contracts.
* Business-hours SLA targets use a simple Mon-Fri 09:00-18:00 approximation. The 24x7 P1
  targets, which are the ones that matter here, are exact.
* No response streaming and no long-term memory, to keep the core small.
