from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

try:
    import streamlit as st
except ImportError:  # pragma: no cover
    st = None

try:
    from supabase import create_client
except ImportError:  # pragma: no cover
    create_client = None


class DashboardSupabaseClient:
    def __init__(self, client):
        self.client = client

    def get_leaderboard(self):
        return self._read("leaderboard", order=("rank", False))

    def get_standings_history(self):
        return self._read("standings", order=("timestamp", False))

    def get_current_positions(self):
        return self._read("positions", order=("agent_name", False))

    def get_recent_trades(self, limit=20):
        return self._read("trades", order=("timestamp", True), limit=limit)

    def get_recent_chat(self, limit=50):
        return self._read("chat_logs", order=("timestamp", True), limit=limit)

    def get_activity_tracking(self):
        return self._read("activity_tracking", order=("week_start", True))

    def get_eliminations(self):
        return self._read("eliminations", order=("timestamp", False))

    def get_agents(self):
        return self._read("agents", order=("agent_name", False))

    def get_current_standings(self):
        return self._read("current_standings", order=("agent_name", False))

    def get_latest_loop_log(self):
        rows = self._read("loop_log", order=("loop_number", True), limit=1)
        return rows[0] if rows else None

    def get_current_week_activity(self):
        week_start = (datetime.now(timezone.utc) - timedelta(days=datetime.now(timezone.utc).weekday())).date().isoformat()
        return self._read("activity_tracking", filters={"week_start": week_start}, order=("agent_name", False))

    def _read(self, table_name, filters=None, order=None, limit=None):
        query = self.client.table(table_name).select("*")
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


def get_client():
    if create_client is None:
        raise RuntimeError("supabase package is not installed")
    url = _get_secret("SUPABASE_URL")
    key = _get_secret("SUPABASE_SERVICE_KEY") or _get_secret("SUPABASE_READER_KEY")
    if not url:
        raise RuntimeError("Set SUPABASE_URL in Streamlit secrets, a [supabase] section, or environment variables")
    if not key:
        raise RuntimeError("Set SUPABASE_SERVICE_KEY or SUPABASE_READER_KEY in Streamlit secrets, a [supabase] section, or environment variables")
    return DashboardSupabaseClient(create_client(url, key))


def _get_secret(key: str) -> str | None:
    try:
        import streamlit as st
        try:
            return str(st.secrets[key])
        except (KeyError, FileNotFoundError):
            pass

        lower_key = key.lower()
        for section_name in ("supabase", "general"):
            try:
                section = st.secrets[section_name]
            except (KeyError, FileNotFoundError):
                continue

            if isinstance(section, dict):
                if key in section:
                    return str(section[key])
                if lower_key in section:
                    return str(section[lower_key])
    except Exception:
        pass
    return os.environ.get(key)
