"""Proactive Issue Detection (the chosen additional problem).

Pure, snapshot-aware analysis over tickets/orders that surfaces what deserves
attention now: SLA breaches, high severity, novelty (known-issue vs new), security,
and clusters. Ops-only. Each item carries a one-line 'why it matters'.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from core.session import Session
from data_layer import datastore

SEV_RANK = {"P1": 3, "P2": 2, "P3": 1}

# Known issues from Product Operations Guide (#04), for cross-referencing tickets.
KNOWN_ISSUES = [
    {"id": "KI-208", "label": "Bulk Upload failures on large CSVs",
     "keywords": ["bulk upload", "csv", "rows", "upload fail", "70%"]},
    {"id": "KI-211", "label": "SwiftShip pickup webhook delay",
     "keywords": ["swiftship", "still shows booked", "still booked", "booked after",
                  "pickup", "webhook", "shows booked"]},
]

# Product areas for clustering + blast-radius.
CLUSTERS = [
    {"tag": "bulk-upload", "keywords": ["bulk upload", "csv", "rows"]},
    {"tag": "pickup-status", "keywords": ["booked after", "still shows booked", "pickup", "webhook"]},
    {"tag": "security", "keywords": ["api key", "credential", "exposure", "leak", "password"]},
    {"tag": "billing-account", "keywords": ["billing", "contact", "invoice"]},
    {"tag": "outage", "keywords": ["all ", "every user", "500", "outage", "cannot create", "failing"]},
]


def classify_severity(subject: str, description: str) -> tuple[str, str]:
    """Heuristic P1/P2/P3 from Support Policy v3 definitions. Returns (severity, why)."""
    text = f"{subject} {description}".lower()
    p1_security = any(k in text for k in ["api key", "credential", "exposure", "key exposure"])
    p1_outage = (("all " in text or "every user" in text) and
                 any(k in text for k in ["fail", "500", "cannot create", "error"]))
    if p1_security:
        return "P1", "Suspected credential exposure (v3: security incident)."
    if p1_outage:
        return "P1", "Complete creation outage, no workaround (v3: production outage)."
    if any(k in text for k in ["fail", "degraded", "bulk upload", "unavailable"]):
        return "P2", "Major feature degraded but a workaround exists (v3: P2)."
    return "P3", "Minor issue / how-to (v3: P3)."


def match_known_issue(subject: str, description: str) -> dict | None:
    text = f"{subject} {description}".lower()
    for ki in KNOWN_ISSUES:
        if any(k in text for k in ki["keywords"]):
            return {"id": ki["id"], "label": ki["label"]}
    return None


def cluster_tag(subject: str, description: str) -> str:
    text = f"{subject} {description}".lower()
    for c in CLUSTERS:
        if any(k in text for k in c["keywords"]):
            return c["tag"]
    return "other"


@dataclass
class RadarItem:
    ticket_id: str
    account_id: str
    account_name: str
    subject: str
    severity: str
    severity_why: str
    sla: dict
    known_issue: dict | None
    novel: bool
    cluster: str
    priority: float = 0.0
    why: str = ""


def build_radar(session: Session) -> dict:
    """Ops-only. Returns ranked open-ticket items + cluster summary."""
    if not session.is_ops:
        return {"error": "access_denied", "message": "Proactive detection is ops-only."}

    store = datastore.get_store()
    now = store.snapshot
    items: list[RadarItem] = []

    for t in store.list_tickets(session, include_closed=False):
        acct = store.accounts.get(t["account_id"], {})
        plan = acct.get("plan", "Standard")
        contract = datastore.CONTRACT_TERMS.get(t["account_id"], {}).get("sla")
        sev, sev_why = classify_severity(t.get("subject", ""), t.get("description", ""))
        sla = datastore.assess_sla(created_at=t["created_at"], now=now, severity=sev,
                                   plan=plan, contract_sla=contract)
        ki = match_known_issue(t.get("subject", ""), t.get("description", ""))
        novel = ki is None and sev == "P1"
        item = RadarItem(
            ticket_id=t["ticket_id"], account_id=t["account_id"],
            account_name=acct.get("account_name", t["account_id"]),
            subject=t.get("subject", ""), severity=sev, severity_why=sev_why,
            sla=sla, known_issue=ki, novel=novel,
            cluster=cluster_tag(t.get("subject", ""), t.get("description", "")),
        )
        # Priority: breached first, then severity, then least time remaining.
        item.priority = (
            (1000 if sla["breached"] else 0)
            + SEV_RANK.get(sev, 1) * 100
            - sla["remaining_min"] / 10.0
        )
        reasons = []
        if sla["breached"]:
            reasons.append(f"SLA BREACHED (+{sla['elapsed_min']-sla['target_min']} min over target)")
        else:
            reasons.append(f"{sla['remaining_min']} min to SLA")
        if sev == "P1":
            reasons.append("P1")
        if novel:
            reasons.append("novel, not a known issue")
        elif ki:
            reasons.append(f"matches {ki['id']}")
        item.why = " · ".join(reasons)
        items.append(item)

    items.sort(key=lambda i: i.priority, reverse=True)

    # Cluster / blast-radius summary.
    clusters: dict[str, dict] = {}
    for it in items:
        c = clusters.setdefault(it.cluster, {"tickets": [], "accounts": set()})
        c["tickets"].append(it.ticket_id)
        c["accounts"].add(it.account_id)
    cluster_summary = [
        {"tag": tag, "ticket_count": len(v["tickets"]), "account_count": len(v["accounts"]),
         "tickets": v["tickets"]}
        for tag, v in sorted(clusters.items(), key=lambda kv: -len(kv[1]["tickets"]))
    ]

    return {
        "snapshot": now.isoformat(),
        "items": [i.__dict__ for i in items],
        "clusters": cluster_summary,
        "breached_count": sum(1 for i in items if i.sla["breached"]),
    }
