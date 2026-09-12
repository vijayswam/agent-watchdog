from watchdog.service import ExpenseService


def clean_expense():
    return {"expense_id": "EXP-101", "amount": 140, "category": "travel", "submitted_at": "2026-09-12"}


def test_approval_is_gated_and_allowed():
    service = ExpenseService()
    # The production decorator's global sink is exercised separately; this asserts the workflow shape.
    result = service.evaluate(clean_expense(), ["expenses:approve"])
    assert result["status"] == "allowed"
    assert service.audit[-1].outcome == "allowed"


def test_tampered_fixture_is_blocked_before_write():
    service = ExpenseService()
    expense = clean_expense() | {"fixture_hash": "TAMPERED"}
    result = service.evaluate(expense, ["expenses:approve"])
    assert result["status"] == "blocked"
    assert expense["expense_id"] not in service.decisions
    assert service.audit[-1].outcome == "blocked"
