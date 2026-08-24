"""Append-only mock store for state-changing actions.

Actions (escalations, ticket updates, follow-up tasks) are proposed first and only
written on explicit confirmation (enforced in the tool layer). Persisted here to a
JSON file so the UI can show state actually changing during a demo.
"""
from __future__ import annotations

import json

from core import config

_VALID_KINDS = {"escalation", "ticket_update", "follow_up_task"}


class ActionStore:
    def __init__(self):
        self.path = config.ACTIONS_STORE
        self.actions: list[dict] = []
        if self.path.exists():
            try:
                self.actions = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                self.actions = []

    def _save(self) -> None:
        self.path.write_text(json.dumps(self.actions, indent=2, ensure_ascii=False),
                             encoding="utf-8")

    def next_id(self, kind: str) -> str:
        prefix = {"escalation": "ESC", "ticket_update": "UPD", "follow_up_task": "TSK"}[kind]
        n = sum(1 for a in self.actions if a["kind"] == kind) + 1
        return f"{prefix}-{n:03d}"

    def record(self, *, kind: str, payload: dict, created_by: str, created_at_iso: str) -> dict:
        if kind not in _VALID_KINDS:
            raise ValueError(f"Unknown action kind: {kind}")
        action = {
            "action_id": self.next_id(kind),
            "kind": kind,
            "payload": payload,
            "created_by": created_by,
            "created_at": created_at_iso,
            "status": "executed",
        }
        self.actions.append(action)
        self._save()
        return action

    def list_all(self) -> list[dict]:
        return list(self.actions)


_STORE: ActionStore | None = None


def get_store() -> ActionStore:
    global _STORE
    if _STORE is None:
        _STORE = ActionStore()
    return _STORE
