from dataclasses import asdict
from typing import Any

from .hook import watchdog_hook
from .models import AuditEvent, WatchdogBlocked


class ExpenseService:
    def __init__(self) -> None:
        self.audit: list[AuditEvent] = []
        self.decisions: dict[str, str] = {}

    def record(self, event: AuditEvent) -> None:
        self.audit.append(event)

    @watchdog_hook(required_scope="expenses:approve")
    def approve_expense(self, expense: dict[str, Any], decision: str, scopes: list[str]) -> dict[str, str]:
        self.decisions[expense["expense_id"]] = decision
        return {"expense_id": expense["expense_id"], "decision": decision}

    def evaluate(self, expense: dict[str, Any], scopes: list[str]) -> dict[str, Any]:
        decision = "approved" if expense.get("amount", 0) <= 500 else "needs_review"
        try:
            result = self.approve_expense(expense=expense, decision=decision, scopes=scopes)
            return {"status": "allowed", "result": result, "audit": [asdict(e) for e in self.audit]}
        except WatchdogBlocked as blocked:
            return {"status": "blocked", "reason": blocked.event.reason, "audit": [asdict(e) for e in self.audit]}


# The API demo has a single service instance. Production: inject a request-scoped,
# durable audit sink (Postgres/SIEM) instead of this in-memory store.
_active_service = ExpenseService()
