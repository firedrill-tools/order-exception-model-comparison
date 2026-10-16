"""Pinned owned native providers and original tool-completion authority."""

import base64
import json
import os
from dataclasses import dataclass, field
from urllib.parse import urlsplit
import httpx
import httpx2
from openai import AsyncOpenAI, omit as openai_omit
from anthropic import AsyncAnthropic, omit
from google import genai
from google.genai import types
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.providers.anthropic import AnthropicProvider
from pydantic_ai.providers.google import GoogleProvider
from .schema import Proposal

DEFAULT_URLS = {
    "openai": "https://api.openai.com/v1",
    "anthropic": "https://api.anthropic.com",
    "google": "https://generativelanguage.googleapis.com",
}
KEYS = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "google": "GOOGLE_API_KEY",
}
READ_TOOLS = {"read_order", "read_request", "read_policy"}
OUTPUT_TOOL = "submit_proposal"
MAX_BODY = 1048576
REQUEST_LIMIT = 6
TOOL_LIMIT = 12


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate original JSON key")
            result[key] = value
        return result

    def invalid(value):
        raise ValueError("nonfinite original JSON")

    return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)


@dataclass(frozen=True)
class ModelConfig:
    identifier: str
    api_key: str = field(repr=False)
    base_url: str

    @property
    def provider(self):
        return self.identifier.split(":", 1)[0]

    @property
    def model(self):
        return self.identifier.split(":", 1)[1]

    def validate(self):
        if (
            not isinstance(self.identifier, str)
            or ":" not in self.identifier
            or self.provider not in DEFAULT_URLS
            or not self.model
            or len(self.identifier) > 250
            or any(c.isspace() for c in self.identifier)
        ):
            raise ValueError(
                "explicit openai:, anthropic: or google: model is required"
            )
        if (
            not isinstance(self.api_key, str)
            or not self.api_key
            or len(self.api_key) > 4096
            or any(not 33 <= ord(c) <= 126 for c in self.api_key)
        ):
            raise ValueError("explicit selected provider API key is required")
        try:
            url = urlsplit(self.base_url)
            url.port
            if (
                not url.hostname
                or url.username
                or url.password
                or url.query
                or url.fragment
                or not (
                    url.scheme == "https"
                    or url.scheme == "http"
                    and url.hostname in {"127.0.0.1", "localhost", "::1"}
                )
            ):
                raise ValueError()
        except (TypeError, ValueError):
            raise ValueError(
                "provider endpoint requires HTTPS or loopback HTTP without credentials/query/fragment"
            ) from None
        if self.provider == "google" and (
            os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "false").lower()
            not in {"false", "0", ""}
            or os.getenv("GOOGLE_GENAI_USE_ENTERPRISE", "").lower() in {"true", "1"}
        ):
            raise ValueError("only explicit Gemini Developer API backend is qualified")
        return self

    def public(self):
        return {
            "identifier": self.identifier,
            "provider": self.provider,
            "requested_model": self.model,
            "base_url": self.base_url,
        }


def configuration(identifier, *, api_key=None, base_url=None):
    if (
        not isinstance(identifier, str)
        or ":" not in identifier
        or identifier.split(":", 1)[0] not in DEFAULT_URLS
    ):
        raise ValueError("explicit provider:model is required")
    provider = identifier.split(":", 1)[0]
    key = (
        api_key
        or os.getenv(KEYS[provider])
        or (os.getenv("GEMINI_API_KEY") if provider == "google" else None)
    )
    return ModelConfig(identifier, key, base_url or DEFAULT_URLS[provider]).validate()


def completion(provider, body):
    if not isinstance(body, dict):
        raise ValueError("original provider response requires a JSON object")
    if provider == "openai":
        choices = body.get("choices")
        if (
            body.get("object") != "chat.completion"
            or not isinstance(body.get("id"), str)
            or not body["id"].strip()
            or not isinstance(choices, list)
            or len(choices) != 1
            or not isinstance(choices[0], dict)
        ):
            raise ValueError("expected one original chat completion")
        choice = choices[0]
        message = choice.get("message")
        if (
            type(choice.get("index")) is not int
            or choice["index"] != 0
            or choice.get("finish_reason") != "tool_calls"
            or not isinstance(message, dict)
            or message.get("role") != "assistant"
            or message.get("refusal")
            or message.get("function_call")
        ):
            raise ValueError(
                "proposal/read turn requires completed tool_calls without refusal/truncation"
            )
        raw_calls = message.get("tool_calls")
        if not isinstance(raw_calls, list):
            raise ValueError("missing original tool calls")
        calls = []
        for call in raw_calls:
            if (
                not isinstance(call, dict)
                or call.get("type") != "function"
                or not isinstance(call.get("function"), dict)
            ):
                raise ValueError("invalid original tool call")
            function = call["function"]
            if not isinstance(function.get("arguments"), str):
                raise ValueError("tool arguments require original JSON text")
            calls.append(
                {
                    "id": call.get("id"),
                    "name": function.get("name"),
                    "args": strict_json(function["arguments"]),
                }
            )
        identity = {
            "response_id": body["id"],
            "response_model": body.get("model"),
            "finish_reason": choice["finish_reason"],
        }
    elif provider == "anthropic":
        content = body.get("content")
        if (
            body.get("type") != "message"
            or body.get("role") != "assistant"
            or not isinstance(body.get("id"), str)
            or not body["id"].strip()
            or body.get("stop_reason") != "tool_use"
            or body.get("stop_sequence") is not None
            or not isinstance(content, list)
            or not content
            or any(
                not isinstance(x, dict)
                or x.get("type")
                not in {"text", "thinking", "redacted_thinking", "tool_use"}
                for x in content
            )
        ):
            raise ValueError("proposal/read turn requires completed tool_use message")
        calls = [
            {"id": part.get("id"), "name": part.get("name"), "args": part.get("input")}
            for part in content
            if part.get("type") == "tool_use"
        ]
        identity = {
            "response_id": body["id"],
            "response_model": body.get("model"),
            "finish_reason": body["stop_reason"],
        }
    else:
        feedback = body.get("promptFeedback")
        candidates = body.get("candidates")
        if isinstance(feedback, dict) and feedback.get("blockReason") not in {
            None,
            "BLOCK_REASON_UNSPECIFIED",
        }:
            raise ValueError("Gemini prompt was blocked")
        if (
            not isinstance(candidates, list)
            or len(candidates) != 1
            or not isinstance(candidates[0], dict)
        ):
            raise ValueError("expected one original Gemini candidate")
        candidate = candidates[0]
        content = candidate.get("content")
        parts = content.get("parts") if isinstance(content, dict) else None
        if (
            candidate.get("finishReason") != "STOP"
            or not isinstance(content, dict)
            or content.get("role") not in {None, "model"}
            or not isinstance(parts, list)
            or not parts
            or any(
                not isinstance(x, dict)
                or any(
                    x.get(key) is not None
                    for key in (
                        "executableCode",
                        "codeExecutionResult",
                        "inlineData",
                        "fileData",
                    )
                )
                for x in parts
            )
            or any(
                isinstance(x, dict) and x.get("blocked") is True
                for x in candidate.get("safetyRatings") or []
            )
        ):
            raise ValueError(
                "proposal/read turn requires completed unblocked STOP tool content"
            )
        calls = []
        for part in parts:
            if part.get("functionCall") is not None:
                call = part["functionCall"]
                if not isinstance(call, dict):
                    raise ValueError("invalid original Gemini function call")
                calls.append(
                    {
                        "id": call.get("id"),
                        "name": call.get("name"),
                        "args": call.get("args"),
                    }
                )
        identity = {
            "response_id": body.get("responseId"),
            "response_model": body.get("modelVersion"),
            "finish_reason": candidate["finishReason"],
        }
    if not 1 <= len(calls) <= 4:
        raise ValueError("expected1–4 original tool calls")
    ids = []
    for call in calls:
        if call["id"] is None and provider == "google":
            pass  # Original ID unavailable; never label an SDK-generated one as observed.
        elif (
            not isinstance(call["id"], str)
            or not call["id"].strip()
            or len(call["id"]) > 256
        ):
            raise ValueError("invalid original tool identity")
        else:
            ids.append(call["id"])
        if call["name"] not in READ_TOOLS | {OUTPUT_TOOL} or not isinstance(
            call["args"], dict
        ):
            raise ValueError("unsupported tool or original arguments")
        if call["name"] == OUTPUT_TOOL:
            Proposal.model_validate(call["args"])
        elif call["name"] == "read_order":
            if (
                set(call["args"]) != {"order_id"}
                or not isinstance(call["args"]["order_id"], str)
                or not call["args"]["order_id"].strip()
                or len(call["args"]["order_id"]) > 128
            ):
                raise ValueError("invalid original order lookup arguments")
        elif call["args"]:
            raise ValueError("request/policy tools take no arguments")
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate original tool identity within a turn")
    if any(call["name"] == OUTPUT_TOOL for call in calls) and len(calls) != 1:
        raise ValueError("proposal cannot be mixed with pending reads")
    return identity, calls


def measurements(provider, body):
    raw = (
        body.get("usageMetadata" if provider == "google" else "usage")
        if isinstance(body, dict)
        else None
    )
    names = {
        "openai": ("prompt_tokens", "completion_tokens", "total_tokens"),
        "anthropic": (
            "input_tokens",
            "output_tokens",
            "cache_creation_input_tokens",
            "cache_read_input_tokens",
            "total_tokens",
        ),
        "google": ("promptTokenCount", "candidatesTokenCount", "totalTokenCount"),
    }
    fields = {}
    for key in names[provider]:
        value = raw.get(key) if isinstance(raw, dict) else None
        valid = type(value) is int and 0 <= value <= 2**53 - 1
        fields[key] = {
            "state": "observed" if valid else "unknown" if value is None else "invalid",
            "value": value if valid else None,
        }
    return {
        "source": "original decoded HTTP JSON before SDK normalization",
        "raw": raw,
        "fields": fields,
        "cost_usd": None,
    }


def aggregate(provider, observations):
    mapping = {
        "openai": ("prompt_tokens", "completion_tokens", "total_tokens"),
        "anthropic": ("input_tokens", "output_tokens", "total_tokens"),
        "google": ("promptTokenCount", "candidatesTokenCount", "totalTokenCount"),
    }[provider]
    result = {
        "requests": len(observations),
        "request_measurement": "prepared native HTTP attempts; upstream receipt/billing is not inferred",
        "usage_semantics": "provider-specific reported counters; cache/reasoning meanings differ",
        "provider": provider,
        "field_mapping": dict(
            zip(("input_tokens", "output_tokens", "total_tokens"), mapping)
        ),
        "cost_usd": None,
    }
    for canonical, original in zip(
        ("input_tokens", "output_tokens", "total_tokens"), mapping
    ):
        rows = [
            (item.get("reported_usage") or {}).get("fields", {}).get(original, {})
            for item in observations
        ]
        total = (
            sum(row["value"] for row in rows)
            if rows and all(row.get("state") == "observed" for row in rows)
            else None
        )
        result[canonical] = total if total is None or total <= 2**53 - 1 else None
    return result


class Boundary:
    def __init__(self, config, receipt):
        self.config = config
        self.receipt = receipt
        self.active = None
        self.read_calls = 0

    async def request(self, request):
        self.receipt.guard()
        path = request.url.path
        allowed = (
            path.endswith("/chat/completions")
            if self.config.provider == "openai"
            else path.endswith("/messages")
            if self.config.provider == "anthropic"
            else path.endswith(":generateContent")
        )
        if request.method != "POST" or not allowed:
            raise ValueError("unsupported provider operation")
        if len(self.receipt.data["native"]) >= REQUEST_LIMIT:
            raise ValueError("native prepared request limit reached")
        raw = await request.aread()
        if len(raw) > MAX_BODY:
            raise ValueError("native request exceeds retained1MiB bound")
        body = strict_json(raw)
        if body.get("stream") is True:
            raise ValueError("only nonstreaming JSON is qualified")
        self.active = {
            "status": "prepared",
            "request_body": body,
            "request_sha256": self.receipt.sha(raw),
            "response": None,
            "reported_usage": None,
            "error": None,
        }
        self.receipt.data["native"].append(self.active)
        self.receipt.save()
        self.receipt.guard()

    async def response(self, response):
        item = self.active
        item.update(
            status="received",
            http_status=response.status_code,
            request_id=response.headers.get("x-request-id")
            or response.headers.get("request-id"),
        )
        try:
            raw = await response.aread()
            item.update(
                decoded_body_base64=base64.b64encode(raw[:MAX_BODY]).decode(),
                body_sha256=self.receipt.sha(raw),
                truncated=len(raw) > MAX_BODY,
            )
            self.receipt.save()
            if len(raw) > MAX_BODY:
                raise ValueError("native response exceeds retained1MiB bound")
            body = strict_json(raw)
            item.update(
                response=body, reported_usage=measurements(self.config.provider, body)
            )
            self.receipt.save()
            self.receipt.guard()
            if 200 <= response.status_code < 300:
                identity, calls = completion(self.config.provider, body)
                reads = sum(call["name"] in READ_TOOLS for call in calls)
                if self.read_calls + reads > TOOL_LIMIT:
                    raise ValueError("native read-tool call limit reached")
                self.read_calls += reads
                item.update(identity, tool_calls=calls, status="accepted")
            else:
                item["status"] = "http_error"
            self.receipt.save()
            self.receipt.guard()
        except BaseException as error:
            self.receipt.native_failure = self.receipt.native_failure or error
            item.update(
                status="rejected",
                error={"name": type(error).__name__, "message": str(error)},
            )
            self.receipt.save()
            raise
        finally:
            await response.aclose()


async def create_model(config, receipt, stack, transport=None):
    config.validate()
    boundary = Boundary(config, receipt)
    hooks = {"request": [boundary.request], "response": [boundary.response]}
    http_type = httpx.AsyncClient if config.provider == "google" else httpx2.AsyncClient
    timeout = (
        httpx.Timeout(30, connect=5)
        if config.provider == "google"
        else httpx2.Timeout(30, connect=5)
    )
    client = await stack.enter_async_context(
        http_type(
            transport=transport,
            timeout=timeout,
            trust_env=False,
            follow_redirects=False,
            event_hooks=hooks,
        )
    )
    if config.provider == "openai":
        sdk = await stack.enter_async_context(
            AsyncOpenAI(
                api_key=config.api_key,
                base_url=config.base_url,
                http_client=client,
                max_retries=0,
                organization=None,
                project=None,
                default_headers={
                    "OpenAI-Organization": openai_omit,
                    "OpenAI-Project": openai_omit,
                },
            )
        )
        model = OpenAIChatModel(
            config.model, provider=OpenAIProvider(openai_client=sdk)
        )
    elif config.provider == "anthropic":
        sdk = await stack.enter_async_context(
            AsyncAnthropic(
                api_key=config.api_key,
                auth_token=None,
                base_url=config.base_url,
                http_client=client,
                max_retries=0,
                default_headers={"Authorization": omit, "X-Api-Key": config.api_key},
            )
        )
        model = AnthropicModel(
            config.model, provider=AnthropicProvider(anthropic_client=sdk)
        )
    else:

        class NoSync(httpx.BaseTransport):
            def handle_request(self, request):
                raise RuntimeError("this comparison owns async generateContent only")

        sync = stack.enter_context(httpx.Client(transport=NoSync(), trust_env=False))
        sdk = genai.Client(
            api_key=config.api_key,
            vertexai=False,
            http_options={
                "base_url": config.base_url,
                "api_version": "v1beta",
                "timeout": 30000,
                "retry_options": types.HttpRetryOptions(attempts=1),
                "httpx_client": sync,
                "httpx_async_client": client,
            },
        )
        stack.callback(sdk.close)
        stack.push_async_callback(sdk.aio.aclose)
        model = GoogleModel(config.model, provider=GoogleProvider(client=sdk))
    return model, boundary
