# ParcelPilot Support Agent

An AI support agent for ParcelPilot, a B2B logistics platform. It answers support
questions from the supplied document and data pack, which is deliberately messy:
customer contracts override the general policy, one policy version is deprecated, and
some past ticket answers are wrong. The agent is built to notice that, cite the source
it actually relied on, and hand off to a human when it should not decide on its own.

One agent serves two roles, picked at a mock login:

* **Customer** answers questions about their own account only.
* **Ops** can look across accounts and gets a "Radar" view that flags what needs
  attention (breached SLAs, novel incidents, clusters).

## Running it

```bash
python -m pip install -r requirements.txt
cp .env.example .env          # put your LLM key in .env
python -m pytest tests/ -q    # 19 ground-truth checks, no API key needed
streamlit run app/streamlit_app.py
```

The chat needs an LLM key; the Radar tab and the tests run without one. The client is
OpenAI-compatible and figures out the provider from the key prefix: `gsk_` uses Groq
(default model `openai/gpt-oss-120b`), `xai-` uses xAI Grok. Set `LLM_MODEL` /
`LLM_BASE_URL` in `.env` to point somewhere else. This build was tested on Groq.

To run the trap cases through the live agent (needs the key):

```bash
python -m eval.run_eval
```

## Things to try

As Northstar (ACCT-001): "Can I cancel ORD-1001 without a cancellation fee?" The answer
is no fee, because the Northstar contract overrides the SOP's INR 250 rule, and it
ignores the old ticket that says otherwise.

As LumenWorks (ACCT-002): "ORD-2002's pickup is late and it's the carrier's fault, do I
get a credit?" gives INR 300 from their contract, not the SOP default. Asking to see
ORD-1001 (another account's order) is refused.

As Ops: "What's most urgent right now?" surfaces the two breached P1s (the API-key
exposure and the Northstar outage).

## How it's built

The design decisions that matter are in
[docs/ARCHITECTURE_NOTE.md](docs/ARCHITECTURE_NOTE.md).
The short version:

* **Source authority** is data, not a prompt hope. Each document carries a tier
  (contract > current policy/SOP > product docs > deprecated > old tickets). Deprecated
  docs are dropped from search, so an outdated policy can't slip into an answer.
* **The arithmetic is plain Python and unit-tested** against the workbook. Fees,
  credits and SLA breaches come from `data_layer/datastore.py`; the model calls those
  functions instead of doing math itself.
* **Access control lives in the tools**, keyed off a server-side session, so no phrasing
  in the chat can widen a customer's scope.
* **Actions need a click.** The agent can only prepare an escalation or ticket update;
  a human confirms before anything is written.
* **Time is the dataset snapshot** (2026-08-16 11:00 IST from the workbook README), never
  the real clock.

## Layout

```
app/streamlit_app.py   chat UI (with tool trace + confirm gate) and the Ops Radar tab
core/                  agent loop, tools, authority model, detection, prompts, session
data_layer/            PDF ingest, retrieval, workbook + calculators, action store
eval/                  golden trap cases run through the live agent
tests/                 ground-truth unit tests
docs/                  architecture, product and AI-tool notes; the data analysis
```

## Deploying

Push to a public GitHub repo, point Streamlit Community Cloud at
`app/streamlit_app.py`, and add `LLM_API_KEY` (and `LLM_MODEL` if you want) in the app
secrets.

## What's mocked

Auth and roles are mocked, which the brief allows. Actions write to a local JSON file.
Retrieval is lexical (BM25) because the corpus is six short documents; embeddings would
be a drop-in if it grew. See the architecture note for the full list of trade-offs.
