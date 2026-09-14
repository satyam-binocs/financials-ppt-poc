from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .config import LlmConfig


class StructuredGateway(Protocol):
    def complete(self, *, task: str, instructions: str, payload: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]: ...


class UsageLimitExceeded(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class UsageReservation:
    input_tokens: int
    output_tokens: int


class RunUsageBudget:
    """Conservative per-process ledger for requests, tokens, and estimated spend."""

    def __init__(self, config: LlmConfig) -> None:
        self.config = config
        self.requests = 0
        self.input_tokens = 0
        self.output_tokens = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def estimated_cost_usd(self) -> float:
        return (
            self.input_tokens * self.config.input_cost_per_million_tokens
            + self.output_tokens * self.config.output_cost_per_million_tokens
        ) / 1_000_000

    def reserve(self, estimated_input_tokens: int) -> UsageReservation:
        reservation = UsageReservation(estimated_input_tokens, self.config.max_output_tokens_per_call)
        next_requests = self.requests + 1
        next_input = self.input_tokens + reservation.input_tokens
        next_output = self.output_tokens + reservation.output_tokens
        next_cost = (
            next_input * self.config.input_cost_per_million_tokens
            + next_output * self.config.output_cost_per_million_tokens
        ) / 1_000_000
        if next_requests > self.config.max_requests_per_run:
            raise UsageLimitExceeded(
                f"LLM request limit reached: {self.requests}/{self.config.max_requests_per_run} requests already reserved"
            )
        if next_input + next_output > self.config.max_tokens_per_run:
            raise UsageLimitExceeded(
                f"LLM token limit would be exceeded: {next_input + next_output}/{self.config.max_tokens_per_run} tokens"
            )
        if next_cost > self.config.max_estimated_cost_usd_per_run:
            raise UsageLimitExceeded(
                f"LLM estimated cost limit would be exceeded: ${next_cost:.4f}/${self.config.max_estimated_cost_usd_per_run:.4f}"
            )
        self.requests = next_requests
        self.input_tokens = next_input
        self.output_tokens = next_output
        return reservation

    def reconcile(self, reservation: UsageReservation, actual_input_tokens: int, actual_output_tokens: int) -> None:
        self.input_tokens += actual_input_tokens - reservation.input_tokens
        self.output_tokens += actual_output_tokens - reservation.output_tokens
        if self.total_tokens > self.config.max_tokens_per_run:
            raise UsageLimitExceeded(
                f"LLM token limit exceeded by API-reported usage: {self.total_tokens}/{self.config.max_tokens_per_run} tokens"
            )
        if self.estimated_cost_usd > self.config.max_estimated_cost_usd_per_run:
            raise UsageLimitExceeded(
                f"LLM estimated cost limit exceeded by API-reported usage: "
                f"${self.estimated_cost_usd:.4f}/${self.config.max_estimated_cost_usd_per_run:.4f}"
            )

    def snapshot(self) -> dict[str, Any]:
        return {
            "api_requests": self.requests,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "estimated_cost_usd": round(self.estimated_cost_usd, 6),
            "limits": {
                "requests": self.config.max_requests_per_run,
                "tokens": self.config.max_tokens_per_run,
                "estimated_cost_usd": self.config.max_estimated_cost_usd_per_run,
            },
        }


class BudgetedJsonGateway:
    """Shared cache, retry, and usage-budget boundary for JSON HTTP providers."""

    def __init__(self, config: LlmConfig, cache_dir: Path) -> None:
        self.config = config
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.usage = RunUsageBudget(config)

    def _complete_http(self, *, request_value: dict[str, Any], endpoint: str, headers: dict[str, str], output_parser) -> dict[str, Any]:
        cache_material = {"provider": self.config.provider, "endpoint": endpoint, "request": request_value}
        cache_key = hashlib.sha256(json.dumps(cache_material, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        cache_path = self.cache_dir / f"{cache_key}.json"
        if self.config.cache_enabled and cache_path.exists():
            return json.loads(cache_path.read_text(encoding="utf-8"))

        data = json.dumps(request_value).encode("utf-8")
        request = urllib.request.Request(
            f"{self.config.base_url}/{endpoint}",
            data=data,
            headers={**headers, "Content-Type": "application/json"},
            method="POST",
        )
        last_error: Exception | None = None
        for attempt in range(self.config.max_retries + 1):
            estimated_input_tokens = max(1, (len(data) + 2) // 3)
            reservation = self.usage.reserve(estimated_input_tokens)
            try:
                with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                    raw = json.loads(response.read().decode("utf-8"))
                usage = raw.get("usage") or {}
                actual_input = int(usage.get("input_tokens", reservation.input_tokens))
                actual_input += int(usage.get("cache_creation_input_tokens", 0))
                actual_input += int(usage.get("cache_read_input_tokens", 0))
                self.usage.reconcile(
                    reservation,
                    actual_input,
                    int(usage.get("output_tokens", reservation.output_tokens)),
                )
                result = json.loads(output_parser(raw))
                if self.config.cache_enabled:
                    cache_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                return result
            except urllib.error.HTTPError as exc:
                body = exc.read().decode("utf-8", errors="replace")
                try:
                    error = json.loads(body).get("error", {})
                    detail = f"{error.get('type') or 'api_error'}:{error.get('code') or exc.code}: {error.get('message') or exc.reason}"
                except json.JSONDecodeError:
                    detail = f"HTTP {exc.code}: {exc.reason}"
                last_error = RuntimeError(detail)
                if exc.code == 429 and ("insufficient_quota" in detail or not exc.headers.get("Retry-After")):
                    break
                if attempt < self.config.max_retries:
                    retry_after = exc.headers.get("Retry-After")
                    delay = float(retry_after) if retry_after and retry_after.replace(".", "", 1).isdigit() else min(2 ** attempt, 4)
                    time.sleep(min(delay, 30))
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
                last_error = exc
                if attempt < self.config.max_retries:
                    time.sleep(min(2 ** attempt, 4))
        raise RuntimeError(f"LLM request failed after {self.config.max_retries + 1} attempts: {last_error}")

    def usage_snapshot(self) -> dict[str, Any]:
        return self.usage.snapshot()


class OpenAIResponsesGateway(BudgetedJsonGateway):
    """Structured-output gateway around the OpenAI Responses API."""

    def complete(self, *, task: str, instructions: str, payload: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
        request_value = {
            "model": self.config.planning_model,
            "input": [
                {"role": "system", "content": [{"type": "input_text", "text": instructions}]},
                {"role": "user", "content": [{"type": "input_text", "text": json.dumps(payload, ensure_ascii=False)}]},
            ],
            "text": {"format": {"type": "json_schema", "name": task, "strict": True, "schema": schema}},
            "max_output_tokens": self.config.max_output_tokens_per_call,
        }
        return self._complete_http(
            request_value=request_value, endpoint="responses",
            headers={"Authorization": f"Bearer {self.config.api_key}"},
            output_parser=self._output_text,
        )

    @staticmethod
    def _output_text(response: dict[str, Any]) -> str:
        if isinstance(response.get("output_text"), str):
            return response["output_text"]
        for output in response.get("output", []):
            for content in output.get("content", []):
                if content.get("type") == "output_text" and isinstance(content.get("text"), str):
                    return content["text"]
        raise ValueError("Responses API result did not contain structured output text")


class AnthropicMessagesGateway(BudgetedJsonGateway):
    """Structured-output gateway around the Anthropic Messages API."""

    def complete(self, *, task: str, instructions: str, payload: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
        request_value = {
            "model": self.config.planning_model,
            "max_tokens": self.config.max_output_tokens_per_call,
            "system": instructions,
            "messages": [{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
            "output_config": {"format": {"type": "json_schema", "schema": schema}},
        }
        return self._complete_http(
            request_value=request_value, endpoint="messages",
            headers={"x-api-key": self.config.api_key, "anthropic-version": self.config.anthropic_version},
            output_parser=self._output_text,
        )

    @staticmethod
    def _output_text(response: dict[str, Any]) -> str:
        for content in response.get("content", []):
            if content.get("type") == "text" and isinstance(content.get("text"), str):
                return content["text"]
        raise ValueError("Anthropic Messages API result did not contain structured output text")


def create_gateway(config: LlmConfig, cache_dir: Path) -> StructuredGateway:
    if config.provider == "openai":
        return OpenAIResponsesGateway(config, cache_dir)
    if config.provider == "anthropic":
        return AnthropicMessagesGateway(config, cache_dir)
    raise ValueError(f"Unsupported LLM provider: {config.provider}")
