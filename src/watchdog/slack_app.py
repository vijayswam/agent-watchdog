"""Slack Events API entry point: detects files, validates them, posts an audit verdict."""
import hashlib
import hmac
import json
import logging
import os
import time
from typing import Any

import httpx
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request, Response

from .service import ExpenseService

load_dotenv()
app = FastAPI(title="Agent Watchdog")
logger = logging.getLogger(__name__)


def verify_slack(signature: str | None, timestamp: str | None, body: bytes) -> None:
    if not signature or not timestamp or abs(time.time() - int(timestamp)) > 300:
        raise HTTPException(401, "Invalid Slack request")
    basestring = f"v0:{timestamp}:".encode() + body
    secret = os.environ["SLACK_SIGNING_SECRET"].encode()
    expected = "v0=" + hmac.new(secret, basestring, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(401, "Invalid Slack signature")


@app.post("/slack/events", response_model=None)
async def slack_events(request: Request, background_tasks: BackgroundTasks,
                       x_slack_signature: str | None = Header(None),
                       x_slack_request_timestamp: str | None = Header(None)) -> dict[str, Any] | Response:
    body = await request.body()
    verify_slack(x_slack_signature, x_slack_request_timestamp, body)
    payload = json.loads(body)
    if payload.get("type") == "url_verification":
        return Response(content=payload["challenge"], media_type="text/plain")
    event = payload.get("event", {})
    if event.get("type") != "file_shared":
        return {"ok": True}
    # Slack retries if this is not acknowledged quickly. Production should enqueue
    # the job durably before returning; BackgroundTasks keeps the demo self-contained.
    background_tasks.add_task(process_file_safely, event["file_id"])
    return {"ok": True, "queued": True, "file_id": event.get("file_id")}


async def process_file(file_id: str) -> None:
    """Fetch one Slack JSON upload, run Watchdog, and post its verdict."""
    token = os.environ["SLACK_BOT_TOKEN"]
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(timeout=20) as client:
        metadata_response = await client.get(
            "https://slack.com/api/files.info", headers=headers, params={"file": file_id}
        )
        metadata = metadata_response.json()
        if not metadata.get("ok"):
            raise RuntimeError(f"Slack files.info failed: {metadata.get('error')}")
        file = metadata["file"]
        channel = _channel_for(file)
        allowed_channel = os.getenv("ALLOWED_SLACK_CHANNEL_ID")
        if allowed_channel and channel != allowed_channel:
            return
        is_json_upload = file.get("name", "").lower().endswith(".json") and file.get("mimetype") in {
            "application/json", "text/plain"
        }
        if not is_json_upload:
            await post_verdict(channel, {"status": "blocked", "reason": "Only JSON expense uploads are accepted."})
            return
        download_response = await client.get(file["url_private_download"], headers=headers)
        download_response.raise_for_status()
    try:
        expense = download_response.json()
    except json.JSONDecodeError:
        await post_verdict(channel, {"status": "blocked", "reason": "Upload is not valid JSON."})
        return
    scopes = os.getenv("WATCHDOG_DEMO_SCOPES", "expenses:approve").split(",")
    # A Slack upload is an independent validation run.  A fresh service keeps the
    # Slack audit compact and prevents one upload's evidence appearing in another.
    verdict = ExpenseService().evaluate(expense, [scope.strip() for scope in scopes])
    await post_verdict(channel, verdict)


async def process_file_safely(file_id: str) -> None:
    """Keep webhook acknowledgements fast while surfacing async failures in logs."""
    try:
        await process_file(file_id)
    except Exception:
        logger.exception("Watchdog could not process Slack file %s", file_id)


def _channel_for(file: dict[str, Any]) -> str:
    shares = file.get("shares", {})
    for visibility in ("public", "private"):
        for channel, entries in shares.get(visibility, {}).items():
            if entries:
                return channel
    raise RuntimeError("The uploaded file is not shared in a channel")


async def post_verdict(channel: str, verdict: dict[str, Any]) -> None:
    token = os.environ["SLACK_BOT_TOKEN"]
    text = "🛡️ *WATCHDOG BLOCKED*" if verdict["status"] == "blocked" else "✅ *WATCHDOG ALLOWED*"
    text += "\n```" + json.dumps(verdict, indent=2) + "```"
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post("https://slack.com/api/chat.postMessage",
                                     headers={"Authorization": f"Bearer {token}"},
                                     json={"channel": channel, "text": text})
        response.raise_for_status()
