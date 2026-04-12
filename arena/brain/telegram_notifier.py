from __future__ import annotations

import json
from urllib.request import Request, urlopen


class TelegramNotifier:
    def __init__(self, config: dict | None = None, opener=urlopen):
        self.config = config or {}
        self.opener = opener
        self.bot_token = self.config.get("bot_token")
        self.chat_id = self.config.get("chat_id")
        self.low_priority_queue: list[str] = []

    def send_low(self, message: str) -> None:
        self.low_priority_queue.append(message)

    def flush_low(self) -> None:
        if not self.low_priority_queue:
            return
        message = "\n".join(self.low_priority_queue)
        self.low_priority_queue.clear()
        self._send(message)

    def send_medium(self, message: str) -> None:
        self._send(message)

    def send_high(self, message: str) -> None:
        self._send(message)

    def send_critical(self, message: str) -> None:
        self._send(message)

    def _send(self, message: str) -> None:
        if not self.bot_token or not self.chat_id:
            return
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        body = json.dumps({"chat_id": self.chat_id, "text": message}).encode("utf-8")
        request = Request(url, data=body, headers={"Content-Type": "application/json"})
        with self.opener(request, timeout=10):
            return
