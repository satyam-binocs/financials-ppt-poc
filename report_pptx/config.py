from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def load_env(path: Path) -> None:
    """Load a small .env file without adding a runtime dependency."""
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip().strip("\"").strip("'")
        if key:
            os.environ.setdefault(key, value)


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class LlmConfig:
    provider: str = "openai"
    api_key: str = ""
    planning_model: str = ""
    base_url: str = "https://api.openai.com/v1"
    timeout_seconds: int = 90
    max_retries: int = 2
    enable_planning: bool = True
    enable_deterministic_fallback: bool = False
    cache_enabled: bool = True
    max_requests_per_run: int = 32
    max_tokens_per_run: int = 200_000
    max_output_tokens_per_call: int = 2_000
    max_estimated_cost_usd_per_run: float = 5.0
    input_cost_per_million_tokens: float = 2.0
    output_cost_per_million_tokens: float = 12.0
    anthropic_version: str = "2023-06-01"
    visual_review_model: str = ""
    enable_visual_review: bool = True
    max_slide_repair_attempts: int = 3
    visual_review_batch_size: int = 4
    min_visual_aesthetic_score: int = 7
    min_visual_readability_score: int = 8
    min_visual_balance_score: int = 7

    @classmethod
    def from_env(cls) -> "LlmConfig":
        provider = os.getenv("LLM_PROVIDER", "openai").strip().lower()
        if provider == "anthropic":
            api_key = os.getenv("ANTHROPIC_API_KEY", "")
            base_url = os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com/v1")
        else:
            api_key = os.getenv("OPENAI_API_KEY", "")
            base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        return cls(
            provider=provider,
            api_key=api_key,
            planning_model=os.getenv("PLANNING_MODEL", ""),
            base_url=base_url.rstrip("/"),
            timeout_seconds=int(os.getenv("LLM_TIMEOUT_SECONDS", "90")),
            max_retries=int(os.getenv("MAX_LLM_RETRIES", "2")),
            enable_planning=_bool("ENABLE_LLM_PLANNING", True),
            enable_deterministic_fallback=_bool("ENABLE_DETERMINISTIC_FALLBACK", False),
            cache_enabled=_bool("ENABLE_LLM_CACHE", True),
            max_requests_per_run=int(os.getenv("MAX_LLM_REQUESTS_PER_RUN", "32")),
            max_tokens_per_run=int(os.getenv("MAX_LLM_TOKENS_PER_RUN", "200000")),
            max_output_tokens_per_call=int(os.getenv("MAX_LLM_OUTPUT_TOKENS_PER_CALL", "2000")),
            max_estimated_cost_usd_per_run=float(os.getenv("MAX_LLM_ESTIMATED_COST_USD_PER_RUN", "5.00")),
            input_cost_per_million_tokens=float(os.getenv("PLANNING_INPUT_COST_PER_1M_TOKENS", "2.00")),
            output_cost_per_million_tokens=float(os.getenv("PLANNING_OUTPUT_COST_PER_1M_TOKENS", "12.00")),
            anthropic_version=os.getenv("ANTHROPIC_VERSION", "2023-06-01"),
            visual_review_model=os.getenv("VISUAL_REVIEW_MODEL", ""),
            enable_visual_review=_bool("ENABLE_LLM_VISUAL_REVIEW", True),
            max_slide_repair_attempts=int(os.getenv("MAX_SLIDE_REPAIR_ATTEMPTS", "3")),
            visual_review_batch_size=int(os.getenv("VISUAL_REVIEW_BATCH_SIZE", "4")),
            min_visual_aesthetic_score=int(os.getenv("MIN_VISUAL_AESTHETIC_SCORE", "7")),
            min_visual_readability_score=int(os.getenv("MIN_VISUAL_READABILITY_SCORE", "8")),
            min_visual_balance_score=int(os.getenv("MIN_VISUAL_BALANCE_SCORE", "7")),
        )

    def validate(self) -> None:
        if not self.enable_planning:
            return
        if self.provider not in {"openai", "anthropic"}:
            raise ValueError(f"Unsupported LLM_PROVIDER={self.provider!r}; supported: 'openai', 'anthropic'")
        key_name = "ANTHROPIC_API_KEY" if self.provider == "anthropic" else "OPENAI_API_KEY"
        missing = [name for name, value in ((key_name, self.api_key), ("PLANNING_MODEL", self.planning_model)) if not value]
        if missing:
            raise ValueError(f"LLM planning is enabled but {', '.join(missing)} is not configured")
        positive = {
            "MAX_LLM_REQUESTS_PER_RUN": self.max_requests_per_run,
            "MAX_LLM_TOKENS_PER_RUN": self.max_tokens_per_run,
            "MAX_LLM_OUTPUT_TOKENS_PER_CALL": self.max_output_tokens_per_call,
            "MAX_LLM_ESTIMATED_COST_USD_PER_RUN": self.max_estimated_cost_usd_per_run,
            "PLANNING_INPUT_COST_PER_1M_TOKENS": self.input_cost_per_million_tokens,
            "PLANNING_OUTPUT_COST_PER_1M_TOKENS": self.output_cost_per_million_tokens,
        }
        invalid = [name for name, value in positive.items() if value <= 0]
        if invalid:
            raise ValueError(f"LLM usage limits and pricing must be positive: {', '.join(invalid)}")

    def validate_visual_review(self) -> None:
        self.validate()
        if self.enable_visual_review and not self.visual_review_model:
            raise ValueError("LLM visual review is enabled but VISUAL_REVIEW_MODEL is not configured")
