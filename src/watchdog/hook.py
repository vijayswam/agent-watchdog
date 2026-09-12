"""The framework-agnostic, fail-closed tool interception layer."""
from collections.abc import Callable
from functools import wraps
from typing import Any

from .models import AuditEvent, WatchdogBlocked


AuditSink = Callable[[AuditEvent], None]


def watchdog_hook(*, sink: AuditSink | None = None, required_scope: str | None = None):
    """Gate a Python tool before it can touch a consequential system.

    Checks are deliberately performed before the wrapped function. A caller cannot
    receive a partial side effect after a failed validation.
    """
    def decorate(tool: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(tool)
        def guarded(*args: Any, **kwargs: Any) -> Any:
            event_sink = sink or getattr(args[0], "record", None)
            if event_sink is None:
                raise RuntimeError("watchdog_hook needs a sink or an instance record(event) method")
            expense = kwargs.get("expense") or next(
                (item for item in args if isinstance(item, dict) and "expense_id" in item), {}
            )
            expense_id = str(expense.get("expense_id", "unknown"))
            checks = {
                "data_quality": _data_quality(expense),
                "tamper": _tamper_check(expense),
                "scope_injection": _scope_check(kwargs, required_scope),
            }
            failures = [name for name, status in checks.items() if status != "pass"]
            if failures:
                event = AuditEvent(expense_id, tool.__name__, "blocked", checks,
                                   f"Failed runtime check(s): {', '.join(failures)}")
                event_sink(event)
                raise WatchdogBlocked(event)
            event = AuditEvent(expense_id, tool.__name__, "allowed", checks)
            event_sink(event)
            return tool(*args, **kwargs)
        return guarded
    return decorate


def _data_quality(expense: dict[str, Any]) -> str:
    required = ("expense_id", "amount", "category", "submitted_at")
    if any(expense.get(field) in (None, "") for field in required):
        return "fail: missing required field"
    return "pass" if isinstance(expense["amount"], (int, float)) and expense["amount"] > 0 else "fail: invalid amount"


def _tamper_check(expense: dict[str, Any]) -> str:
    return "fail: fixture marked tampered" if expense.get("fixture_hash") == "TAMPERED" else "pass"


def _scope_check(arguments: dict[str, Any], required_scope: str | None) -> str:
    text = " ".join(str(value).lower() for value in arguments.values())
    if any(token in text for token in ("ignore previous", "system prompt", "override policy")):
        return "fail: injection-shaped input"
    scopes = set(arguments.get("scopes", []))
    return "pass" if not required_scope or required_scope in scopes else "fail: missing scope"
