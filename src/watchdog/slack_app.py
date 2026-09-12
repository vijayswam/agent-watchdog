"""Slack Events API entry point: detects files, validates them, posts an audit verdict."""
import hashlib
import hmac
import json
import os
import time
from typing import Any

import httpx
from fastapi import FastAPI, Header, HTTPException, Request

from .service import _active_service

app = FastAPI(title="Agent Watchdog")


def verify_slack(signature: str | None, timestamp: str | None, body: bytes) -> None:
    if not signature or not timestamp or abs(time.time() - int(timestamp)) > 300:
        raise HTTPException(401, "Invalid Slack request")
    basestring = f"v0:{timestamp}:".encode() + body
    secret = os.environ["SLACK_SIGNING_SECRET"].encode()
    expected = "v0=" + hmac.new(secret, basestring, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(401, "Invalid Slack signature")


@app.post("/slack/events")
async def slack_events(request: Request, x_slack_signature: str | None = Header(None),
                       x_slack_request_timestamp: str | None = Header(None)) -> dict[str, Any]:
    body = await request.body()
    verify_slack(x_slack_signature, x_slack_request_timestamp, body)
    payload = json.loads(body)
    if payload.get("type") == "url_verification":
        return {"challenge": payload["challenge"]}
    event = payload.get("event", {})
    if event.get("type") != "file_shared":
        return {"ok": True}
    # Acknowledging quickly is essential; production should enqueue this job.
    # The worker retrieves file metadata/content using SLACK_BOT_TOKEN, then calls evaluate.
    return {"ok": True, "queued": True, "file_id": event.get("file_id")}


async def post_verdict(channel: str, verdict: dict[str, Any]) -> None:
    token = os.environ["SLACK_BOT_TOKEN"]
    text = "🛡️ *WATCHDOG BLOCKED*" if verdict["status"] == "blocked" else "✅ *WATCHDOG ALLOWED*"
    text += "\n```" + json.dumps(verdict, indent=2) + "```"
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post("https://slack.com/api/chat.postMessage",
                                     headers={"Authorization": f"Bearer {token}"},
                                     json={"channel": channel, "text": text})
        response.raise_for_status()

