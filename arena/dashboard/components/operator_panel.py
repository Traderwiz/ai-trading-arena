from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from arena.dashboard.time_utils import format_timestamp_eastern


def render_operator_panel(latest_loop: dict | None, rejection_rows: list[dict]) -> None:
    st.subheader("Operator View")
    _render_latest_loop(latest_loop)
    _render_recent_rejections(rejection_rows)


def _render_latest_loop(latest_loop: dict | None) -> None:
    if not latest_loop:
        st.info("No loop diagnostics yet.")
        return

    errors = latest_loop.get("errors") or {}
    diagnostics = errors.get("agent_diagnostics") or {}
    fallback_mode = errors.get("fallback_mode") or []
    cols = st.columns(4)
    cols[0].metric("Loop Number", latest_loop.get("loop_number", "-"))
    cols[1].metric("Agents Processed", len(latest_loop.get("agents_processed") or []))
    cols[2].metric("Fallback Agents", len(fallback_mode))
    cols[3].metric("Agent Errors", len(errors.get("agent_errors") or {}))
    st.caption(f"Completed: {format_timestamp_eastern(latest_loop.get('completed_at'), fallback=str(latest_loop.get('completed_at', '')))}")

    if fallback_mode:
        st.warning("Fallback mode active: " + ", ".join(fallback_mode))

    for agent_name in sorted(diagnostics.keys()):
        diag = diagnostics.get(agent_name) or {}
        with st.expander(f"{agent_name.title()} diagnostics", expanded=False):
            trade = diag.get("parsed_trade_decision")
            comms = diag.get("parsed_comms_decision") or {}
            validation = diag.get("trade_validation") or {}
            execution = diag.get("trade_execution") or {}
            qualification = diag.get("trade_qualification") or {}
            token_usage = (latest_loop.get("token_usage") or {}).get(agent_name) or {}

            summary_rows = [
                {"Field": "Trade decision", "Value": _format_trade(trade)},
                {"Field": "Trade validation", "Value": "approved" if validation.get("approved") else validation.get("rejection_reason", "n/a")},
                {"Field": "Execution", "Value": "success" if execution.get("success") else execution.get("error", "n/a")},
                {"Field": "Qualifying trade", "Value": _format_qualification(qualification)},
                {"Field": "Chat", "Value": str(comms.get("chat") or "")[:180]},
                {"Field": "Social", "Value": str(comms.get("social") or "")[:180]},
                {"Field": "Market symbols", "Value": ", ".join(diag.get("market_snapshot_symbols") or [])},
            ]
            st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)

            if token_usage:
                st.markdown("**Token usage**")
                st.code(json.dumps(token_usage, indent=2), language="json")


def _render_recent_rejections(rejection_rows: list[dict]) -> None:
    st.markdown("**Recent Trade Rejections**")
    if not rejection_rows:
        st.caption("No recent trade rejections.")
        return

    rows = []
    for row in rejection_rows:
        input_data = row.get("input_data") or {}
        rows.append(
            {
                "Timestamp": format_timestamp_eastern(row.get("timestamp"), fallback=str(row.get("timestamp", ""))),
                "Agent": row.get("agent_name"),
                "Symbol": input_data.get("symbol"),
                "Side": str(input_data.get("side", "")).upper(),
                "Quantity": input_data.get("quantity"),
                "Reason": row.get("rejection_reason"),
            }
        )
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def _format_trade(trade: dict | None) -> str:
    if not trade:
        return "none"
    return f"{trade.get('side')} {trade.get('quantity')} {trade.get('symbol')}"


def _format_qualification(qualification: dict) -> str:
    if not qualification:
        return "n/a"
    return (
        f"{'yes' if qualification.get('qualified') else 'no'} "
        f"(value ${float(qualification.get('trade_usdc_value') or 0):.2f}, "
        f"threshold ${float(qualification.get('threshold_usdc') or 0):.2f})"
    )
