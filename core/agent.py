"""The agent loop: a plain tool-calling loop over an OpenAI-compatible endpoint.

No framework, so the control flow stays easy to follow. Returns the final answer plus
the tool-use trace and any pending action proposal awaiting confirmation.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field

from core import config, prompts, tools
from core.session import Session

MAX_STEPS = 8
_MAX_RETRIES = 5


@dataclass
class TraceStep:
    tool: str
    args: dict
    result: dict


@dataclass
class AgentResult:
    answer: str
    trace: list[TraceStep] = field(default_factory=list)
    pending_action: dict | None = None
    messages: list[dict] = field(default_factory=list)


def _client():
    if not config.LLM_API_KEY:
        raise RuntimeError(
            "No LLM API key set. Add LLM_API_KEY (or GROQ_API_KEY / XAI_API_KEY) to .env.")
    from openai import OpenAI
    return OpenAI(api_key=config.LLM_API_KEY, base_url=config.LLM_BASE_URL)


def _create_with_backoff(client, messages):
    """Call the model, retrying on transient rate limits (free-tier TPM caps)."""
    delay = 2.0
    for attempt in range(_MAX_RETRIES):
        try:
            return client.chat.completions.create(
                model=config.LLM_MODEL, messages=messages,
                tools=tools.TOOL_SCHEMAS, tool_choice="auto", temperature=0.1)
        except Exception as e:
            transient = "rate_limit" in str(e).lower() or getattr(e, "status_code", None) == 429
            if not transient or attempt == _MAX_RETRIES - 1:
                raise
            time.sleep(delay)
            delay *= 2
    raise RuntimeError("unreachable")


def run_agent(user_message: str, session: Session,
              history: list[dict] | None = None) -> AgentResult:
    """history: prior messages (including assistant/tool turns) to preserve context."""
    client = _client()
    messages: list[dict] = []
    if not history:
        messages.append({"role": "system", "content": prompts.build_system_prompt(session)})
    else:
        messages = list(history)
    messages.append({"role": "user", "content": user_message})

    trace: list[TraceStep] = []
    pending_action: dict | None = None

    for _ in range(MAX_STEPS):
        resp = _create_with_backoff(client, messages)
        msg = resp.choices[0].message

        assistant_msg: dict = {"role": "assistant", "content": msg.content or ""}
        if msg.tool_calls:
            assistant_msg["tool_calls"] = [
                {"id": tc.id, "type": "function",
                 "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in msg.tool_calls]
        messages.append(assistant_msg)

        if not msg.tool_calls:
            return AgentResult(answer=msg.content or "", trace=trace,
                               pending_action=pending_action, messages=messages)

        for tc in msg.tool_calls:
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            result = tools.dispatch(name, args, session)
            trace.append(TraceStep(tool=name, args=args, result=result))
            if name == "prepare_action" and result.get("proposal"):
                pending_action = result
            messages.append({"role": "tool", "tool_call_id": tc.id,
                             "content": json.dumps(result, ensure_ascii=False)})

    return AgentResult(
        answer=("I need more steps than allowed to answer this safely. I'm escalating to a human "
                "for review."),
        trace=trace, pending_action=pending_action, messages=messages)
