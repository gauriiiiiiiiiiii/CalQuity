"""Streamlit UI for the ParcelPilot support agent.

One agent, two roles via a mock login. The chat shows which tools ran, and any
state-changing action needs a confirmation click. Ops also gets the Radar tab.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Make the repo root importable when launched via `streamlit run app/streamlit_app.py`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

# Hosted deployments supply config through st.secrets, local runs through .env. Mirror
# secrets into the environment before core.config reads them, so one code path covers both.
try:
    for _key in ("LLM_API_KEY", "LLM_MODEL", "LLM_BASE_URL"):
        if _key in st.secrets and not os.getenv(_key):
            os.environ[_key] = str(st.secrets[_key])
except Exception:  # no secrets file locally, which is fine
    pass

from core import agent, config
from core.session import Role, Session
from data_layer import actionstore, datastore

st.set_page_config(page_title="ParcelPilot Support Agent", page_icon="📦", layout="wide")

TOOL_ICONS = {
    "search_documents": "📄", "get_order": "📦", "get_account": "🏢",
    "list_orders": "📦", "get_ticket": "🎫", "list_tickets": "🎫",
    "assess_cancellation": "🧮", "assess_service_credit": "🧮", "assess_sla": "⏱️",
    "scan_issues": "🛰️", "prepare_action": "⚙️",
}


# --- Session state -----------------------------------------------------------
def _reset_chat():
    st.session_state.history = []
    st.session_state.chat = []
    st.session_state.pending = None


if "session" not in st.session_state:
    st.session_state.session = None
if "history" not in st.session_state:
    _reset_chat()


# --- Sidebar: mock login -----------------------------------------------------
ds = datastore.get_store()

with st.sidebar:
    st.title("📦 ParcelPilot")
    st.caption("AI support agent · mock login")

    role = st.radio("Sign in as", ["Customer", "Ops / Support staff"], key="role_choice")
    if role == "Customer":
        accts = list(ds.accounts.keys())
        labels = {a: f"{a} · {ds.accounts[a]['account_name']}" for a in accts}
        acct = st.selectbox("Account", accts, format_func=lambda a: labels[a])
        if st.button("Sign in", use_container_width=True):
            st.session_state.session = Session(role=Role.CUSTOMER, account_id=acct)
            _reset_chat()
    else:
        name = st.text_input("Your name", value="Priya (Ops)")
        if st.button("Sign in", use_container_width=True):
            st.session_state.session = Session(role=Role.OPS, user_name=name)
            _reset_chat()

    if st.session_state.session:
        st.success(f"Signed in: {st.session_state.session.label()}")
        if st.button("Reset conversation", use_container_width=True):
            _reset_chat()

    st.divider()
    st.caption(f"Dataset snapshot (\"now\"):\n**{ds.snapshot.isoformat()}**")
    if not config.llm_available():
        st.warning("No LLM_API_KEY set, so chat is disabled. The Radar tab still works. "
                   "Add the key to .env to enable the agent.")

    st.divider()
    with st.expander("Recorded actions"):
        acts = actionstore.get_store().list_all()
        if not acts:
            st.caption("None yet.")
        for a in reversed(acts):
            st.write(f"**{a['action_id']}** · {a['kind']} · {a['created_by']}")
            st.caption(a["payload"].get("summary", ""))


session: Session | None = st.session_state.session
if session is None:
    st.info("👈 Sign in as a customer or ops user to begin.")
    st.stop()


# --- Rendering helpers -------------------------------------------------------
def render_trace(trace):
    if not trace:
        return
    with st.expander(f"🔧 Tools used ({len(trace)})", expanded=False):
        for step in trace:
            icon = TOOL_ICONS.get(step.tool, "🔧")
            st.markdown(f"{icon} **{step.tool}**  `{step.args}`")
            st.json(step.result, expanded=False)


def confirm_action(pending: dict):
    st.warning(f"**Confirm {pending['kind']}.** This will change state.")
    st.markdown(f"**{pending['summary']}**")
    st.caption(pending["details"])
    if pending.get("related_ids"):
        st.caption("Related: " + ", ".join(pending["related_ids"]))
    c1, c2 = st.columns(2)
    if c1.button("✅ Confirm & execute", key="confirm_btn"):
        rec = actionstore.get_store().record(
            kind=pending["kind"],
            payload={k: pending[k] for k in ("summary", "details", "related_ids", "priority")
                     if k in pending},
            created_by=session.label(), created_at_iso=ds.snapshot.isoformat())
        st.session_state.chat.append({
            "role": "assistant",
            "content": f"✅ Executed **{rec['action_id']}** ({rec['kind']}).",
            "trace": []})
        st.session_state.history.append(
            {"role": "assistant", "content": f"Action {rec['action_id']} was confirmed and executed."})
        st.session_state.pending = None
        st.rerun()
    if c2.button("✖ Cancel", key="cancel_btn"):
        st.session_state.chat.append({
            "role": "assistant", "content": "Okay, I won't create that action.", "trace": []})
        st.session_state.pending = None
        st.rerun()


# --- Tabs --------------------------------------------------------------------
tab_chat, tab_radar = st.tabs(["💬 Chat", "🛰️ Ops Radar"])

with tab_chat:
    st.subheader(f"Support chat · {session.label()}")

    for turn in st.session_state.chat:
        with st.chat_message(turn["role"]):
            st.markdown(turn["content"])
            render_trace(turn.get("trace", []))

    if st.session_state.pending:
        confirm_action(st.session_state.pending)

    disabled = not config.llm_available() or st.session_state.pending is not None
    prompt = st.chat_input("Ask about an order, policy, credit, SLA…", disabled=disabled)
    if prompt:
        st.session_state.chat.append({"role": "user", "content": prompt, "trace": []})
        with st.spinner("Thinking…"):
            try:
                res = agent.run_agent(prompt, session, history=st.session_state.history)
                st.session_state.history = res.messages
                st.session_state.chat.append(
                    {"role": "assistant", "content": res.answer or "(no answer)",
                     "trace": res.trace})
                st.session_state.pending = res.pending_action
            except Exception as e:
                st.session_state.chat.append(
                    {"role": "assistant", "content": f"⚠️ Error: {e}", "trace": []})
        st.rerun()

with tab_radar:
    st.subheader("Proactive Issue Detection")
    if not session.is_ops:
        st.info("The Radar is available to ops/support staff only. Sign in as ops to view it.")
    else:
        from core import detection
        radar = detection.build_radar(session)
        top = st.columns(3)
        top[0].metric("Open tickets", len(radar["items"]))
        top[1].metric("SLA breached", radar["breached_count"])
        top[2].metric("Clusters", len(radar["clusters"]))

        st.markdown("#### What needs attention (ranked)")
        for it in radar["items"]:
            sev = it["severity"]
            badge = {"P1": "🔴", "P2": "🟠", "P3": "🟢"}.get(sev, "⚪")
            breach = "⛔ BREACHED" if it["sla"]["breached"] else "on track"
            with st.expander(f"{badge} {it['ticket_id']} · {it['account_name']} · {sev} · {breach}"):
                st.markdown(f"**{it['subject']}**")
                st.caption(it["why"])
                st.write(f"Severity rationale: {it['severity_why']}")
                st.json(it["sla"], expanded=False)
                if st.button("Prepare escalation", key=f"esc_{it['ticket_id']}"):
                    st.session_state.pending = {
                        "proposal": True, "requires_confirmation": True, "kind": "escalation",
                        "summary": f"Escalate {it['ticket_id']} ({it['account_name']}, {sev})",
                        "details": f"{it['subject']}. {it['why']}. Severity: {it['severity_why']}",
                        "related_ids": [it["ticket_id"], it["account_id"]],
                        "priority": sev}
                    st.info("Escalation prepared. Go to the Chat tab to confirm.")

        st.markdown("#### Clusters / blast radius")
        for c in radar["clusters"]:
            st.write(f"**{c['tag']}**: {c['ticket_count']} ticket(s) across "
                     f"{c['account_count']} account(s): {', '.join(c['tickets'])}")
