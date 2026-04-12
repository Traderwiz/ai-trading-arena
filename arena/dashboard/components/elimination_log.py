from __future__ import annotations

import streamlit as st

from arena.dashboard.config import ordinal


def render_eliminations(elimination_rows: list[dict], trades_rows: list[dict]) -> None:
    if not elimination_rows:
        return
    st.subheader("Elimination Log")
    trade_map = {row["id"]: row for row in trades_rows if row.get("id") is not None}
    for row in elimination_rows:
        with st.container(border=True):
            finish_place = row.get("finish_place")
            st.markdown(f"### {row.get('agent_name', '').title()} - {ordinal(int(finish_place)) if finish_place else 'Eliminated'}")
            st.markdown(f"**Final equity:** ${float(row.get('final_equity_usdc', 0)):.2f}")
            st.markdown(f"**Type:** {row.get('elimination_type', 'unknown').title()}")
            st.markdown(f"**Timestamp:** {row.get('timestamp', '')}")
            if row.get("last_words"):
                st.markdown(f"**Last words:** {row['last_words']}")
            fatal_trade = trade_map.get(row.get("fatal_trade_id"))
            if fatal_trade:
                st.markdown(
                    f"**Fatal trade:** {fatal_trade.get('side')} {fatal_trade.get('quantity')} {fatal_trade.get('symbol')} @ ${float(fatal_trade.get('price_usdc', 0)):.4f}"
                )
