"""Trusted session context. Populated at (mock) login, never by model output.

Access control keys off this object inside the tool layer, so no prompt wording
can widen a caller's scope.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Role(str, Enum):
    CUSTOMER = "customer"   # scoped to exactly one account
    OPS = "ops"             # authorised ParcelPilot staff; cross-account, logged


@dataclass(frozen=True)
class Session:
    role: Role
    account_id: str | None = None   # required for CUSTOMER; ignored for OPS
    user_name: str = ""

    def __post_init__(self) -> None:
        if self.role == Role.CUSTOMER and not self.account_id:
            raise ValueError("Customer sessions must be bound to an account_id.")

    @property
    def is_ops(self) -> bool:
        return self.role == Role.OPS

    def can_access_account(self, account_id: str) -> bool:
        """The single source of truth for account scoping."""
        if self.role == Role.OPS:
            return True
        return account_id == self.account_id

    def label(self) -> str:
        if self.is_ops:
            return f"Ops · {self.user_name or 'staff'}"
        return f"Customer · {self.account_id}"
