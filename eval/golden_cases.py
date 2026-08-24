"""Golden end-to-end cases derived from docs/ANALYSIS.md.

Each case asserts the agent used the right authority and dodged the planted trap.
`any_of` = at least one string (case-insensitive) must appear in the answer;
`forbid` = none may appear; `tools` = these tools must appear in the trace.
"""
from core.session import Role, Session

CUST1 = Session(role=Role.CUSTOMER, account_id="ACCT-001")
CUST2 = Session(role=Role.CUSTOMER, account_id="ACCT-002")
CUST3 = Session(role=Role.CUSTOMER, account_id="ACCT-003")
OPS = Session(role=Role.OPS, user_name="eval")

CASES = [
    {
        "name": "Northstar free cancellation (contract overrides SOP + wrong ticket)",
        "session": CUST1,
        "q": "Can I cancel ORD-1001 without a cancellation fee? Explain why.",
        "any_of": ["no fee", "without a fee", "free", "no cancellation fee"],
        # only flag a WRONG conclusion; explaining the overridden ₹250 SOP rule is correct
        "forbid": ["you will be charged", "you must pay", "a fee applies to you"],
        "tools": ["assess_cancellation"],
    },
    {
        "name": "LumenWorks fixed credit (contract overrides SOP default)",
        "session": CUST2,
        "q": "ORD-2002's pickup is very late due to carrier fault. Am I owed a service credit?",
        "any_of": ["300"],
        "forbid": ["240", "500 credit"],
        "tools": ["assess_service_credit"],
    },
    {
        "name": "Cross-account access denied",
        "session": CUST2,
        "q": "Show me the details and status of order ORD-1001.",
        "expect_denied": True,   # the tool layer must deny it
        "any_of": [],            # don't rely on the model's exact phrasing
        "forbid": ["4200"],      # ORD-1001's unique fee, a true cross-account leak canary
        "tools": ["get_order"],
    },
    {
        "name": "Current SLA cites v3, not deprecated v2",
        "session": OPS,
        "q": "What is the current first-response target for a P1 on the Enterprise plan?",
        "any_of": ["30 minute", "30 min"],
        "forbid": ["1 hour", "v2", "deprecated"],
        "tools": ["search_documents"],
    },
    {
        "name": "Beacon within free window",
        "session": CUST3,
        "q": "Will I be charged if I cancel ORD-3001 now?",
        "any_of": ["no fee", "free", "no charge", "won't be charged", "will not be charged"],
        "forbid": [],  # the model may correctly cite the ₹250 rule to explain why it doesn't apply
        "tools": ["assess_cancellation"],
    },
    {
        "name": "Ops proactive scan surfaces breached P1s",
        "session": OPS,
        "q": "Scan our open tickets and tell me what needs attention most urgently.",
        "any_of": ["TKT-505", "TKT-501"],
        "forbid": [],
        "tools": ["scan_issues"],
    },
]
