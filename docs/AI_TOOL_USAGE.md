# AI Tool Usage

I used Claude Code while building this, and I drove it rather than took its output on faith.

## The decisions were mine

* One agent with two roles instead of two apps.
* Proactive detection as the extra problem.
* Access control enforced in the data layer, not the prompt.
* Arithmetic kept in tested Python, not the model.
* A confirmation gate the agent cannot bypass.

## What I used it for

* Reading the six PDFs and the workbook into the ground truth in `ANALYSIS.md`.
* Drafting the modules.
* Writing the test and eval harnesses.

## How I checked it

* I verified every fee, credit, SLA target and citation in `ANALYSIS.md` against the source
  documents myself.
* The 19 unit tests pin those numbers to values I derived from the documents, so a
  plausible-sounding wrong answer fails the build instead of shipping.
* The 6 golden cases do the same for the agent's reasoning over the planted traps.
* Two of my own eval assertions turned out to be wrong before the agent did. Finding that
  took reading the data, not prompting.

## At runtime

The agent runs on Groq (`openai/gpt-oss-120b`) over the OpenAI-compatible API. The client
detects the provider from the key prefix, so moving to xAI Grok or another host is a config
change.
