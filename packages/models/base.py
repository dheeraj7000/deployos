"""Model Provider Interface and Structured Generation Abstraction."""

from abc import ABC, abstractmethod
from typing import Any, TypeVar, Type, Optional
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class ModelResponse(BaseModel):
    content: str
    parsed: Optional[Any] = None
    model_name: str
    tokens_input: int = 0
    tokens_output: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: float = 0.0


class ModelProvider(ABC):
    """Abstract base class for LLM inference providers."""

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> ModelResponse:
        """Standard text generation."""
        pass

    @abstractmethod
    async def structured_generate(
        self,
        schema: Type[T],
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.0,
    ) -> tuple[T, ModelResponse]:
        """Strict JSON/Pydantic structured output generation."""
        pass
