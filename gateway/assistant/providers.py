import json
from pathlib import Path

import httpx

from .models import MapPlan
from .secrets import get_secret


CONFIG_PATH = Path(__file__).resolve().parents[1] / "providers.json"
PLAN_SCHEMA = MapPlan.model_json_schema()
TOOL_NAME = "plan_map_request"
TOOL_DESCRIPTION = "Choose one supported map action for a Chinese user request. Never invent a destination."


class ProviderError(Exception):
    pass


def catalog() -> dict:
    return json.loads(CONFIG_PATH.read_text())


class ProviderClient:
    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    async def plan(self, provider: str, model: str | None, text: str) -> MapPlan:
        config = catalog().get(provider)
        if not config:
            raise ProviderError("未知模型供应商")
        key = get_secret(provider)
        if not key:
            raise ProviderError(f"尚未配置 {provider} API Key")
        selected_model = model or config["model"]
        protocol = config["protocol"]
        try:
            if protocol == "responses":
                raw = await self._responses(config["base_url"], key, selected_model, text)
            elif protocol == "anthropic":
                raw = await self._anthropic(config["base_url"], key, selected_model, text)
            else:
                raw = await self._chat(config["base_url"], key, selected_model, text)
            return MapPlan.model_validate(raw)
        except (httpx.HTTPError, KeyError, IndexError, StopIteration, ValueError) as exc:
            raise ProviderError(f"{provider} 未返回可用的地图动作") from exc

    async def _post(self, url: str, headers: dict, body: dict) -> dict:
        response = await self.client.post(url, headers=headers, json=body, timeout=25)
        response.raise_for_status()
        return response.json()

    async def _responses(self, base: str, key: str, model: str, text: str) -> dict:
        payload = await self._post(
            f"{base}/responses",
            {"Authorization": f"Bearer {key}"},
            {
                "model": model,
                "store": False,
                "input": [{"role": "user", "content": text}],
                "tools": [{"type": "function", "name": TOOL_NAME, "description": TOOL_DESCRIPTION, "parameters": PLAN_SCHEMA}],
                "tool_choice": {"type": "function", "name": TOOL_NAME},
                "parallel_tool_calls": False,
            },
        )
        call = next(item for item in payload["output"] if item.get("type") == "function_call" and item.get("name") == TOOL_NAME)
        return json.loads(call["arguments"])

    async def _chat(self, base: str, key: str, model: str, text: str) -> dict:
        payload = await self._post(
            f"{base}/chat/completions",
            {"Authorization": f"Bearer {key}"},
            {
                "model": model,
                "messages": [{"role": "user", "content": text}],
                "tools": [{"type": "function", "function": {"name": TOOL_NAME, "description": TOOL_DESCRIPTION, "parameters": PLAN_SCHEMA}}],
                "tool_choice": {"type": "function", "function": {"name": TOOL_NAME}},
            },
        )
        call = next(call for call in payload["choices"][0]["message"]["tool_calls"] if call["function"]["name"] == TOOL_NAME)
        return json.loads(call["function"]["arguments"])

    async def _anthropic(self, base: str, key: str, model: str, text: str) -> dict:
        payload = await self._post(
            f"{base}/messages",
            {"x-api-key": key, "anthropic-version": "2023-06-01"},
            {
                "model": model,
                "max_tokens": 512,
                "messages": [{"role": "user", "content": text}],
                "tools": [{"name": TOOL_NAME, "description": TOOL_DESCRIPTION, "input_schema": PLAN_SCHEMA}],
                "tool_choice": {"type": "tool", "name": TOOL_NAME},
            },
        )
        return next(item["input"] for item in payload["content"] if item.get("type") == "tool_use" and item.get("name") == TOOL_NAME)
