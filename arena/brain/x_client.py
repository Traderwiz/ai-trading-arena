from __future__ import annotations

import json
from urllib.request import Request, urlopen


class XClientError(RuntimeError):
    pass


class XClient:
    def __init__(self, config: dict | None = None, opener=urlopen):
        self.config = config or {}
        self.opener = opener
        self.bearer_tokens = self.config.get("bearer_tokens", {})
        self.enabled = self.config.get("enabled", True)

    def post(self, agent_name: str, content: str) -> dict:
        if not self.enabled:
            return {"id": None, "status": "disabled", "content": content}
        token = self.bearer_tokens.get(agent_name)
        if not token:
            raise XClientError(f"No X token configured for {agent_name}")
        request = Request(
            "https://api.x.com/2/tweets",
            data=json.dumps({"text": content}).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with self.opener(request, timeout=10) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            raise XClientError(str(exc)) from exc
        if "data" not in payload:
            raise XClientError("X API response missing data")
        return payload["data"]
