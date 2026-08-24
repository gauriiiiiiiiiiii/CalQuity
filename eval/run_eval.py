"""Run the golden cases end-to-end through the agent and report pass/fail.

Requires an LLM key (LLM_API_KEY). Run: ``python -m eval.run_eval``.
The deterministic layer (calculators, access, authority) is covered separately by
``pytest tests/`` and does not need an API key.
"""
from __future__ import annotations

import sys
import time

from core import agent, config
from eval.golden_cases import CASES

# Windows consoles default to cp1252; model replies may contain unicode punctuation.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def _norm(s: str) -> str:
    """Normalise unicode punctuation the model likes to emit (non-breaking hyphens,
    thin/nbsp spaces) so ASCII substring checks are robust."""
    for ch in ("‑", "‐", "‒", "–", "—"):  # various hyphens/dashes
        s = s.replace(ch, "-")
    for ch in (" ", " ", " ", " "):            # nbsp / thin spaces
        s = s.replace(ch, " ")
    return s.lower()


def _check(case: dict, res: "agent.AgentResult") -> tuple[bool, list[str]]:
    answer = _norm(res.answer or "")
    tools_used = {s.tool for s in res.trace}
    fails: list[str] = []

    if case.get("expect_denied"):
        denied = any(isinstance(s.result, dict) and s.result.get("error") == "access_denied"
                     for s in res.trace)
        if not denied:
            fails.append("expected a tool-layer access_denied in the trace")

    if case["any_of"] and not any(_norm(s) in answer for s in case["any_of"]):
        fails.append(f"expected one of {case['any_of']}")
    for bad in case.get("forbid", []):
        if _norm(bad) in answer:
            fails.append(f"must not contain '{bad}'")
    for t in case.get("tools", []):
        if t not in tools_used:
            fails.append(f"expected tool '{t}' (used: {sorted(tools_used)})")
    return (not fails), fails


def main() -> int:
    if not config.llm_available():
        print("No LLM API key set, so the agent-level eval cannot run.")
        print("Set it in .env, or run `pytest tests/` for the deterministic ground-truth layer.")
        return 2

    passed = 0
    for i, case in enumerate(CASES):
        if i:
            time.sleep(3)  # pace calls under free-tier TPM limits
        try:
            res = agent.run_agent(case["q"], case["session"])
            ok, fails = _check(case, res)
        except Exception as e:
            ok, fails, res = False, [f"exception: {type(e).__name__}: {e}"], None
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {case['name']}")
        if not ok:
            for f in fails:
                print(f"        - {f}")
            if res:
                print(f"        answer: {(res.answer or '')[:160]}")
        passed += ok

    print(f"\n{passed}/{len(CASES)} cases passed.")
    return 0 if passed == len(CASES) else 1


if __name__ == "__main__":
    sys.exit(main())
