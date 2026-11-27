"""Zoho ZeptoMail HTTP transport. Retry policy lives outside this module."""
from dataclasses import dataclass

import httpx

from config import settings

_PREFIX = "Zoho-enczapikey "


@dataclass
class TransportResult:
    outcome: str
    provider_reference: str | None = None
    error: str | None = None
    retry_after_seconds: int | None = None


def authorization_header(api_key: str) -> str:
    key = (api_key or "").strip()
    if key.lower().startswith("zoho-enczapikey"):
        return key
    return f"{_PREFIX}{key}"


def send_endpoint(base_url: str) -> str:
    url = (base_url or "").strip().rstrip("/")
    if url.endswith("/email"):
        return url
    return f"{url}/v1.1/email"


class EmailTransport:
    def __init__(self, client: httpx.Client | None = None):
        self._client = client

    def send(
        self,
        *,
        recipient_email: str,
        recipient_name: str | None,
        subject: str,
        html_body: str,
        text_body: str | None = None,
    ) -> TransportResult:
        if not settings.ZEPTO_API_KEY or not settings.ZEPTO_BASE_URL:
            return TransportResult(outcome="permanent", error="Email provider is not configured")
        payload = {
            "from": {
                "address": settings.ZEPTO_SENDER_EMAIL,
                "name": settings.ZEPTO_SENDER_NAME,
            },
            "to": [
                {
                    "email_address": {
                        "address": recipient_email,
                        "name": recipient_name or recipient_email,
                    }
                }
            ],
            "subject": subject,
            "htmlbody": html_body,
            "track_clicks": False,
            "track_opens": False,
        }
        if text_body:
            payload["textbody"] = text_body
        headers = {
            "Authorization": authorization_header(settings.ZEPTO_API_KEY),
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        timeout = settings.EMAIL_REQUEST_TIMEOUT_SECONDS
        try:
            if self._client is not None:
                response = self._client.post(
                    send_endpoint(settings.ZEPTO_BASE_URL),
                    json=payload,
                    headers=headers,
                    timeout=timeout,
                    follow_redirects=False,
                )
            else:
                with httpx.Client(timeout=timeout, follow_redirects=False) as client:
                    response = client.post(
                        send_endpoint(settings.ZEPTO_BASE_URL),
                        json=payload,
                        headers=headers,
                    )
        except httpx.TimeoutException:
            return TransportResult(outcome="ambiguous", error="Provider timeout")
        except httpx.HTTPError:
            return TransportResult(outcome="temporary", error="Provider connection failed")
        return _classify(response)


def _classify(response: httpx.Response) -> TransportResult:
    retry_after = None
    raw = response.headers.get("Retry-After")
    if raw and raw.isdigit():
        retry_after = int(raw)
    reference = None
    accepted = False
    try:
        body = response.json()
    except Exception:
        body = None
    if isinstance(body, dict):
        data = body.get("data") if isinstance(body.get("data"), dict) else body
        if isinstance(data, dict):
            reference = data.get("request_id") or data.get("message_id") or body.get("request_id")
        accepted = str(body.get("message", "")).lower() in {"ok", "success"} or body.get("data") is not None
    if response.status_code in (200, 201) and (accepted or body is None or response.status_code == 201):
        if response.status_code in (200, 201):
            return TransportResult(outcome="accepted", provider_reference=str(reference) if reference else None)
    if response.status_code in (408, 429) or response.status_code >= 500:
        return TransportResult(outcome="temporary", error=f"Provider HTTP {response.status_code}", retry_after_seconds=retry_after)
    if response.status_code in (401, 403, 400, 422):
        return TransportResult(outcome="permanent", error=f"Provider HTTP {response.status_code}")
    return TransportResult(outcome="ambiguous", error=f"Provider HTTP {response.status_code}")
