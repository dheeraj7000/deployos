"""Live Provider Adapters for OpenAI, Anthropic, Gemini, and Local Models."""

import json
import os
import time
from typing import Any, Optional, Type, TypeVar
import httpx
from pydantic import BaseModel
from packages.models.base import ModelProvider, ModelResponse

T = TypeVar("T", bound=BaseModel)


class OpenAIProvider(ModelProvider):
    """OpenAI API Adapter (GPT-4o, o1, etc.)."""

    def __init__(self, model_name: str = "gpt-4o", api_key: Optional[str] = None):
        self.model_name = model_name
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self.base_url = "https://api.openai.com/v1"

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> ModelResponse:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        start = time.perf_counter()
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"model": self.model_name, "messages": messages, "temperature": temperature, "max_tokens": max_tokens},
            )
            resp.raise_for_status()
            data = resp.json()

        latency_ms = (time.perf_counter() - start) * 1000.0
        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        total_tokens = usage.get("total_tokens", prompt_tokens + completion_tokens)
        cost_usd = (prompt_tokens * 0.005 + completion_tokens * 0.015) / 1000.0

        return ModelResponse(
            content=content,
            model_name=self.model_name,
            tokens_input=prompt_tokens,
            tokens_output=completion_tokens,
            total_tokens=total_tokens,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
        )

    async def structured_generate(
        self,
        schema: Type[T],
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.0,
    ) -> tuple[T, ModelResponse]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        start = time.perf_counter()
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model_name,
                    "messages": messages,
                    "temperature": temperature,
                    "response_format": {
                        "type": "json_schema",
                        "json_schema": {
                            "name": schema.__name__,
                            "schema": schema.model_json_schema(),
                            "strict": True,
                        },
                    },
                },
            )
            resp.raise_for_status()
            data = resp.json()

        latency_ms = (time.perf_counter() - start) * 1000.0
        raw_json = data["choices"][0]["message"]["content"]
        parsed = schema.model_validate_json(raw_json)
        usage = data.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        total_tokens = usage.get("total_tokens", prompt_tokens + completion_tokens)
        cost_usd = (prompt_tokens * 0.005 + completion_tokens * 0.015) / 1000.0

        response = ModelResponse(
            content=raw_json,
            parsed=parsed,
            model_name=self.model_name,
            tokens_input=prompt_tokens,
            tokens_output=completion_tokens,
            total_tokens=total_tokens,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
        )
        return parsed, response


class AnthropicProvider(ModelProvider):
    """Anthropic Claude API Adapter (Claude 3.5 Sonnet, etc.)."""

    def __init__(self, model_name: str = "claude-3-5-sonnet-20241022", api_key: Optional[str] = None):
        self.model_name = model_name
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
        self.base_url = "https://api.anthropic.com/v1"

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> ModelResponse:
        start = time.perf_counter()
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        body: dict[str, Any] = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system_prompt:
            body["system"] = system_prompt

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(f"{self.base_url}/messages", headers=headers, json=body)
            resp.raise_for_status()
            data = resp.json()

        latency_ms = (time.perf_counter() - start) * 1000.0
        content = data["content"][0]["text"]
        usage = data.get("usage", {})
        prompt_tokens = usage.get("input_tokens", 0)
        completion_tokens = usage.get("output_tokens", 0)
        total_tokens = prompt_tokens + completion_tokens
        cost_usd = (prompt_tokens * 0.003 + completion_tokens * 0.015) / 1000.0

        return ModelResponse(
            content=content,
            model_name=self.model_name,
            tokens_input=prompt_tokens,
            tokens_output=completion_tokens,
            total_tokens=total_tokens,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
        )

    async def structured_generate(
        self,
        schema: Type[T],
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.0,
    ) -> tuple[T, ModelResponse]:
        # Claude tool use / JSON schema enforcement
        schema_json = json.dumps(schema.model_json_schema())
        augmented_system = (
            f"{system_prompt or ''}\n\n"
            f"You MUST return ONLY valid JSON matching this schema:\n{schema_json}\n"
            f"Do not include any explanation or markdown formatting."
        )
        resp = await self.generate(prompt, system_prompt=augmented_system, temperature=temperature)
        cleaned = resp.content.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned.split("```json")[1].split("```")[0].strip()
        elif cleaned.startswith("```"):
            cleaned = cleaned.split("```")[1].split("```")[0].strip()

        parsed = schema.model_validate_json(cleaned)
        resp.parsed = parsed
        return parsed, resp


def get_model_provider(model_name: str = "mock-reliable-v1") -> ModelProvider:
    """Factory helper to obtain the configured provider."""
    lowered = model_name.lower()
    if "gpt" in lowered or "openai" in lowered or "o1" in lowered:
        return OpenAIProvider(model_name=model_name)
    elif "claude" in lowered or "anthropic" in lowered:
        return AnthropicProvider(model_name=model_name)
    else:
        from packages.models.mock import MockModelProvider
        return MockModelProvider(model_name=model_name)
