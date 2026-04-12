from __future__ import annotations

from datetime import datetime, timezone

import streamlit as st
from streamlit_autorefresh import st_autorefresh

from arena.dashboard.components.activity_status import render_activity_status
from arena.dashboard.components.chat_feed import render_chat
from arena.dashboard.components.elimination_log import render_eliminations
from arena.dashboard.components.equity_chart import render_equity_chart
from arena.dashboard.components.leaderboard import render_leaderboard
from arena.dashboard.components.portfolio import render_portfolios
from arena.dashboard.components.trades_table import render_trades
from arena.dashboard.config import DISCLAIMER, REFRESH_INTERVAL_MS, derive_phase, derive_status
from arena.dashboard.supabase_client import get_client


st.set_page_config(
    page_title="AI Trading Arena",
    page_icon="🏟️",
    layout="wide",
    initial_sidebar_state="collapsed",
)
st_autorefresh(interval=REFRESH_INTERVAL_MS, key="arena_refresh")


def main() -> None:
    client = get_client()
    agents = client.get_agents()
    leaderboard_rows = client.get_leaderboard()
    standings_rows = client.get_standings_history()
    current_standings = client.get_current_standings()
    positions_rows = client.get_current_positions()
    trades_rows = client.get_recent_trades(limit=20)
    all_trades_rows = client.get_recent_trades(limit=200)
    chat_rows = client.get_recent_chat(limit=50)
    activity_rows = client.get_current_week_activity() or client.get_activity_tracking()
    elimination_rows = client.get_eliminations()
    latest_loop = client.get_latest_loop_log()

    active_count = len([row for row in agents if row.get("status") == "active"])
    elimination_count = len(elimination_rows)
    current_phase = derive_phase(active_count, elimination_count)
    competition_status = "COMPLETE" if active_count <= 1 and agents else derive_status(latest_loop.get("completed_at") if latest_loop else None, 60)

    _render_header(competition_status, current_phase, latest_loop)
    render_leaderboard(leaderboard_rows, agents, elimination_rows)
    render_equity_chart(standings_rows)
    render_portfolios(agents, current_standings, positions_rows)
    render_trades(trades_rows)
    render_chat(chat_rows)
    render_activity_status(activity_rows)
    render_eliminations(elimination_rows, all_trades_rows)
    _render_footer()


def _render_header(status: str, current_phase: str, latest_loop: dict | None) -> None:
    st.title("AI TRADING ARENA")
    st.caption("Big Brother meets Wall Street - AI agents trading crypto with real money")
    cols = st.columns([1.3, 1.5, 2])
    cols[0].markdown(_status_badge(status), unsafe_allow_html=True)
    cols[1].markdown(f"**Phase:** {current_phase}")
    last_updated = latest_loop.get("completed_at") if latest_loop else None
    if not last_updated:
        last_updated = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    cols[2].markdown(f"**Last updated:** {last_updated}")
    st.warning(DISCLAIMER, icon="⚠️")


def _status_badge(status: str) -> str:
    color = {"LIVE": "#00C853", "PAUSED": "#FFD600", "COMPLETE": "#888888"}.get(status, "#888888")
    return f"<span style='background:{color};color:#111111;padding:0.35rem 0.7rem;border-radius:6px;font-weight:700'>{status}</span>"


def _render_footer() -> None:
    st.divider()
    st.markdown("[@AITradingArena](https://x.com/AITradingArena)")
    st.caption("Season 1 - Experiment")
    st.caption(DISCLAIMER)


if __name__ == "__main__":
    main()
