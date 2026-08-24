# AI Tool Usage

I used Claude Code as a coding assistant while building this.

Where it helped:

* Reading the six PDFs and the workbook and writing up the ground truth in `ANALYSIS.md`:
  the correct answer and governing source for each order and ticket, and the list of
  planted traps (the deprecated policy, the contract overrides, the wrong historical
  tickets, the SwiftShip webhook delay, the snapshot time).
* Drafting the module scaffolding (ingest, retrieval, data layer and calculators, the
  tool layer, the agent loop, detection, and the Streamlit UI) and the test and eval
  harnesses.
* Writing and running the tests until they were green, and boot-testing the app.

The product and technical calls were mine: one agent with two roles, choosing proactive
detection as the extra problem, enforcing access in the data layer, keeping the
arithmetic in tested Python, and requiring confirmation before actions. I checked the
generated answers against the actual source documents rather than trusting them.

At runtime the agent itself runs on Groq (`openai/gpt-oss-120b`) through the
OpenAI-compatible API. The client detects the provider from the key prefix, so switching
to xAI Grok or another compatible host is a one-line change.
