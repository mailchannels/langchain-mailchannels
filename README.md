# MailChannels for LangChain

A LangChain tool wrapping the official `mailchannels` Python SDK. Supports plain text and optional HTML, sync `invoke` and async `ainvoke`, provider dry-run validation, and actual sending when the application explicitly enables it. This package is prepared locally and is not yet published to PyPI.

Install from this directory with `pip install .`. Python 3.10 or newer is required.

```python
import os
from langchain_mailchannels import MailChannelsSendEmailTool

tool = MailChannelsSendEmailTool(
    api_key=os.environ["MAILCHANNELS_API_KEY"],
    sender="notifications@example.com",
    allowed_recipients=["recipient@example.net"],
    dry_run=True,
)
result = tool.invoke({
    "to": ["recipient@example.net"],
    "subject": "Your requested update",
    "text": "Your report is ready.",
})
# In an async application: result = await tool.ainvoke({...})
```

Use a sender authorized by your MailChannels account and configure Domain Lockdown/DKIM as documented at https://docs.mailchannels.com/email-api/overview. Dry-run still calls MailChannels and transmits the message for validation, but does not send email. No live service calls are required by the test suite.

To send mail, the **application** creates a tool with `dry_run=False`. The model cannot select the API key, sender, endpoint, recipient permissions or mode through tool arguments. Bind the tool to a model with its normal LangChain `bind_tools([tool])` interface, or pass it to a LangChain agent. A model-generated tool call still requires execution by the application's tool runner. Apply your application's approval and tenant authorization policy before executing sending tools.

The tool restricts recipients to the configured exact mailbox allowlist (domain normalization follows Pydantic; local-part case is preserved). Create one tool per tenant and grant only appropriate recipients. Keys are private secret attributes and excluded from tool schemas, repr and model dumps. Do not pickle tool instances or capture process memory as a secret-storage strategy. LangChain callbacks/tracing can include message input: configure trace retention/redaction appropriately. Provider rendered MIME, failure reasons and HTTP headers are not returned to the model.

Results are `validated` (dry-run only), `accepted` (provider handoff, not inbox delivery), `failed` (provider result), or `unknown`. The tool never retries automatically. A timeout or malformed response may follow acceptance. Agent reruns, graph replay, or invoking the same tool twice can send twice; this tool does not claim idempotency. Applications needing durable replay protection must record and reconcile operations outside the model and must not blindly retry unknown outcomes. Async cancellation does not stop an in-flight request in the executor.

This initial tool intentionally exposes a bounded transactional-message interface; it does not expose attachments, Cc/Bcc, custom headers, bulk campaigns or delivery webhooks. Those remain available through the SDK. The package has not been submitted to LangChain's catalog or published.

Run `pip install '.[test]'` then `pytest`. Tests use the released SDK with intercepted HTTP and real LangChain invocation; no credentials or live email required.

For repeatable Linux verification, run from the package directory:

```sh
docker run --rm -v "$PWD:/src:ro" python:3.10-slim sh /src/tests/container-check.sh
docker run --rm -v "$PWD:/src:ro" python:3.13-slim sh /src/tests/container-check.sh
```

The container script tests the released SDK, builds a source distribution and wheel, then verifies import of the installed wheel outside the source tree. CI also checks Python 3.12.

Release operators: see [RELEASING.md](RELEASING.md) for candidate builds, the exact
company PyPI trusted-publisher settings, artifact review and registry verification.
Publishing is disabled until explicitly configured; no release is implied by green CI.
