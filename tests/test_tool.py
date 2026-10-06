"""Real LangChain + published SDK contract tests, with HTTP intercepted."""

import asyncio
import json

import pytest
import requests
import responses
from langchain_core.tools import ToolException
from langchain_core.utils.function_calling import convert_to_openai_tool
from pydantic import ValidationError

from langchain_mailchannels import MailChannelsSendEmailTool

URL = "https://api.mailchannels.net/tx/v1/send"
MESSAGE = {"to": ["recipient@example.net"], "subject": "Update", "text": "Private body"}
KEY = "test-secret-not-a-real-key"


def tool(**kwargs):
    return MailChannelsSendEmailTool(
        api_key=KEY, sender="sender@example.com",
        allowed_recipients=["recipient@example.net"], **kwargs,
    )


def accepted(status="sent", **kwargs):
    return {"request_id": "req1", "results": [
        {"index": 0, "message_id": "msg1", "status": status, **kwargs}
    ]}


@responses.activate
def test_dry_run_payload_and_schema(monkeypatch):
    monkeypatch.setenv("MAILCHANNELS_API_URL", "https://attacker.invalid")
    responses.post(URL, json={"data": ["private rendered MIME"]}, status=200)
    t = tool()
    assert t.invoke({**MESSAGE, "html": "<p>Private body</p>"}) == {
        "status": "validated", "dry_run": True, "sent": False,
    }
    req = responses.calls[0].request
    assert req.url == URL + "?dry-run=true"
    assert req.headers["X-Api-Key"] == KEY
    payload = json.loads(req.body)
    assert payload["from"] == {"email": "sender@example.com"}
    assert payload["personalizations"] == [{"to": [{"email": "recipient@example.net"}]}]
    assert payload["content"] == [
        {"type": "text/plain", "value": "Private body"},
        {"type": "text/html", "value": "<p>Private body</p>"},
    ]
    schema = convert_to_openai_tool(t)["function"]["parameters"]
    assert set(schema["properties"]) == {"to", "subject", "text", "html"}
    assert t.get_input_schema().model_json_schema()["additionalProperties"] is False
    for value in [repr(t), t.model_dump_json(), json.dumps(t.to_json()), json.dumps(schema)]:
        assert KEY not in value


@pytest.mark.parametrize("bad", [
    {"api_key": "injected"}, {"sender": "attacker@example.net"},
    {"dry_run": False}, {"subject": "injected\r\nBcc: x@y.com"},
    {"to": []}, {"to": ["not an address"]}, {"text": ""},
])
@responses.activate
def test_invalid_input_never_calls_network(bad):
    with pytest.raises(ValidationError):
        tool().invoke({**MESSAGE, **bad})
    assert len(responses.calls) == 0


@responses.activate
def test_allowlist_checked_before_network():
    with pytest.raises(ToolException, match="allowlist"):
        tool().invoke({**MESSAGE, "to": ["someone@example.net"]})
    assert len(responses.calls) == 0


@responses.activate
def test_send_and_tool_call_envelope():
    responses.post(URL, json=accepted(), status=202)
    result = tool(dry_run=False).invoke({"type": "tool_call", "id": "call1",
                                       "name": "mailchannels_send_email", "args": MESSAGE})
    assert result.tool_call_id == "call1"
    assert json.loads(result.content) == {
        "status": "accepted", "dry_run": False, "delivery_confirmed": False,
        "request_id": "req1", "message_id": "msg1",
    }
    assert responses.calls[0].request.url == URL


@responses.activate
def test_failed_result_does_not_leak_provider_reason():
    responses.post(URL, json=accepted("failed", reason=KEY + " Private body"), status=202)
    result = tool(dry_run=False).invoke(MESSAGE)
    assert result["status"] == "failed"
    assert KEY not in json.dumps(result)
    assert "Private body" not in json.dumps(result)


@pytest.mark.parametrize("status", [400, 401, 403, 429, 500, 503])
@responses.activate
def test_api_errors_are_sanitized_and_not_retried(status):
    responses.post(URL, json={"message": KEY + " Private body"}, status=status)
    result = tool(dry_run=False).invoke(MESSAGE)
    assert result["status"] == "unknown"
    assert result["retry_safe"] is False
    assert KEY not in json.dumps(result)
    assert len(responses.calls) == 1


@responses.activate
def test_timeout_unknown_no_retry():
    responses.post(URL, body=requests.Timeout(KEY))
    result = tool(dry_run=False).invoke(MESSAGE)
    assert result["status"] == "unknown"
    assert len(responses.calls) == 1
    assert KEY not in json.dumps(result)


@pytest.mark.parametrize("dry_run,data", [
    (True, accepted()), (False, {"data": ["mime"]}),
    (False, {}), (False, {"request_id": "r", "results": []}),
    (False, {"request_id": "r", "results": [{"index": 1, "message_id": "m", "status": "sent"}]}),
])
@responses.activate
def test_unexpected_response_is_never_success(dry_run, data):
    responses.post(URL, json=data, status=200)
    assert tool(dry_run=dry_run).invoke(MESSAGE)["status"] == "unknown"


@pytest.mark.asyncio
async def test_async_concurrent_isolated_keys():
    with responses.RequestsMock() as mock:
        mock.post(URL, json={"data": ["mime"]}, status=200)
        a = tool()
        b = MailChannelsSendEmailTool(api_key="second-key", sender="other@example.com",
                                     allowed_recipients=["recipient@example.net"])
        results = await asyncio.gather(a.ainvoke(MESSAGE), b.ainvoke(MESSAGE))
        assert all(r["status"] == "validated" for r in results)
        assert {c.request.headers["X-Api-Key"] for c in mock.calls} == {KEY, "second-key"}
        assert {json.loads(c.request.body)["from"]["email"] for c in mock.calls} == {
            "sender@example.com", "other@example.com"}


@pytest.mark.parametrize("kwargs", [{"api_key": ""}, {"allowed_recipients": []}, {"dry_run": "false"}])
def test_invalid_configuration(kwargs):
    config = {"api_key": KEY, "sender": "sender@example.com",
              "allowed_recipients": ["recipient@example.net"], **kwargs}
    with pytest.raises(ValueError):
        MailChannelsSendEmailTool(**config)
