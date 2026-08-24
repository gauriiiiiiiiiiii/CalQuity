# Product Note

## The extra problem I picked: proactive issue detection

A chatbot only helps once someone asks. For a 20-person ops team the expensive misses
are the ones nobody flagged in time, so I built an ops "Radar" (`core/detection.py`,
shown in the Radar tab).

It scans the open tickets against the dataset snapshot time and ranks them by what
actually deserves attention. It computes time to SLA breach using the governing target,
so a Northstar P1 is judged against their 15-minute contract target rather than the
30-minute default. It classifies severity from the Support Policy v3 definitions, and it
cross-references each ticket against the known-issues doc so it can tell "this matches
KI-208" apart from a novel incident. A novel P1 is the signal that matters most, since
that is a possible new outage, and it is exactly the thing a keyword dashboard misses.
It also groups tickets by area and counts affected accounts, and every item has a
one-click "prepare escalation" that goes through the same confirmation gate as the chat.

On the supplied data this puts the two breached P1s at the top: the API-key exposure at
Axis Labs, well past its target, and the Northstar outage, breached and novel. The
lower-priority known-issue tickets sort below them, which is the call I'd want ops to
make.

## What I'd build next

1. Show the customer the conflict, not just the answer. The agent already resolves
   which source wins; surfacing "this contract term applies to you, and it overrides this
   general rule" would make the answer teach trust. This matters because the whole product
   lives on trust.
2. A human-in-the-loop escalation queue that captures corrections. When ops overrides the
   agent, store that as a labelled example. It is the loop that improves the system and
   feeds the eval set.
3. Onboard contracts through the agent instead of by hand. Today the two contracts are
   parsed into a small table. A real deployment would have the agent extract the terms and
   a human approve them, which is what makes it scale past four accounts.
4. Volume anomaly detection (complaint spikes, carrier-specific failure rates). The brief
   asks for sudden increases and unusual patterns, and the current Radar is per-ticket, not
   trend-based.

## What I left out on purpose

Real authentication and RBAC (mocked, per the brief). A vector database (six short
documents do not need one). Streaming and long-term memory (kept the core small).
Precise business-hours SLA math (approximated; the 24x7 P1 targets are exact). Real
workflow integrations like return-to-origin, which several tickets would eventually need.

## The metric I'd track

Grounded-answer accuracy: the share of answers that get the entitlement right, cite the
correct governing source, and make the right call on whether to escalate. Offline it is
the eval pass rate; in production it is how often ops has to overturn an answer. It
targets the exact failure the client is worried about, a confident wrong answer.
