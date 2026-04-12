from __future__ import annotations

from typing import Any

from openai import OpenAI


class LLMError(RuntimeError):
    pass


DEFAULT_LLM_CONFIGS = {
    "grok": {
        "base_url": "https://api.x.ai/v1",
        "model": "grok-4-1-fast-non-reasoning",
        "api_key": "${XAI_API_KEY}",
        "temperature": 0.7,
        "max_tokens": 800,
        "response_format": True,
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
        "api_key": "${DEEPSEEK_API_KEY}",
        "temperature": 0.7,
        "max_tokens": 800,
        "response_format": True,
    },
    "qwen": {
        "base_url": "http://100.93.133.94:1234/v1",
        "model": "qwen2.5-14b-instruct-1m",
        "api_key": "lm-studio",
        "temperature": 0.7,
        "max_tokens": 800,
        "response_format": True,
    },
    "llama": {
        "base_url": "http://100.93.133.94:1234/v1",
        "model": "meta-llama-3.1-8b-instruct",
        "api_key": "lm-studio",
        "temperature": 0.7,
        "max_tokens": 800,
        "response_format": True,
    },
}


class LLMClient:
    def __init__(self, agent_name: str, config: dict | None = None, client: OpenAI | None = None):
        supplied = config or {}
        if "llm" in supplied:
            all_configs = {**DEFAULT_LLM_CONFIGS, **supplied["llm"]}
        elif agent_name in supplied:
            all_configs = {**DEFAULT_LLM_CONFIGS, **supplied}
        else:
            all_configs = DEFAULT_LLM_CONFIGS
        if agent_name not in all_configs:
            raise LLMError(f"No LLM config for {agent_name}")
        self.agent_name = agent_name
        self.config = all_configs[agent_name]
        self.client = client or OpenAI(base_url=self.config["base_url"], api_key=self.config["api_key"])
        self.model = self.config["model"]
        self.last_response_meta: dict[str, Any] = {}

    @property
    def is_local(self) -> bool:
        base_url = str(self.config.get("base_url", ""))
        return "100.93.133.94" in base_url or "lm-studio" in base_url.lower()

    def call(self, system_prompt: str, user_prompt: str, temperature: float | None = None, max_tokens: int | None = None) -> str:
        temperature = self.config.get("temperature", 0.7) if temperature is None else temperature
        max_tokens = self.config.get("max_tokens", 800) if max_tokens is None else max_tokens
        request: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if self.config.get("response_format", True):
            request["response_format"] = {"type": "json_object"}

        try:
            response = self.client.chat.completions.create(**request)
        except Exception as exc:  # noqa: BLE001
            if "response_format" in str(exc) and "response_format" in request:
                request.pop("response_format", None)
                try:
                    response = self.client.chat.completions.create(**request)
                except Exception as retry_exc:  # noqa: BLE001
                    raise LLMError(str(retry_exc)) from retry_exc
            else:
                raise LLMError(str(exc)) from exc

        try:
            raw = response.choices[0].message.content
        except Exception as exc:  # noqa: BLE001
            raise LLMError("LLM response missing message content") from exc
        usage = getattr(response, "usage", None)
        self.last_response_meta = {
            "model": self.model,
            "usage": {
                "prompt_tokens": getattr(usage, "prompt_tokens", None),
                "completion_tokens": getattr(usage, "completion_tokens", None),
                "total_tokens": getattr(usage, "total_tokens", None),
            },
        }
        if not raw:
            raise LLMError("LLM returned empty content")
        return raw

    def ping(self) -> bool:
        return bool(self.model and self.config.get("base_url"))
