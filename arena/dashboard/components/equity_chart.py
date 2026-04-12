from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from arena.dashboard.config import AGENT_COLORS, STARTING_LINE_COLOR, THRESHOLD_COLOR


def render_equity_chart(standings_rows: list[dict]) -> None:
    st.subheader("Equity Curves")
    if not standings_rows:
        st.info("Competition not yet started.")
        return

    df = pd.DataFrame(standings_rows)
    if df.empty:
        st.info("Competition not yet started.")
        return
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    if len(df) > 1000:
        df = df.groupby("agent_name", group_keys=False).apply(lambda group: group.iloc[:: max(1, len(group) // 250)]).reset_index(drop=True)

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

    fig.add_hline(y=100, line_dash="dot", line_color=STARTING_LINE_COLOR, annotation_text="$100 start")
    fig.add_hline(y=10, line_dash="dash", line_color=THRESHOLD_COLOR, annotation_text="$10 elimination")
    fig.update_layout(
        template="plotly_dark",
        height=420,
        margin={"l": 20, "r": 20, "t": 20, "b": 20},
        xaxis_title="Time",
        yaxis_title="Equity (USDC)",
        legend_title="Agent",
    )
    st.plotly_chart(fig, use_container_width=True)
