# ParcelPilot Support Agent

An AI support agent for ParcelPilot, a B2B logistics platform. It answers support questions
from the supplied document and data pack, which is deliberately messy:

* Customer contracts override the general policy.
* One policy version is deprecated but still reads as relevant.
* Some past ticket answers are simply wrong.

The agent is built to notice that, cite the source it actually relied on, and hand off to a
human when it should not decide on its own.

One agent serves two roles, picked at a mock login:

* **Customer.** Their own account only.
* **Ops.** Across accounts, plus a Radar view flagging what needs attention: breached SLAs,
  novel incidents, clusters.

## Running it

```bash
python -m pip install -r requirements.txt
cp .env.example .env          # put your LLM key in .env
python -m pytest tests/ -q    # 19 ground-truth checks, no API key needed
streamlit run app/streamlit_app.py
```

* The chat needs an LLM key. The Radar tab and the tests run without one.
* The client is OpenAI-compatible and detects the provider from the key prefix: `gsk_` uses
  Groq (default `openai/gpt-oss-120b`), `xai-` uses xAI Grok.
* Set `LLM_MODEL` or `LLM_BASE_URL` in `.env` to point elsewhere. This build was tested on
  Groq.
* `python -m eval.run_eval` runs the trap cases through the live agent. Needs the key.

## Things to try

* **As Northstar (ACCT-001):** "Can I cancel ORD-1001 without a cancellation fee?" No fee,
  because their contract overrides the SOP's INR 250 rule, and it ignores the old ticket
  saying otherwise.
* **As LumenWorks (ACCT-002):** "ORD-2002's pickup is late and it's the carrier's fault, do
  I get a credit?" INR 300 from their contract, not the SOP default. Asking to see ORD-1001,
  another account's order, is refused.
* **As Ops:** "What's most urgent right now?" Surfaces the two breached P1s, the API-key
  exposure and the Northstar outage.

## How it's built

Full reasoning in [docs/ARCHITECTURE_NOTE.md](docs/ARCHITECTURE_NOTE.md). The short version:

* **Source authority is data, not a prompt hope.** Each document carries a tier: contract >
  current policy/SOP > product docs > deprecated > old tickets. Deprecated docs are dropped
  from search, so an outdated policy cannot slip into an answer.
* **The arithmetic is plain Python and unit-tested.** Fees, credits and SLA breaches come
  from `data_layer/datastore.py`. The model calls those functions instead of doing math.
* **Access control lives in the tools**, keyed off a server-side session, so no phrasing in
  the chat can widen a customer's scope.
* **Actions need a click.** The agent can only prepare an escalation or ticket update. A
  human confirms before anything is written.
* **Time is the dataset snapshot** (2026-08-16 11:00 IST from the workbook README), never
  the real clock.

## Notes

* [Architecture note](docs/ARCHITECTURE_NOTE.md) covers agent and tool design, document and
  structured-data handling, source conflicts, and the trade-offs.
* [Product note](docs/PRODUCT_NOTE.md) covers the extra problem I picked, what I'd build
  next, what I left out, and the metric I'd judge this on.
* [AI tool usage](docs/AI_TOOL_USAGE.md) covers which AI tools I used and how.
* [Data analysis](docs/ANALYSIS.md) is the ground truth worked out from the pack by hand.
  The tests use it as the source for every expected number.

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

* Point Streamlit Community Cloud at `app/streamlit_app.py`.
* Add `LLM_API_KEY`, and `LLM_MODEL` if you want to pin one, in the app secrets.

Auth and roles are mocked, which the brief allows, and actions write to a local JSON file.
The architecture note lists the rest of the trade-offs.
