import json
from abc import ABC, abstractmethod
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.core.config import (
    LLM_TIMEOUT_SECONDS,
    LLM_PROVIDER,
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    OPENROUTER_MODEL,
)


class LLMError(RuntimeError):
    pass


class LLMProvider(ABC):
    name: str
    model: str

    @abstractmethod
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        raise NotImplementedError

    @staticmethod
    def _post(url: str, payload: dict, headers: dict | None = None) -> dict:
        request = Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", **(headers or {})},
            method="POST",
        )
        try:
            with urlopen(request, timeout=LLM_TIMEOUT_SECONDS) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise LLMError(f"LLM request failed ({exc.code}): {detail}") from exc
        except (URLError, TimeoutError) as exc:
            raise LLMError(f"Unable to reach the configured LLM: {exc}") from exc


class OpenRouterProvider(LLMProvider):
    name = "openrouter"

    def __init__(self):
        if not OPENROUTER_API_KEY:
            raise LLMError("OPENROUTER_API_KEY is required when LLM_PROVIDER=openrouter")
        self.model = OPENROUTER_MODEL

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        data = self._post(
            f"{OPENROUTER_BASE_URL}/chat/completions",
            {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            },
            {
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "HTTP-Referer": "http://localhost:5173",
                "X-Title": "Basketball RAG Scouting Console",
            },
        )
        try:
            return data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError("The OpenRouter response did not contain message content") from exc


def get_llm_provider() -> LLMProvider:
    return OpenRouterProvider()
