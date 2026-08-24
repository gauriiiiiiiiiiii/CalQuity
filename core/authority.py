"""Source authority model.

Support Policy v3 §1 states the precedence explicitly:
  signed customer agreement > current support policy > current product documentation;
  historical tickets and internal notes are context only and may be wrong.

We encode that ordering as numeric tiers and attach authority metadata to every
supplied document. Deprecated documents are retained for reference but must never
supply an answer.
"""
from __future__ import annotations

from dataclasses import dataclass

# Higher tier wins. Gaps left between values so intermediate tiers can be added.
TIER_CONTRACT = 100        # signed customer agreement (scoped to its account)
TIER_CURRENT_POLICY = 80   # current support policy / SOP (operational rules)
TIER_CURRENT_DOC = 60      # current product documentation / known issues
TIER_DEPRECATED = 10       # retained for history, never governs
TIER_TICKET_HISTORY = 5    # past ticket resolutions, untrusted context only

TIER_NAMES = {
    TIER_CONTRACT: "customer agreement",
    TIER_CURRENT_POLICY: "current policy/SOP",
    TIER_CURRENT_DOC: "current product doc",
    TIER_DEPRECATED: "deprecated",
    TIER_TICKET_HISTORY: "historical ticket",
}


@dataclass(frozen=True)
class SourceMeta:
    doc_id: str
    filename: str
    title: str
    tier: int
    status: str            # CURRENT | DEPRECATED | ACTIVE
    effective: str         # ISO-ish effective date/term, as printed in the doc
    governs_account: str | None = None   # set for contracts
    usable: bool = True    # False => never returned as an answer source

    @property
    def tier_name(self) -> str:
        return TIER_NAMES.get(self.tier, "unknown")


# Metadata assigned deterministically from the supplied filenames and headers, not guessed.
SOURCE_REGISTRY: dict[str, SourceMeta] = {
    "01_Support_Policy_v3_CURRENT.pdf": SourceMeta(
        "support_policy_v3", "01_Support_Policy_v3_CURRENT.pdf",
        "Support Policy v3 (CURRENT)", TIER_CURRENT_POLICY, "CURRENT", "2026-05-01",
    ),
    "02_Support_Policy_v2_DEPRECATED.pdf": SourceMeta(
        "support_policy_v2", "02_Support_Policy_v2_DEPRECATED.pdf",
        "Support Policy v2 (DEPRECATED)", TIER_DEPRECATED, "DEPRECATED", "2025-01-01",
        usable=False,
    ),
    "03_Cancellation_and_Service_Credit_SOP_v4.pdf": SourceMeta(
        "cancellation_sop_v4", "03_Cancellation_and_Service_Credit_SOP_v4.pdf",
        "Cancellation & Service Credit SOP v4 (CURRENT)", TIER_CURRENT_POLICY, "CURRENT",
        "2026-06-15",
    ),
    "04_Product_Operations_Guide_and_Known_Issues.pdf": SourceMeta(
        "product_ops_guide", "04_Product_Operations_Guide_and_Known_Issues.pdf",
        "Product Operations Guide & Known Issues (CURRENT)", TIER_CURRENT_DOC, "CURRENT",
        "2026-08-14",
    ),
    "05_Northstar_Logistics_Enterprise_Agreement.pdf": SourceMeta(
        "northstar_agreement", "05_Northstar_Logistics_Enterprise_Agreement.pdf",
        "Northstar Logistics Enterprise Agreement", TIER_CONTRACT, "ACTIVE",
        "2026-01-01 to 2026-12-31", governs_account="ACCT-001",
    ),
    "06_LumenWorks_Service_Agreement.pdf": SourceMeta(
        "lumenworks_agreement", "06_LumenWorks_Service_Agreement.pdf",
        "LumenWorks Service Agreement", TIER_CONTRACT, "ACTIVE",
        "2026-03-01 to 2027-02-28", governs_account="ACCT-002",
    ),
}

BY_DOC_ID = {m.doc_id: m for m in SOURCE_REGISTRY.values()}


def meta_for_file(filename: str) -> SourceMeta | None:
    return SOURCE_REGISTRY.get(filename)


def contract_for_account(account_id: str) -> SourceMeta | None:
    for m in SOURCE_REGISTRY.values():
        if m.tier == TIER_CONTRACT and m.governs_account == account_id:
            return m
    return None


@dataclass
class Resolution:
    governing: SourceMeta | None
    considered: list[SourceMeta]
    conflict: bool
    note: str


def resolve(sources: list[SourceMeta], account_id: str | None = None) -> Resolution:
    """Pick the governing source among candidates.

    Rules: drop unusable (deprecated) and out-of-scope contracts; the highest tier
    wins; a tie at the top tier flags a conflict for human review.
    """
    usable = [
        s for s in sources
        if s.usable
        and not (s.tier == TIER_CONTRACT and account_id and s.governs_account != account_id)
    ]
    if not usable:
        return Resolution(None, sources, False, "No usable (non-deprecated, in-scope) source.")

    usable.sort(key=lambda s: s.tier, reverse=True)
    top = usable[0].tier
    top_sources = [s for s in usable if s.tier == top]
    if len(top_sources) > 1:
        names = ", ".join(s.title for s in top_sources)
        return Resolution(None, usable, True,
                          f"Conflict: {len(top_sources)} equal-authority sources ({names}).")
    return Resolution(top_sources[0], usable, False,
                      f"Governed by {top_sources[0].title} ({top_sources[0].tier_name}).")
