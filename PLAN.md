# Delivery Plan — Agent Watchdog

## Target experience

**User action:** Upload an expense JSON/PDF to `#expense-approvals`.

**Agent action:** The Slack listener verifies the event, queues the file, extracts structured fields, then asks the Expense Approval Agent to evaluate it. Every read/policy/write tool call is wrapped by Watchdog. The final message says exactly what passed or was blocked and links/expands the audit trail.

**Safety invariant:** No consequential write executes unless the watchdog has emitted an `allowed` audit event for that exact call and correlation ID.

## Workstreams and sequence

1. **Repository and delivery baseline — Day 1**
   - Create public GitHub repository `agent-watchdog`; protect `main`; add issue templates, CI, `.env.example`, and a permissive license.
   - Acceptance: a fresh clone runs unit tests without secrets.

2. **Slack ingress agent — Day 1**
   - Create Slack app, subscribe to `file_shared`, verify Slack signatures, filter permitted channel(s), acknowledge in under 3 seconds, and enqueue idempotently by `event_id`.
   - Acceptance: an upload produces one queued job; re-delivery produces no duplicate processing.

3. **File intake / evidence agent — Day 2**
   - Retrieve file metadata and content with a least-privilege bot token; validate MIME/size/schema; hash the original; store encrypted object metadata and correlation ID.
   - Acceptance: malformed, stale, and altered files fail closed with a user-readable Slack verdict.

4. **Expense decision agent + hooked tools — Day 2**
   - Implement `get_expense_data`, `check_policy_limit`, and `approve_expense` as individually hooked tools; use the OpenAI Agents SDK only for bounded interpretation/routing, with deterministic policy and writes outside model discretion.
   - Acceptance: clean case succeeds; each failed check prevents the write.

5. **Watchdog and audit agent — Day 3**
   - Add pre-call data-quality, integrity/tamper, authorization scope, injection, allowlist, timeout, and rate-limit gates. Persist immutable audit events before allowing calls.
   - Acceptance: tests prove direct wrapper bypasses are blocked at the service boundary; audit records carry correlation IDs and redacted arguments.

6. **Slack verdict / human-control agent — Day 3**
   - Post compact block/allow message plus expandable audit fields. Add `Request human review` for threshold cases; a human may approve a business outcome but cannot erase a failed audit record.
   - Acceptance: every demo case reaches a clear Slack conclusion and review routing is logged.

7. **Reliability and submission — Day 4**
   - Add worker retries, dead-letter queue, idempotency, observability, test fixtures, threat-model doc, architecture diagram, 2-minute demo video, and seeded clean/rigged scripts.
   - Acceptance: repeatable end-to-end demo and a reviewer can find setup, design, tests, and limitations in under five minutes.

## Explicit scope decisions

- Slack Incoming Webhooks alone cannot detect uploaded files. The implementation needs a Slack app using the Events API plus a bot token; incoming webhooks can remain an optional notification fallback.
- Auth0 is a demo seam. For the hackathon, model scopes as signed claims/test fixtures; production should validate a JWT and its issuer/audience rather than trusting a hardcoded scope list.
- Keep the approval write deterministic and guarded. The LLM should not be the policy engine or authorization boundary.

## GitHub issue backlog

| Priority | Issue | Definition of done |
| --- | --- | --- |
| P0 | Signed Slack `file_shared` ingress | Signature, timestamp, channel allowlist, idempotency tests |
| P0 | Fail-closed watchdog wrapper | All gates run pre-call; no write on block |
| P0 | Slack audit verdict | One readable message per correlation ID |
| P1 | Async job worker + durable audit store | Retry and dead-letter behavior demonstrated |
| P1 | Human-review action | Permissioned Slack interaction and immutable audit event |
| P1 | Threat model and demo fixtures | Clean, tampered, scope, injection scenarios |
| P2 | Auth0 JWT verifier | Issuer/audience/JWKS verification |

