from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any, Literal


@dataclass(frozen=True)
class AuditEvent:
    expense_id: str
    tool_name: str
    outcome: Literal["allowed", "blocked"]
    checks: dict[str, str]
    reason: str | None = None
    at: str = datetime.now(UTC).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class WatchdogBlocked(Exception):
    def __init__(self, event: AuditEvent):
        self.event = event
        super().__init__(event.reason or "Watchdog blocked this tool call")

