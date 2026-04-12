from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from arena.sanity.sanity_checker import STABLECOINS


@dataclass
class ActivityStatus:
    agent_name: str
    week_start: date
    qualifying_trades: int
    daily_chats_completed: int
    flag_status: str
    warning: str = ""


@dataclass
class ActivityEvent:
    agent_name: str
    flag_status: str
    details: str
    elimination_required: bool = False


class ActivityTracker:
    def __init__(self, supabase_client, config: dict | None = None, now_provider=None):
        self.supabase = supabase_client
        self.config = (config or {}).get("activity", config or {})
        self.min_trades_per_week = int(self.config.get("min_trades_per_week", 2))
        self.min_trade_value_usdc = float(self.config.get("min_trade_value_usdc", 10.0))
        self.min_trade_value_percent = float(self.config.get("min_trade_value_percent", 0.10))
        self.now_provider = now_provider or (lambda: datetime.now(timezone.utc))

    def get_status(self, agent_name: str, now: datetime | None = None) -> ActivityStatus:
        now = now or self.now_provider()
        week_start = current_week_start(now)
        row = self._get_or_create_week(agent_name, week_start)
        return ActivityStatus(
            agent_name=agent_name,
            week_start=week_start,
            qualifying_trades=int(row.get("qualifying_trades", 0)),
            daily_chats_completed=int(row.get("daily_chats_completed", 0)),
            flag_status=row.get("flag_status", "clear"),
            warning=_warning_for_flag(row.get("flag_status", "clear")),
        )

    def update_activity(
        self,
        agent_name: str,
        trade_details: dict | None,
        total_equity_usdc: float,
        chat_posted: bool = False,
        now: datetime | None = None,
    ) -> ActivityStatus:
        now = now or self.now_provider()
        week_start = current_week_start(now)
        row = self._get_or_create_week(agent_name, week_start)

        updates = {}
        if chat_posted:
            updates["daily_chats_completed"] = int(row.get("daily_chats_completed", 0)) + 1

        if self.trade_qualifies(trade_details, total_equity_usdc):
            updates["qualifying_trades"] = int(row.get("qualifying_trades", 0)) + 1

        if updates:
            self._update_activity_row(agent_name, week_start, updates)
        return self.get_status(agent_name, now)

    def evaluate_weekly_compliance(self, agent_names: list[str], now: datetime | None = None) -> list[ActivityEvent]:
        now = now or self.now_provider()
        if not is_weekly_evaluation_time(now):
            return []

        events: list[ActivityEvent] = []
        for agent_name in agent_names:
            status = self.get_status(agent_name, now)
            if status.qualifying_trades >= self.min_trades_per_week:
                self._update_activity_row(agent_name, status.week_start, {"flag_status": "clear"})
                continue

            missed_weeks = self._count_consecutive_missed_weeks(agent_name, status.week_start)
            if missed_weeks >= 3:
                flag_status = "eliminated"
                details = "Third consecutive missed week - eliminate for inactivity"
                elimination_required = True
            elif missed_weeks == 2:
                flag_status = "red"
                details = "Second consecutive missed week - Red Flag"
                elimination_required = False
            else:
                flag_status = "yellow"
                details = "First missed week - Yellow Flag"
                elimination_required = False

            self._update_activity_row(
                agent_name,
                status.week_start,
                {"flag_status": flag_status, "flag_issued_at": now.isoformat()},
            )
            events.append(ActivityEvent(agent_name, flag_status, details, elimination_required))
        return events

    def trade_qualifies(self, trade_details: dict | None, total_equity_usdc: float) -> bool:
        if not trade_details:
            return False
        if trade_details.get("success") is False:
            return False
        symbol = str(trade_details.get("symbol", "")).upper()
        if symbol in STABLECOINS:
            return False
        usdc_value = float(trade_details.get("usdc_value") or 0)
        threshold = min(self.min_trade_value_usdc, total_equity_usdc * self.min_trade_value_percent)
        return usdc_value >= threshold

    def _count_consecutive_missed_weeks(self, agent_name: str, current_week_start: date) -> int:
        rows = self._fetch_rows("activity_tracking", {"agent_name": agent_name}, order=("week_start", True))
        expected = current_week_start
        count = 0
        for row in rows:
            week_start = _coerce_date(row.get("week_start"))
            if week_start != expected:
                break
            if int(row.get("qualifying_trades", 0)) >= self.min_trades_per_week:
                break
            count += 1
            expected = expected - timedelta(days=7)
        return count

    def _get_or_create_week(self, agent_name: str, week_start: date) -> dict:
        rows = self._fetch_rows("activity_tracking", {"agent_name": agent_name, "week_start": week_start.isoformat()}, limit=1)
        if rows:
            return rows[0]
        row = {
            "agent_name": agent_name,
            "week_start": week_start.isoformat(),
            "qualifying_trades": 0,
            "daily_chats_completed": 0,
            "flag_status": "clear",
        }
        self.supabase.table("activity_tracking").insert(row).execute()
        return row

    def _update_activity_row(self, agent_name: str, week_start: date, updates: dict) -> None:
        query = self.supabase.table("activity_tracking").update(updates).eq("agent_name", agent_name).eq("week_start", week_start.isoformat())
        query.execute()

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


def current_week_start(now: datetime) -> date:
    now = now.astimezone(timezone.utc)
    return (now - timedelta(days=now.weekday())).date()


def is_weekly_evaluation_time(now: datetime) -> bool:
    now = now.astimezone(timezone.utc)
    return now.weekday() == 6 and now.hour == 23


def _warning_for_flag(flag_status: str) -> str:
    return {
        "yellow": "Yellow Flag: you missed the weekly trade minimum.",
        "red": "Red Flag: one more missed week means elimination.",
        "eliminated": "You are out for inactivity.",
    }.get(flag_status, "")


def _coerce_date(value) -> date:
    if isinstance(value, date):
        return value
    return datetime.fromisoformat(str(value)).date()
