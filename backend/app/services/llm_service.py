import json
from abc import ABC, abstractmethod
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.core.config import (
    LLM_PROVIDER,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    OPENAI_API_KEY,
    OPENAI_MODEL,
    LLM_TIMEOUT_SECONDS,
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


class OllamaProvider(LLMProvider):
    name = "ollama"

    def __init__(self):
        self.model = OLLAMA_MODEL

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        data = self._post(
            f"{OLLAMA_BASE_URL}/api/chat",
            {
                "model": self.model,
                "stream": False,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "options": {"temperature": 0.2},
            },
        )
        return data["message"]["content"].strip()


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(self):
        if not OPENAI_API_KEY:
            raise LLMError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")
        self.model = OPENAI_MODEL

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        data = self._post(
            "https://api.openai.com/v1/responses",
            {
                "model": self.model,
                "instructions": system_prompt,
                "input": user_prompt,
                "reasoning": {"effort": "low"},
                "text": {"verbosity": "medium"},
            },
            {"Authorization": f"Bearer {OPENAI_API_KEY}"},
        )
        if data.get("output_text"):
            return data["output_text"].strip()
        for item in data.get("output", []):
            for content in item.get("content", []):
                if content.get("type") == "output_text":
                    return content.get("text", "").strip()
        raise LLMError("The OpenAI response did not contain output text")


def get_llm_provider() -> LLMProvider:
    return OpenAIProvider() if LLM_PROVIDER == "openai" else OllamaProvider()
