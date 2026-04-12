from __future__ import annotations

from datetime import datetime, timedelta, timezone

from arena.brain.llm_client import LLMClient, LLMError


class MemoryManager:
    def __init__(self, supabase_client, config: dict | None = None, summary_client: LLMClient | None = None, now_provider=None):
        self.supabase = supabase_client
        self.config = (config or {}).get("memory", config or {})
        self.summary_client = summary_client or LLMClient("deepseek", config)
        self.daily_summary_hour = int(self.config.get("daily_summary_hour_utc", 0))
        self.weekly_summary_day = int(self.config.get("weekly_summary_day", 6))
        self.now_provider = now_provider or (lambda: datetime.now(timezone.utc))

    def get_latest_summaries(self, agent_name: str) -> dict:
        daily = self._fetch_rows(
            "memory_summaries",
            {"agent_name": agent_name, "summary_type": "daily"},
            order=("period_end", True),
            limit=1,
        )
        weekly = self._fetch_rows(
            "memory_summaries",
            {"agent_name": agent_name, "summary_type": "weekly"},
            order=("period_end", True),
            limit=1,
        )
        return {
            "daily_summary": daily[0]["content"] if daily else "No daily summary yet.",
            "weekly_summary": weekly[0]["content"] if weekly else "No weekly summary yet.",
        }

    def generate_due_summaries(self, agent_names: list[str], now: datetime | None = None) -> None:
        now = now or self.now_provider()
        if now.hour == self.daily_summary_hour:
            for agent_name in agent_names:
                try:
                    self.generate_daily_summary(agent_name, now)
                except LLMError:
                    continue
        if now.weekday() == self.weekly_summary_day and now.hour == self.daily_summary_hour:
            for agent_name in agent_names:
                try:
                    self.generate_weekly_summary(agent_name, now)
                except LLMError:
                    continue

    def generate_daily_summary(self, agent_name: str, now: datetime | None = None) -> str:
        now = now or self.now_provider()
        day_start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
        trades = self._fetch_rows("trades", {"agent_name": agent_name})
        chat = self._fetch_rows("chat_logs", {"sender": agent_name})
        standings = self._fetch_rows("standings", {"agent_name": agent_name}, order=("timestamp", True), limit=5)
        prompt = (
            f"Summarize today's Arena activity for {agent_name} in exactly 200 words.\n"
            f"Cover: key trades, P&L change, notable chat moments, rivalries, strategy shifts, and current competitive position.\n\n"
            f"Today's data:\nTrades: {trades}\nChat: {chat}\nStandings: {standings}"
        )
        content = self.summary_client.call("Respond in plain text only.", prompt)
        self.supabase.table("memory_summaries").insert(
            {
                "agent_name": agent_name,
                "summary_type": "daily",
                "period_start": day_start.isoformat(),
                "period_end": now.isoformat(),
                "content": content,
            }
        ).execute()
        return content

    def generate_weekly_summary(self, agent_name: str, now: datetime | None = None) -> str:
        now = now or self.now_provider()
        week_start = now - timedelta(days=7)
        daily_summaries = self._fetch_rows("memory_summaries", {"agent_name": agent_name, "summary_type": "daily"})
        prompt = (
            f"Compress this week's daily summaries for {agent_name} into a 500-word weekly summary.\n"
            f"Daily summaries: {daily_summaries}"
        )
        content = self.summary_client.call("Respond in plain text only.", prompt)
        self.supabase.table("memory_summaries").insert(
            {
                "agent_name": agent_name,
                "summary_type": "weekly",
                "period_start": week_start.isoformat(),
                "period_end": now.isoformat(),
                "content": content,
            }
        ).execute()
        return content

    def _fetch_rows(self, table_name: str, filters: dict | None = None, order: tuple[str, bool] | None = None, limit: int | None = None) -> list[dict]:
        query = self.supabase.table(table_name).select("*")
        for field, value in (filters or {}).items():
            query = query.eq(field, value)
        if order:
            query = query.order(order[0], desc=order[1])
        if limit:
            query = query.limit(limit)
        response = query.execute()
        if isinstance(response, dict):
            return response.get("data", [])
        return getattr(response, "data", [])
