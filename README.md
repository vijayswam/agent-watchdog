# Agent Watchdog

**A Slack-native runtime safety gate for consequential AI agent actions.**

Agent Watchdog turns a Slack file upload into a controlled agent workflow. When an expense JSON file is shared in Slack, the app verifies the signed Slack event, retrieves the file, runs runtime checks *before* the approval tool can act, and posts a clear allow/block verdict with audit evidence back to the same channel.

This is not a chatbot bolted onto Slack: Slack is the operational surface where a team submits evidence, sees the safety decision, and retains an audit trail alongside the original work item.

## What it demonstrates

| Scenario | Runtime checks | Result in Slack |
| --- | --- | --- |
| Clean expense upload | Data quality, tamper signal, required `expenses:approve` scope, injection-shaped input | `✅ WATCHDOG ALLOWED` and the approval decision |
| Tampered expense upload | The fixture’s tamper signal is detected before the tool executes | `🛡️ WATCHDOG BLOCKED` with the failed check |
| Malformed/non-JSON upload | File type and JSON parsing validation | A blocked verdict with a readable reason |

The approval tool is wrapped by the reusable `@watchdog_hook` decorator. Its checks happen before the side effect, so a failed validation is fail-closed: the approval action does not run.

## Architecture

```text
Slack file_shared event
        │ signed request verification
        ▼
FastAPI /slack/events → background file processor → Slack files.info/download
                                                        │
                                                        ▼
                                           ExpenseService.approve_expense
                                                        │
                                          @watchdog_hook checks:
                                  data quality · tamper · scope · injection
                                                        │
                                                        ▼
                                  Slack verdict + per-upload audit evidence
```

## Repository layout

```text
src/watchdog/hook.py       # framework-agnostic, fail-closed decorator
src/watchdog/service.py    # gated expense-approval tool and audit model
src/watchdog/slack_app.py  # Slack Events API, file processor, and verdicts
demo/                      # clean and tampered files for the live demo
tests/                     # runtime guardrail tests
```

## Run locally

Requires Python 3.11+.

```bash
cd /Users/vijayswaminathan/VScodeRepos/Watchdog-agent/agent-watchdog
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
```

Set these values in `.env` (never commit this file):

```dotenv
SLACK_BOT_TOKEN=xoxb-...
SLACK_SIGNING_SECRET=...
ALLOWED_SLACK_CHANNEL_ID=your_demo_channel_id
WATCHDOG_DEMO_SCOPES=expenses:approve
```

Start the server:

```bash
uvicorn watchdog.slack_app:app --host 0.0.0.0 --port 8000
```

For Slack to reach your laptop, start an HTTPS tunnel in a second terminal:

```bash
cloudflared tunnel --url http://127.0.0.1:8000
```

Use the resulting public URL plus `/slack/events` as the Slack Event Subscriptions Request URL. Cloudflare quick-tunnel URLs change when restarted, so update and re-verify Slack’s Request URL when that happens.

## Slack configuration

1. Create a Slack app from scratch.
2. Add bot token scopes: `files:read` and `chat:write`.
3. Install/reinstall the app to the workspace after changing scopes.
4. Invite the bot to the demo channel.
5. Under **Event Subscriptions**, enable events and configure the verified `https://.../slack/events` Request URL.
6. Subscribe to the bot event `file_shared`.
7. Copy the Bot User OAuth Token and Signing Secret into `.env`, then restart Uvicorn.

## Demo

With the server and tunnel running, upload these files to the configured Slack channel:

```text
demo/expense-clean.json     → allowed approval verdict
demo/expense-tampered.json  → blocked tamper verdict
```

The Slack message is the human-visible control point: it states whether action was permitted and includes the audit checks that led to that result.

## Verify

```bash
pytest -q
```

## Hackathon fit

- **Core functionality:** working end-to-end agent workflow in Slack.
- **Innovation:** a runtime safety gate is native to the work conversation, rather than an after-the-fact evaluator or standalone chatbot.
- **Technical execution:** signed Slack events, private-file retrieval, scoped runtime interception, fail-closed gating, and audit evidence.
- **Usefulness:** a team sees an understandable decision and reason in the channel where the request originated.

## Current demo boundaries

This is intentionally a hackathon prototype. It uses FastAPI background tasks and in-memory audit data; a production deployment should add a durable job queue, persistent audit sink, idempotency storage, retry/dead-letter handling, and a human-review interaction for ambiguous cases.
