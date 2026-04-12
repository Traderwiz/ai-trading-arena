from __future__ import annotations

import pandas as pd
import streamlit as st

from arena.dashboard.config import AGENT_META
from arena.dashboard.time_utils import format_timestamp_eastern


def render_activity_status(activity_rows: list[dict]) -> None:
    st.subheader("Activity Compliance")
    rows = _build_rows(activity_rows)
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)


def _build_rows(activity_rows: list[dict]) -> list[dict]:
    by_agent = {row["agent_name"]: row for row in activity_rows}
    rows = []
    for agent_name in ["grok", "deepseek", "qwen", "llama"]:
        row = by_agent.get(agent_name, {})
        rows.append(
            {
                "Agent": AGENT_META[agent_name]["display_name"],
                "Qualifying Trades": f"{int(row.get('qualifying_trades', 0))}/2",
                "Flag Status": _flag_label(row.get("flag_status", "clear")),
                "Flag Issued": format_timestamp_eastern(row.get("flag_issued_at"), fallback=str(row.get("flag_issued_at") or "")),
            }
        )
    return rows


def _flag_label(flag_status: str) -> str:
    return {
        "clear": "Clear ✅",
        "yellow": "Yellow 🟡",
        "red": "Red 🔴",
        "eliminated": "Eliminated ✕",
    }.get(flag_status, flag_status.title())
