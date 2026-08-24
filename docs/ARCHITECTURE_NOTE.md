# Architecture Note

## What I built

One agent serving two roles (customer and ops), chosen at a mock login. I went with a
single agent rather than two apps because the interesting requirement is access control,
and the cleanest way to show it is the same tools behaving differently for different
callers. Ops additionally gets a proactive "Radar" view, which is the extra problem I
picked.

The stack is Python with a Streamlit UI. The agent talks to an OpenAI-compatible LLM
endpoint (tested on Groq's `openai/gpt-oss-120b`). Keeping the client OpenAI-compatible
means the provider is a config change, not a rewrite.

## Agent design

The agent is a plain tool-calling loop (`core/agent.py`), no framework. I kept it
framework-free on purpose: the control flow is easy to read and easy to defend, and there
is nothing hidden between the model and the tools. Each turn sends the conversation plus
the tool schemas to the model, runs any tool calls it asks for, feeds the results back,
and repeats until the model answers or proposes an action. There is a step cap and
retry-with-backoff for the free-tier rate limit.

The system prompt (`core/prompts.py`) carries the role, the account scope, the snapshot
time, the source-authority order, and the escalation rules. Two behaviours are pushed
hard: cite the source you actually used, and never do fee/credit/SLA math in your head,
call the tool.

## Tool design

Three tool families, which the model chooses between:

1. **Document search** (`search_documents`) returns ranked passages, each tagged with its
   authority tier, status and effective date. Deprecated documents are excluded unless
   explicitly asked for.
2. **Structured lookup and calculation** over the workbook: `get_order`, `get_ticket`,
   `list_orders`, `list_tickets`, `get_account`, plus the calculators
   `assess_cancellation`, `assess_service_credit` and `assess_sla`. The calculators
   return the rule they applied and the numbers behind it, not just an answer.
3. **State-changing action** (`prepare_action`) for escalations, ticket updates and
   follow-up tasks. It only ever prepares a proposal. The write happens after the user
   confirms in the UI, so confirmation is enforced by the tool layer, not by trusting the
   model to ask.

Ops-only tools (`scan_issues`) are gated in the dispatcher, not in the prompt.

## Document and structured-data handling

Documents are parsed once (`data_layer/ingest.py`) into chunks with authority metadata
and stored as a JSON index that ships with the repo, so the app starts without
re-parsing. Retrieval (`data_layer/docstore.py`) is BM25. For six short documents a
lexical ranker is accurate and needs no embedding service; embeddings would be a small
change if the corpus grew.

The workbook is loaded with openpyxl into plain dictionaries (`data_layer/datastore.py`).
The dataset snapshot time comes from the README sheet and is used everywhere time
matters. The calculators are pure functions, unit-tested against the values in
`ANALYSIS.md`. Keeping the math in tested code, out of the model, is the main reason the
numeric answers are reliable.

## Source reliability and conflict handling

Support Policy v3 states the precedence rule itself: signed customer agreement first,
then current policy and product docs, then historical tickets as context only. I encoded
that as numeric tiers (`core/authority.py`) and attached a tier to every document. The
resolver drops deprecated and out-of-scope sources, takes the highest tier, and flags a
conflict when two equal-authority sources disagree, which is a case for a human rather
than a guess. Old ticket resolutions are returned with a warning and never treated as
authority. In practice this is what makes the agent answer "no fee" for Northstar's
cancellation while ignoring the historical ticket that says a fee applies.

## Access control

Enforcement sits in the tool functions, keyed off a server-side `Session` (`core/session.py`),
not off anything the model says. A customer query is forced to their own account; asking
for another account's order returns a denial at the data layer, so the model never
receives the row. Ticket free text is treated as data, not instructions, which also
defuses prompt injection planted in a ticket body.

## Trade-offs and what's left out

* Auth and roles are mocked (allowed by the brief). The enforcement boundary is real, so
  swapping in real SSO only changes how the session is filled.
* Actions write to a local JSON file rather than a real ticketing system.
* Contract-specific terms (Northstar's fee waiver, LumenWorks' credit) are parsed once
  into a small table with citations. A production version would have the agent extract
  these with a human approving them, which is what lets it scale past a handful of
  contracts.
* Business-hours SLA targets use a simple Mon-Fri 09:00-18:00 approximation. The 24x7 P1
  targets, which are the ones that matter here, are exact.
* No response streaming or long-term memory, to keep the core small.
