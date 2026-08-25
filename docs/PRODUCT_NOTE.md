# Product Note

## The extra problem I picked: proactive issue detection

A chatbot only helps once someone asks. For a 20-person ops team the expensive misses are
the ones nobody flagged in time, so I built an ops Radar (`core/detection.py`, shown in the
Radar tab).

What it does:

* Scans open tickets against the snapshot time and ranks them by what deserves attention.
* Computes time to SLA breach using the **governing** target, so a Northstar P1 is judged
  against their 15-minute contract term, not the 30-minute default.
* Classifies severity from the Policy v3 definitions.
* Cross-references the known-issues doc, so it can tell "this matches KI-208" apart from a
  novel incident. A novel P1 is the signal that matters most, because it may be a new
  outage, and it is exactly what a keyword dashboard misses.
* Groups tickets by area and counts affected accounts.
* Puts a one-click "prepare escalation" on every item, through the same confirmation gate
  as the chat.

On the supplied data it surfaces the two breached P1s first: the Axis Labs API-key exposure,
well past target, and the Northstar outage, breached and novel. The known-issue tickets sort
below them, which is the call I'd want ops to make.

## What I'd build next

1. **Show the conflict, not just the answer.** The agent already resolves which source wins.
   Surfacing "this contract term applies to you, and it overrides this general rule" makes
   the answer teach trust, and the whole product lives on trust.
2. **A human-in-the-loop escalation queue that captures corrections.** When ops overrides
   the agent, store that as a labelled example. That is the loop that improves the system
   and grows the eval set.
3. **Onboard contracts through the agent.** Today the two contracts are parsed into a table
   by hand. A real deployment would have the agent extract terms and a human approve them,
   which is what makes it scale past four accounts.
4. **Volume anomaly detection.** Complaint spikes, carrier-specific failure rates. The brief
   asks for sudden increases and unusual patterns; the current Radar is per-ticket, not
   trend-based.

## What I left out on purpose

I spent the time on conflict arbitration and the enforcement boundary, because that is where
a wrong answer costs the client money. Everything that would only have made the demo look
bigger got cut:

* No real login.
* No vector database.
* No streaming, no long-term memory.
* No integration with a real ticketing or return-to-origin workflow.

The architecture note gives the reasoning behind each.

The omission I would defend in a review is the last one. Preparing an escalation for a human
to act on is honest about what this system is today. Wiring it straight into a ticketing
system would have demoed better and been worse, because the confirmation step is the point.

## The metric I'd track

**Grounded-answer accuracy:** the share of answers that get the entitlement right, cite the
correct governing source, and make the right call on whether to escalate.

* Offline, it is the eval pass rate.
* In production, it is how often ops has to overturn an answer.
* It targets the exact failure the client is worried about: a confident wrong answer.
