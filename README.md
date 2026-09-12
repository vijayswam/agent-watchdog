# Agent Watchdog

**Runtime evaluation and guardrails for consequential agent tool calls — demonstrated in Slack.**

An expense file lands in Slack. A Slack event triggers the workflow; the Expense Approval Agent evaluates it, while Watchdog intercepts every consequential tool call. Only a passing call reaches the approval action. Slack receives the final verdict plus a compact audit trail.

## Why this is an agent experience, not a chatbot

Slack is the operational surface: people submit evidence where finance teams already work, see the verdict in the same thread, and can act on a readable audit trail. The Watchdog sits *inside* the tool-call path, so it guards the moment of consequence rather than merely summarizing an agent's self-reported result.

## Demo contract

| Scenario | Watchdog result | Slack result |
| --- | --- | --- |
| Clean expense JSON | Validates data, integrity, and `expenses:approve` scope; allows action | ✅ approved / needs review, audit trail |
| Tampered or malformed upload | Blocks before `approve_expense` runs | 🛡️ blocked, failed checks, no write |
| Injection-shaped input or missing scope | Blocks before action | 🛡️ blocked, reason and audit trail |

## Architecture

```text
Slack file_shared event → verified FastAPI endpoint → queue/worker → Expense Agent
                                                          │
                                                          ▼
          Slack final verdict ← audit sink ← Watchdog decorator → approval tool
                                      (data quality · integrity · scope/injection)
```

## Local run

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
uvicorn watchdog.slack_app:app --reload
pytest
```

For a real Slack demo, create a Slack app with `files:read`, `chat:write`, and `channels:history` bot scopes; subscribe to `file_shared`; point Events Request URL to `/slack/events`; and set the three Slack values in `.env`. Use a public HTTPS tunnel for local development. Do **not** put secrets in the repo.

## Judging-focused build checklist

- **Core functionality:** record a two-minute clean and blocked Slack demo, including proof `approve_expense` was not reached.
- **Innovation:** narrate the new pattern: runtime eval as a visible, native Slack control point—not an offline score or generic bot.
- **Technical execution:** use signed Slack requests, idempotent queued event processing, durable append-only audits, retries/dead-letter handling, and tests for bypass attempts.
- **Usefulness:** make verdicts readable; add a Slack `Approve anyway` human-review action for ambiguous/high-value expenses, never an automatic override.

## Delivery plan

See [PLAN.md](PLAN.md) for owners, order of work, acceptance criteria, and the GitHub/Slack setup sequence.

