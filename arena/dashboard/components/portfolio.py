from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from arena.dashboard.config import AGENT_COLORS, AGENT_META


def render_portfolios(agents: list[dict], current_standings: list[dict], positions_rows: list[dict]) -> None:
    st.subheader("Portfolio Breakdown")
    standings_map = {row["agent_name"]: row for row in current_standings}
    positions_map: dict[str, list[dict]] = {}
    for row in positions_rows:
        positions_map.setdefault(row["agent_name"], []).append(row)

    for agent_name in ["grok", "deepseek", "qwen", "llama"]:
        meta = AGENT_META[agent_name]
        with st.expander(f"{meta['display_name']}"):
            rows = positions_map.get(agent_name, [])
            standing = standings_map.get(agent_name, {})
            cash_usdc = float(standing.get("cash_usdc", 100.0 if not current_standings else 0.0))
            if rows:
                df = pd.DataFrame(rows)[["symbol", "quantity", "current_price_usdc", "current_value_usdc", "unrealized_pnl_usdc"]]
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.caption("No open positions.")

            st.markdown(f"**Cash (USDC):** ${cash_usdc:.2f}")
            labels = ["Cash"] + [row["symbol"] for row in rows]
            values = [cash_usdc] + [float(row.get("current_value_usdc", 0.0)) for row in rows]
            fig = go.Figure(
                go.Pie(
                    labels=labels,
                    values=values,
                    hole=0.45,
                    marker={"colors": [_cash_color(agent_name)] + [_position_color(agent_name, index) for index in range(len(rows))]},
                )
            )
            fig.update_layout(template="plotly_dark", height=300, margin={"l": 20, "r": 20, "t": 20, "b": 20})
            st.plotly_chart(fig, use_container_width=True)


def _cash_color(agent_name: str) -> str:
    return AGENT_COLORS.get(agent_name, "#888888")


def _position_color(agent_name: str, offset: int) -> str:
    palette = [AGENT_COLORS.get(agent_name, "#888888"), "#999999", "#BBBBBB", "#666666"]
    return palette[offset % len(palette)]
