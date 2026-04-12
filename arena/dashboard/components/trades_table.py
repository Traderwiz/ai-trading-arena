from __future__ import annotations

import pandas as pd
import streamlit as st


def render_trades(trades_rows: list[dict]) -> None:
    st.subheader("Recent Trades")
    if not trades_rows:
        st.info("No trades yet.")
        return

    agent_filter = st.selectbox("Filter by agent", ["All"] + sorted({row["agent_name"] for row in trades_rows}), index=0)
    filtered = trades_rows if agent_filter == "All" else [row for row in trades_rows if row["agent_name"] == agent_filter]

    table_rows = []
    for row in filtered:
        tx_hash = row.get("tx_hash")
        table_rows.append(
            {
                "Timestamp": row.get("timestamp"),
                "Agent": row.get("agent_name"),
                "Side": str(row.get("side", "")).upper(),
                "Symbol": row.get("symbol"),
                "Quantity": row.get("quantity"),
                "Price (USDC)": row.get("price_usdc"),
                "Value (USDC)": row.get("usdc_value"),
                "Confidence": row.get("confidence"),
                "BaseScan": f"https://basescan.org/tx/{tx_hash}" if tx_hash else "",
            }
        )
    df = pd.DataFrame(table_rows)
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={"BaseScan": st.column_config.LinkColumn("BaseScan")} if hasattr(st, "column_config") else None,
    )
