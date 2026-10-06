"""Application-scoped email tool using the official MailChannels SDK."""

from typing import Any

from langchain_core.tools import BaseTool, ToolException
from mailchannels import Client, MailChannelsError, RequestsClient, SendResponse
from pydantic import BaseModel, ConfigDict, EmailStr, Field, PrivateAttr, SecretStr
from requests import RequestException


class EmailInput(BaseModel):
    """Model-visible message fields; credentials and policy are application-only."""

    model_config = ConfigDict(extra="forbid")
    to: list[EmailStr] = Field(min_length=1, max_length=100)
    subject: str = Field(min_length=1, max_length=998, pattern=r"^[^\r\n]+$")
    text: str = Field(min_length=1, max_length=100_000)
    html: str | None = Field(default=None, max_length=100_000)


class MailChannelsSendEmailTool(BaseTool):
    """Send or validate transactional email within a fixed application policy.

    Async LangChain invocation uses BaseTool's executor implementation. Each
    invocation creates its own SDK transport; there is no shared mutable SDK
    global, automatic retry, or exactly-once delivery guarantee.
    """

    name: str = "mailchannels_validate_email"
    description: str = (
        "Validate a transactional email without sending it. Only configured "
        "recipients are permitted. Validation does not prove inbox delivery."
    )
    args_schema: type[BaseModel] = Field(default=EmailInput, exclude=True)
    _key: SecretStr = PrivateAttr()
    _sender: str = PrivateAttr()
    _allowed: frozenset[str] = PrivateAttr()
    _dry_run: bool = PrivateAttr()

    def __init__(
        self, *, api_key: str | SecretStr, sender: str,
        allowed_recipients: list[str], dry_run: bool = True, **kwargs: Any,
    ) -> None:
        """Configure a key, authorized sender, exact recipient allowlist and mode."""
        from pydantic import TypeAdapter

        key = api_key if isinstance(api_key, SecretStr) else SecretStr(api_key)
        if not key.get_secret_value().strip():
            raise ValueError("api_key must not be empty")
        if type(dry_run) is not bool:
            raise ValueError("dry_run must be a boolean")
        address = TypeAdapter(EmailStr)
        validated_sender = str(address.validate_python(sender))
        allowed = frozenset(str(address.validate_python(a)) for a in allowed_recipients)
        if not allowed:
            raise ValueError("allowed_recipients must not be empty")
        super().__init__(**kwargs)
        self._key = key
        self._sender = validated_sender
        self._allowed = allowed
        self._dry_run = dry_run
        if not dry_run:
            self.name = "mailchannels_send_email"
            self.description = (
                "Send a transactional email to configured recipients. This has "
                "an external side effect. Accepted does not mean delivered. "
                "Never retry an unknown outcome automatically."
            )

    def _run(
        self, to: list[str], subject: str, text: str, html: str | None = None,
    ) -> dict[str, Any]:
        """Invoke the SDK once and return bounded, non-content response metadata."""
        # Revalidate even for direct callers of _run; policy applies in all paths.
        message = EmailInput(to=to, subject=subject, text=text, html=html)
        recipients = list(dict.fromkeys(str(a) for a in message.to))
        if not set(recipients).issubset(self._allowed):
            raise ToolException("Recipient is outside the application's allowlist.")
        content = [{"type": "text/plain", "value": message.text}]
        if message.html:
            content.append({"type": "text/html", "value": message.html})
        payload = {
            "from": {"email": self._sender},
            "personalizations": [{"to": [{"email": a} for a in recipients]}],
            "subject": message.subject, "content": content,
        }
        try:
            with RequestsClient(timeout=30.0) as transport:
                client = Client(
                    api_key=self._key.get_secret_value(),
                    base_url="https://api.mailchannels.net/tx/v1",
                    http_client=transport, strict_responses=True,
                )
                result = client.emails.send(payload, dry_run=self._dry_run)
        except (MailChannelsError, RequestException, ValueError):
            # Provider bodies/exceptions may contain secrets or message content.
            # A failed response can follow acceptance: do not claim non-delivery.
            return {"status": "unknown", "dry_run": self._dry_run,
                    "retry_safe": False,
                    "message": "Request failed or response could not be verified; reconcile before retrying."}
        return self._result(result)

    def _result(self, result: SendResponse) -> dict[str, Any]:
        """Distinguish dry-run, accepted, failed and malformed response variants."""
        if self._dry_run and result.data and not result.results:
            return {"status": "validated", "dry_run": True, "sent": False}
        if not self._dry_run and result.results and not result.data:
            # One personalization was sent. Extra/missing indices are ambiguous.
            if len(result.results) == 1 and result.results[0].index == 0:
                item = result.results[0]
                return {"status": "accepted" if item.status == "sent" else "failed",
                        "dry_run": False, "delivery_confirmed": False,
                        "request_id": result.request_id, "message_id": item.message_id}
        return {"status": "unknown", "dry_run": self._dry_run, "retry_safe": False,
                "message": "Unexpected response variant; reconcile before retrying."}
