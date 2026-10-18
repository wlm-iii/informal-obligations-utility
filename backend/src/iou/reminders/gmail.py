"""Send-only Gmail REST adapter. No inbox scope, redirects, or automatic send retries."""

import base64
import json
from email.message import EmailMessage
from http.client import HTTPException as ProtocolError
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, build_opener

from fastapi import HTTPException

from iou.config import get_settings
from iou.evidence.storage import NoRedirects


class PreparationFailed(Exception):
    """No message submission occurred."""


class Rejected(Exception):
    """Gmail explicitly rejected submission with a 4xx response."""


class Uncertain(Exception):
    """Gmail may have accepted the message. Never automatically resend."""


def request(url, data, headers):
    req = Request(url, data=data, headers=headers, method="POST")
    with build_opener(NoRedirects()).open(req, timeout=10) as response:
        body = response.read(65537)
        if len(body) > 65536:
            raise ValueError("Oversized provider response")
        result = json.loads(body)
        if not isinstance(result, dict):
            raise ValueError("Invalid provider response")
        return result


class Gmail:
    def __init__(self, settings):
        self.settings = settings

    def prepare(self):
        try:
            settings = self.settings
            result = request(
                "https://oauth2.googleapis.com/token",
                urlencode(
                    {
                        "client_id": settings.gmail_client_id.get_secret_value(),
                        "client_secret": settings.gmail_client_secret.get_secret_value(),
                        "refresh_token": settings.gmail_refresh_token.get_secret_value(),
                        "grant_type": "refresh_token",
                    }
                ).encode(),
                {"Content-Type": "application/x-www-form-urlencoded"},
            )
            token = result["access_token"]
            if (
                not isinstance(token, str)
                or not token
                or len(token) > 8192
                or "\r" in token
                or "\n" in token
            ):
                raise ValueError("Invalid token")
            return token
        except (HTTPError, URLError, OSError, ProtocolError, ValueError, KeyError, TypeError):
            raise PreparationFailed from None

    def send(self, token, delivery):
        message = EmailMessage()
        message["From"] = f"IOU <{self.settings.gmail_sender_email}>"
        message["To"] = delivery.recipient_email
        message["Subject"] = delivery.subject
        # Correlation only: Message-ID is not a Gmail idempotency guarantee.
        message["Message-ID"] = (
            f"<iou-{delivery.id}@{str(self.settings.gmail_sender_email).split('@')[1]}>"
        )
        message.set_content(delivery.body)
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        try:
            result = request(
                "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
                json.dumps({"raw": raw}).encode(),
                {"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            )
            identity = result["id"]
            if not isinstance(identity, str) or not identity or len(identity) > 200:
                raise ValueError("Invalid message identity")
            return identity
        except HTTPError as error:
            if 400 <= error.code < 500 and error.code != 408:
                raise Rejected from None
            raise Uncertain from None
        except (URLError, OSError, ProtocolError, ValueError, KeyError, TypeError):
            raise Uncertain from None


def get_mailer():
    settings = get_settings()
    if settings.email_mode != "gmail":
        raise HTTPException(503, "Email sending is disabled.")
    return Gmail(settings)
