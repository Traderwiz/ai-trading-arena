from __future__ import annotations

import streamlit as st

from arena.dashboard.config import AGENT_COLORS, AGENT_META, PNL_NEGATIVE, PNL_POSITIVE, STARTING_CAPITAL_USDC, ordinal


def render_leaderboard(leaderboard_rows: list[dict], agents: list[dict], eliminations: list[dict]) -> None:
    st.subheader("Leaderboard")
    rows = _build_leaderboard_rows(leaderboard_rows, agents, eliminations)
    if not rows:
        st.info("Competition not yet started.")
        return

    for row in rows:
        color = AGENT_COLORS.get(row["agent_name"], "#999999")
        pnl_color = PNL_POSITIVE if row["pnl_percent"] >= 0 else PNL_NEGATIVE
        with st.container(border=True):
            cols = st.columns([1, 3, 2, 2, 1.5, 1.5])
            cols[0].markdown(f"### {ordinal(int(row['rank']))}")
            cols[1].markdown(
                f"### <span style='color:{color}'>{row['display_name']}</span><br><span style='font-size:0.9rem;color:#AAAAAA'>{row['archetype']}</span>",
                unsafe_allow_html=True,
            )
            cols[2].markdown(f"### ${row['total_equity_usdc']:.2f}")
            cols[3].markdown(
                f"### <span style='color:{pnl_color}'>{row['pnl_percent']:+.2f}%</span>",
                unsafe_allow_html=True,
            )
            cols[4].markdown(f"### {row['num_positions']}")
            status_label = "● Active" if row["status"] == "active" else f"✕ {row['status'].title()}"
            cols[5].markdown(
                f"<div style='color:{color if row['status']=='active' else '#777777'};font-weight:600'>{status_label}</div>{row['x_link']}",
                unsafe_allow_html=True,
            )


def _build_leaderboard_rows(leaderboard_rows: list[dict], agents: list[dict], eliminations: list[dict]) -> list[dict]:
    agent_map = {agent["agent_name"]: agent for agent in agents}
    elimination_map = {row["agent_name"]: row for row in eliminations}
    rows = []

    if leaderboard_rows:
        for row in leaderboard_rows:
            agent = agent_map.get(row["agent_name"], {})
            meta = AGENT_META.get(row["agent_name"], {})
            x_handle = agent.get("x_handle")
            rows.append(
                {
                    "agent_name": row["agent_name"],
                    "display_name": row.get("display_name") or meta.get("display_name", row["agent_name"].title()),
                    "archetype": meta.get("archetype", ""),
                    "rank": row.get("rank", len(rows) + 1),
                    "total_equity_usdc": float(row.get("total_equity_usdc", STARTING_CAPITAL_USDC)),
                    "pnl_percent": float(row.get("pnl_percent", 0.0)),
                    "num_positions": int(row.get("num_positions", 0)),
                    "status": row.get("status", "pending"),
                    "x_link": _x_link(x_handle),
                }
            )
    else:
        for index, agent_name in enumerate(["grok", "deepseek", "qwen", "llama"], start=1):
            agent = agent_map.get(agent_name, {"agent_name": agent_name, "status": "pending"})
            meta = AGENT_META.get(agent_name, {})
            rows.append(
                {
                    "agent_name": agent_name,
                    "display_name": meta.get("display_name", agent_name.title()),
                    "archetype": meta.get("archetype", ""),
                    "rank": index,
                    "total_equity_usdc": STARTING_CAPITAL_USDC,
                    "pnl_percent": 0.0,
                    "num_positions": 0,
                    "status": agent.get("status", "pending"),
                    "x_link": _x_link(agent.get("x_handle")),
                }
            )

    def sort_key(item):
        if item["status"] == "eliminated":
            finish_place = elimination_map.get(item["agent_name"], {}).get("finish_place", 99)
            return (1, finish_place)
        return (0, -item["pnl_percent"])

    return sorted(rows, key=sort_key)


def _x_link(handle: str | None) -> str:
    if not handle:
        return ""
    normalized = handle.lstrip("@")
    return f"[X](https://x.com/{normalized})"
