# Data Analysis (Ground Truth)

Notes from reading the pack before writing code, so the system is built against the real
data rather than the worked examples in the brief. The unit tests check these values.

## Ground rules

* Reference "now" is the workbook snapshot: **2026-08-16 11:00 Asia/Kolkata**.
* Every SLA breach, cancellation window and pickup delay is measured from it, never the
  real clock.
* Currency is INR. The data is synthetic.

## Source authority

Policy v3 §1 states the precedence itself, so I used its own ordering:

1. Signed customer agreement, for its own account only, while in term.
2. Current policy, SOP and product docs.
3. Historical tickets and internal notes: context only, may be wrong, never authority.

On top of that ordering:

* Within a tier, the later effective date wins.
* A source only counts if it is in effect at the snapshot and in scope for the account.
* Policy v2 is stamped DEPRECATED. It is the closest textual match for SLA questions,
  which is what makes it dangerous, and it must never answer a current request.

| Doc | Status | Effective | Governs | Catch |
|-----|--------|-----------|---------|-------|
| 01 Support Policy v3 | CURRENT | 2026-05-01 | Severity, first-response SLA by plan, the precedence rule | this is the authority |
| 02 Support Policy v2 | DEPRECATED | 2025-01-01 | Old, longer SLA targets | looks relevant, must never be used |
| 03 Cancellation & Credit SOP v4 | CURRENT | 2026-06-15 | Cancel fees by status, failed-pickup credit, approvals | defaults that contracts override |
| 04 Product Ops Guide + Known Issues | CURRENT | 2026-08-14 | Plan limits, KI-208, KI-211 | real limit 5000 vs failures near 3000 |
| 05 Northstar Agreement | ACTIVE | 2026 term | ACCT-001 custom SLA, free cancellation | overrides SOP and policy |
| 06 LumenWorks Agreement | ACTIVE | 2026-03 to 2027-02 | ACCT-002 custom credit | overrides SOP credit |

## SOP v4 rules

Cancellation, by status:

* DRAFT: free.
* BOOKED, not yet picked up: free within 30 minutes of booking, else INR 250 unless a
  contract waives it.
* PICKED_UP: cannot cancel, goes to return-to-origin.
* DELIVERED: cannot cancel.

Failed-pickup credit, by default:

* Needs pickup more than 2 hours past the window end.
* Needs carrier at fault and no customer fault.
* Pays the lower of INR 500 or 10% of the fee.
* Above INR 1,000 needs manager approval.
* Never promise a credit while fault or timing is unknown.

## Known issues

* **KI-208.** Bulk upload fails above roughly 3,000 rows even though the real limit is
  5,000. Workaround: split below 3,000.
* **KI-211.** SwiftShip pickup webhooks can lag up to 20 minutes, so a parcel may already
  be collected while the status still reads BOOKED. Verify before telling a customer the
  pickup failed.

## Contracts

* **Northstar, ACCT-001.** P1 15 min, P2 1h, P3 8 business hours. May cancel any BOOKED
  shipment before pickup with no fee, regardless of age. Credit capped at INR 5,000/month.
* **LumenWorks, ACCT-002.** No cancellation waiver. Fixed INR 300 credit when pickup runs
  more than 4 hours past the window, with carrier fault and no customer fault.

## Accounts

| Account | Name | Plan | Contract |
|---------|------|------|----------|
| ACCT-001 | Northstar Logistics | Enterprise | 05 |
| ACCT-002 | LumenWorks | Growth | 06 |
| ACCT-003 | Beacon Retail | Standard | none |
| ACCT-004 | Axis Labs | Enterprise | none |

## Orders

| Order | Acct | Status | Timing | Governing rule | Answer |
|-------|------|--------|--------|----------------|--------|
| ORD-1001 | Northstar | BOOKED | booked 09:00, cancel asked 11:00 (+120m), fee 4200 | Northstar §2 over SOP | Cancel, no fee. SOP alone would charge 250. |
| ORD-1002 | Northstar | PICKED_UP | picked up 09:35 | SOP + Northstar §2 | Cannot cancel, return-to-origin. |
| ORD-2001 | LumenWorks | BOOKED | booked 09:00, cancel asked 10:15 (+75m), fee 1800 | SOP v4, no waiver | INR 250 fee. |
| ORD-2002 | LumenWorks | BOOKED | window ended 06:30, not picked up (+4h30m), carrier fault, fee 2400 | LumenWorks §3 over SOP | Credit INR 300. Default would be 240. |
| ORD-3001 | Beacon | BOOKED | booked 10:25, cancel asked 10:40 (+15m), fee 1200 | SOP v4 | No fee, inside the 30-minute window. |
| ORD-4001 | Axis Labs | DELIVERED | delivered 2026-08-15 | SOP v4 | Cannot cancel. |

## Open tickets

* **TKT-501** Northstar, 10:30. "All shipment creation failing, HTTP 500 for every user."
  P1 outage, no workaround. Contract target 15 min, so breached at +30 min. Novel, not a
  known issue. Escalate.
* **TKT-502** LumenWorks, 09:45. "Bulk upload fails for 4,200-row CSV." KI-208, P2. Growth
  P2 is 4 business hours, so still within target.
* **TKT-503** Beacon, 10:05. "Change billing contact." P3 how-to.
* **TKT-504** Northstar, 10:50. "SwiftShip order still BOOKED after pickup 10 min ago."
  KI-211. Verify before saying the pickup failed.
* **TKT-505** Axis Labs, 08:30. "Possible API key exposure." P1 security. Enterprise P1
  target 30 min, so badly breached at +2h30m. Escalate.

## Closed tickets that give wrong advice

These are the sharpest traps in the pack. Both look authoritative and both are wrong,
which is why ticket history is returned as context with a warning, never as a source.

* **TKT-450**, Northstar. Says the INR 250 fee applies after 30 minutes. Their contract
  waives it. This one sits directly behind ORD-1001.
* **TKT-451**, LumenWorks. Says the Growth plan supports only 3,000 rows. The real limit
  is 5,000; 3,000 is only where KI-208 starts failing.

## When to escalate

* Equal-authority sources conflict, or the governing source is silent.
* A goodwill or exception call, or a credit above INR 1,000.
* A P1, or a breached SLA.
* A security incident.
* An action the system cannot take.
* No citation to ground the answer on.
