# Data Analysis (Ground Truth)

Notes from reading the pack before writing code, so the system is built against the
real data. The values here are what the unit tests check.

Reference "now" is the workbook snapshot: **2026-08-16 11:00 Asia/Kolkata**. All time
math (SLA breaches, cancellation windows, pickup delays) uses this, not the real clock.
Currency is INR. The dataset is synthetic.

## Source authority

Support Policy v3 §1 gives the precedence rule, so I use its own words:

1. Signed customer agreement (only for its own account, while in term).
2. Current policy, SOP, and product docs.
3. Historical tickets and internal notes: context only, may be wrong, never authority.

Support Policy v2 is stamped DEPRECATED and must never answer a current request, even
though it is a close match for SLA questions. Within the same tier, the later effective
date wins, and a source only applies if it is in effect at the snapshot time and in scope
for the account.

## The documents

| Doc | Status | Effective | Governs | Trap |
|-----|--------|-----------|---------|------|
| 01 Support Policy v3 | CURRENT | 2026-05-01 | Severity + first-response SLA by plan; precedence rule | this is the authority |
| 02 Support Policy v2 | DEPRECATED | 2025-01-01 | Old, longer SLA targets | must never be used, looks relevant |
| 03 Cancellation & Service Credit SOP v4 | CURRENT | 2026-06-15 | Cancel fees by status; failed-pickup credit; approvals | defaults that contracts override |
| 04 Product Ops Guide + Known Issues | CURRENT | 2026-08-14 | Plan limits; KI-208, KI-211 | real limit 5000 vs failures ~3000; webhook delay |
| 05 Northstar Agreement | ACTIVE | 2026 term | ACCT-001 custom SLA + free cancellation | overrides SOP/policy |
| 06 LumenWorks Agreement | ACTIVE | 2026-03 to 2027-02 | ACCT-002 custom credit | overrides SOP credit |

Key SOP v4 rules: DRAFT cancels free; BOOKED and not picked up cancels free within 30
minutes of booking, otherwise INR 250 unless a contract waives it; PICKED_UP uses
return-to-origin; DELIVERED cannot cancel. Failed-pickup credit by default needs pickup
more than 2 hours past the window end, carrier at fault, no customer fault, and pays the
lower of INR 500 or 10% of the fee. Credits above INR 1,000 need manager approval, and
you do not promise a credit when fault or timing is unknown.

Known issues: KI-208, bulk upload fails above roughly 3,000 rows although the real limit
is 5,000 (workaround: split below 3,000). KI-211, SwiftShip pickup webhooks can lag up to
20 minutes, so a parcel may be collected while the status still shows BOOKED; verify
before telling a customer the pickup failed.

Contracts: Northstar (ACCT-001) has P1 15 min, P2 1h, P3 8 business hours, and may cancel
any BOOKED shipment before pickup with no fee regardless of age; credits capped at INR
5,000/month. LumenWorks (ACCT-002) has no cancellation waiver, and a fixed INR 300 credit
when pickup is more than 4 hours past the window with carrier fault and no customer fault.

## Accounts

| Account | Name | Plan | Contract |
|---------|------|------|----------|
| ACCT-001 | Northstar Logistics | Enterprise | 05 |
| ACCT-002 | LumenWorks | Growth | 06 |
| ACCT-003 | Beacon Retail | Standard | none |
| ACCT-004 | Axis Labs | Enterprise | none |

## Orders (snapshot 2026-08-16 11:00)

| Order | Acct | Status | Timing | Governing rule | Answer |
|-------|------|--------|--------|----------------|--------|
| ORD-1001 | Northstar | BOOKED | booked 09:00, cancel req 11:00 (+120m), fee 4200 | Northstar §2 over SOP | Cancel, no fee. SOP alone would charge 250. |
| ORD-1002 | Northstar | PICKED_UP | picked up 09:35 | SOP + Northstar §2 | Cannot cancel; return-to-origin. |
| ORD-2001 | LumenWorks | BOOKED | booked 09:00, cancel req 10:15 (+75m), fee 1800 | SOP v4, no waiver | INR 250 fee. |
| ORD-2002 | LumenWorks | BOOKED | window ends 06:30, not picked up (+4h30m), carrier fault, fee 2400 | LumenWorks §3 over SOP | Credit INR 300. Default would be 240. |
| ORD-3001 | Beacon | BOOKED | booked 10:25, cancel req 10:40 (+15m), fee 1200 | SOP v4 | No fee, within 30-min window. |
| ORD-4001 | Axis Labs | DELIVERED | delivered 2026-08-15 | SOP v4 | Cannot cancel. |

## Tickets

Open:

* TKT-501, Northstar, 10:30, "all shipment creation failing, HTTP 500 for every user".
  P1 outage, no workaround. Northstar P1 target 15 min, so breached at +30 min. Novel,
  not a known issue. Escalate.
* TKT-502, LumenWorks, 09:45, "bulk upload fails for 4,200-row CSV". Matches KI-208. P2.
  Growth P2 is 4 business hours, so within target. Workaround: split below 3,000.
* TKT-503, Beacon, 10:05, "change billing contact". P3 how-to.
* TKT-504, Northstar, 10:50, "SwiftShip order still BOOKED after pickup 10 min ago".
  Matches KI-211; verify before saying the pickup failed.
* TKT-505, Axis Labs, 08:30, "possible API key exposure". P1 security. Enterprise P1
  target 30 min, so badly breached at +2h30m. Escalate.

Closed, and both contain wrong guidance:

* TKT-450, Northstar, says a INR 250 fee applies after 30 min. Wrong for Northstar, the
  contract waives it. This is the trap behind ORD-1001.
* TKT-451, LumenWorks, says the Growth plan supports only 3,000 rows. Wrong, the limit is
  5,000; 3,000 is only the KI-208 failure threshold.

## Traps to handle (these become tests)

1. v2 is a strong match for SLA queries but must never be used; use v3.
2. Northstar cancellation is free (contract over SOP).
3. LumenWorks credit is INR 300 (contract over SOP default).
4. TKT-450 and TKT-451 are wrong; ignore them.
5. TKT-504 is the KI-211 webhook delay, not a lost pickup.
6. All time math uses the snapshot.
7. Credit above INR 1,000 needs manager approval.
8. Cross-account reads must be denied at the data layer.
9. Do not promise a credit when fault or timing is unknown.
10. PICKED_UP and DELIVERED orders cannot be cancelled.

## When to escalate

Equal-authority sources conflict or the governing source is silent; a goodwill or
exception decision, or a credit above INR 1,000; a P1 or a breached SLA; a security
incident; an action outside the system; or no citation to ground the answer.
