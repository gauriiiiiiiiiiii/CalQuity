"""Ground-truth tests for the arithmetic and access rules the LLM must not get wrong.

Every expectation here comes from docs/ANALYSIS.md, derived from the actual data pack.
Snapshot "now" is 2026-08-16 11:00 IST.
"""
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from core import tools
from core.authority import (SOURCE_REGISTRY, TIER_CONTRACT, TIER_DEPRECATED, resolve)
from core.session import Role, Session
from data_layer import datastore, docstore

IST = ZoneInfo("Asia/Kolkata")
OPS = Session(role=Role.OPS, user_name="tester")
CUST1 = Session(role=Role.CUSTOMER, account_id="ACCT-001")
CUST2 = Session(role=Role.CUSTOMER, account_id="ACCT-002")


@pytest.fixture(scope="module")
def ds():
    return datastore.get_store()


# --- Snapshot ----------------------------------------------------------------
def test_snapshot_time(ds):
    assert ds.snapshot == datetime(2026, 8, 16, 11, 0, tzinfo=IST)


# --- Cancellation ------------------------------------------------------------
def test_ord1001_northstar_cancels_free(ds):
    r = tools.dispatch("assess_cancellation", {"order_id": "ORD-1001"}, CUST1)
    assert r["cancellable"] is True
    assert r["fee_inr"] == 0                      # contract waives the 250 fee
    assert r["fee_waived_by_contract"] is True
    assert r["minutes_since_booking"] == 120      # 09:00 -> 11:00
    assert any("Northstar" in c for c in r["citations"])


def test_ord2001_lumenworks_pays_fee(ds):
    r = tools.dispatch("assess_cancellation", {"order_id": "ORD-2001"}, CUST2)
    assert r["fee_inr"] == 250                     # 75 min, no waiver
    assert r["within_free_window"] is False


def test_ord3001_beacon_within_window_free(ds):
    r = tools.dispatch("assess_cancellation", {"order_id": "ORD-3001"}, OPS)
    assert r["fee_inr"] == 0                        # 15 min <= 30
    assert r["within_free_window"] is True


def test_ord1002_picked_up_not_cancellable(ds):
    r = tools.dispatch("assess_cancellation", {"order_id": "ORD-1002"}, OPS)
    assert r["cancellable"] is False
    assert r.get("next_step") == "return_to_origin"


def test_ord4001_delivered_not_cancellable(ds):
    r = tools.dispatch("assess_cancellation", {"order_id": "ORD-4001"}, OPS)
    assert r["cancellable"] is False


# --- Service credit ----------------------------------------------------------
def test_ord2002_lumenworks_fixed_credit(ds):
    r = tools.dispatch("assess_service_credit", {"order_id": "ORD-2002"}, CUST2)
    assert r["eligible"] is True
    assert r["credit_inr"] == 300                   # contract fixed, overrides default
    assert r["delay_hours"] == 4.5                   # window end 06:30 -> now 11:00
    assert r["needs_manager_approval"] is False


def test_default_credit_formula():
    # Synthetic: 3h late, carrier fault, no customer fault, fee 4200 -> min(500, 420) = 420
    now = datetime(2026, 8, 16, 11, 0, tzinfo=IST)
    end = datetime(2026, 8, 16, 8, 0, tzinfo=IST)
    r = datastore.assess_service_credit(
        carrier_fault=True, customer_fault=False, pickup_window_end=end,
        pickup_actual_at=None, now=now, shipment_fee=4200, credit_terms=None,
        credit_citation=None)
    assert r["eligible"] is True
    assert r["credit_inr"] == 420


def test_unknown_fault_no_promise():
    now = datetime(2026, 8, 16, 11, 0, tzinfo=IST)
    end = datetime(2026, 8, 16, 8, 0, tzinfo=IST)
    r = datastore.assess_service_credit(
        carrier_fault=None, customer_fault=None, pickup_window_end=end,
        pickup_actual_at=None, now=now, shipment_fee=1000, credit_terms=None,
        credit_citation=None)
    assert r["eligible"] is None


# --- SLA ---------------------------------------------------------------------
def test_tkt501_northstar_p1_breached(ds):
    r = tools.dispatch("assess_sla", {"ticket_id": "TKT-501", "severity": "P1"}, OPS)
    assert r["breached"] is True                    # 15-min contract target, 30 min elapsed
    assert r["target_min"] == 15
    assert r["sla_source"] == "contract"


def test_tkt505_axis_p1_breached(ds):
    r = tools.dispatch("assess_sla", {"ticket_id": "TKT-505", "severity": "P1"}, OPS)
    assert r["breached"] is True                    # 30-min Enterprise target, 150 min elapsed
    assert r["target_min"] == 30
    assert r["sla_source"] == "policy_v3"


# --- Access control ----------------------------------------------------------
def test_customer_cannot_read_other_account_order(ds):
    r = tools.dispatch("get_order", {"order_id": "ORD-1001"}, CUST2)  # ORD-1001 is ACCT-001
    assert r.get("error") == "access_denied"


def test_customer_can_read_own_order(ds):
    r = tools.dispatch("get_order", {"order_id": "ORD-2001"}, CUST2)
    assert r.get("order_id") == "ORD-2001"


def test_customer_list_orders_is_scoped(ds):
    r = tools.dispatch("list_orders", {"account_id": "ACCT-001"}, CUST2)  # tries to widen
    assert all(o["account_id"] == "ACCT-002" for o in r["orders"])


def test_scan_issues_ops_only():
    r = tools.dispatch("scan_issues", {}, CUST1)
    assert r.get("error") == "access_denied"


# --- Documents / authority ---------------------------------------------------
def test_deprecated_v2_excluded_by_default():
    store = docstore.get_store()
    hits = store.search("enterprise P1 first response target", top_k=5)
    ids = {h.chunk.doc_id for h in hits}
    assert "support_policy_v2" not in ids
    assert "support_policy_v3" in ids


def test_contract_only_visible_to_its_account():
    store = docstore.get_store()
    # A LumenWorks customer must not retrieve Northstar's agreement.
    hits = store.search("cancellation fee waiver", top_k=8, account_id="ACCT-002")
    assert all(h.chunk.governs_account in (None, "ACCT-002") for h in hits)


def test_authority_resolution_contract_wins():
    contract = SOURCE_REGISTRY["05_Northstar_Logistics_Enterprise_Agreement.pdf"]
    sop = SOURCE_REGISTRY["03_Cancellation_and_Service_Credit_SOP_v4.pdf"]
    dep = SOURCE_REGISTRY["02_Support_Policy_v2_DEPRECATED.pdf"]
    res = resolve([dep, sop, contract], account_id="ACCT-001")
    assert res.governing.tier == TIER_CONTRACT
    assert res.conflict is False


def test_deprecated_never_governs():
    dep = SOURCE_REGISTRY["02_Support_Policy_v2_DEPRECATED.pdf"]
    assert dep.tier == TIER_DEPRECATED and dep.usable is False
    res = resolve([dep], account_id=None)
    assert res.governing is None
