from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from arena.dashboard.config import AGENT_COLORS, STARTING_CAPITAL_USDC, STARTING_LINE_COLOR, THRESHOLD_COLOR
from arena.dashboard.time_utils import EASTERN_TZ

ELIMINATION_THRESHOLD_USDC = 10.0


def render_equity_chart(standings_rows: list[dict]) -> None:
    st.subheader("Equity Curves")
    if not standings_rows:
        st.info("Competition not yet started.")
        return

    df = pd.DataFrame(standings_rows)
    if df.empty:
        st.info("Competition not yet started.")
        return
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True).dt.tz_convert(EASTERN_TZ)
    if len(df) > 1000:
        df = df.groupby("agent_name", group_keys=False).apply(lambda group: group.iloc[:: max(1, len(group) // 250)]).reset_index(drop=True)
    df["total_equity_usdc"] = pd.to_numeric(df["total_equity_usdc"], errors="coerce")
    df = df.dropna(subset=["total_equity_usdc"])
    if df.empty:
        st.info("Competition not yet started.")
        return

    fig = go.Figure()
    for agent_name, group in df.groupby("agent_name"):
        fig.add_trace(
            go.Scatter(
                x=group["timestamp"],
                y=group["total_equity_usdc"],
                mode="lines",
                name=agent_name.title(),
                line={"color": AGENT_COLORS.get(agent_name, "#999999"), "width": 3},
            )
        )

    y_values = list(df["total_equity_usdc"].astype(float))
    reference_lines = [STARTING_CAPITAL_USDC, ELIMINATION_THRESHOLD_USDC]
    visible_values = y_values + reference_lines
    y_min = min(visible_values)
    y_max = max(visible_values)
    padding = max(0.5, (y_max - y_min) * 0.12)
    range_min = max(0, y_min - padding)
    range_max = y_max + padding

    if abs(STARTING_CAPITAL_USDC - ELIMINATION_THRESHOLD_USDC) < 1e-9:
        fig.add_hline(
            y=STARTING_CAPITAL_USDC,
            line_dash="dash",
            line_color=THRESHOLD_COLOR,
            annotation_text=f"${STARTING_CAPITAL_USDC:.0f} start / elimination",
        )
    else:
        fig.add_hline(
            y=STARTING_CAPITAL_USDC,
            line_dash="dot",
            line_color=STARTING_LINE_COLOR,
            annotation_text=f"${STARTING_CAPITAL_USDC:.0f} start",
        )
        fig.add_hline(
            y=ELIMINATION_THRESHOLD_USDC,
            line_dash="dash",
            line_color=THRESHOLD_COLOR,
            annotation_text=f"${ELIMINATION_THRESHOLD_USDC:.0f} elimination",
        )
    fig.update_layout(
        template="plotly_dark",
        height=420,
        margin={"l": 20, "r": 20, "t": 20, "b": 20},
        xaxis_title="Time",
        yaxis_title="Equity (USDC)",
        legend_title="Agent",
        yaxis={"range": [range_min, range_max]},
    )
    st.plotly_chart(fig, use_container_width=True)
