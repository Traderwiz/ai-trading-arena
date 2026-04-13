from __future__ import annotations

import streamlit as st

from arena.dashboard.config import AGENT_COLORS, CHAT_FEED_DEFAULT_LIMIT
from arena.dashboard.time_utils import format_timestamp_eastern


def render_chat(chat_rows: list[dict]) -> None:
    st.subheader("Group Chat")
    st.caption("Newest first.")
    if not chat_rows:
        st.info("No messages yet.")
        return

    sorted_rows = sorted(chat_rows, key=lambda row: str(row.get("timestamp", "")), reverse=True)
    feed_mode = st.radio(
        "Feed",
        ("Agent posts", "All messages"),
        horizontal=True,
        label_visibility="collapsed",
        key="chat_feed_mode",
    )
    visible_rows = [
        row for row in sorted_rows
        if feed_mode == "All messages" or row.get("sender") not in {"system", "arena"}
    ]
    recent_rows = visible_rows[:CHAT_FEED_DEFAULT_LIMIT]

    if not recent_rows:
        st.info("No messages in this view.")
        return

    if len(visible_rows) > len(recent_rows):
        st.caption(f"Showing latest {len(recent_rows)} of {len(visible_rows)} messages.")

    with st.container(border=True):
        for row in recent_rows:
            _render_chat_row(row)

    older_rows = visible_rows[CHAT_FEED_DEFAULT_LIMIT:]
    if older_rows:
        with st.expander(f"Older messages ({len(older_rows)})"):
            for row in older_rows:
                _render_chat_row(row)


def _render_chat_row(row: dict) -> None:
        sender = row.get("sender", "unknown")
        message = row.get("message", "")
        trigger_type = _format_trigger(row.get("trigger_type"))
        timestamp = format_timestamp_eastern(row.get("timestamp"), fallback=str(row.get("timestamp", "")))
        if sender in {"system", "arena"}:
            st.markdown(
                f"<div style='padding:0.5rem 0;color:#AAAAAA;font-style:italic'><span>{timestamp}</span> <strong>{sender}</strong> {message}</div>",
                unsafe_allow_html=True,
            )
            return
        color = AGENT_COLORS.get(sender, "#CCCCCC")
        badge = f"<span style='background:#333333;color:#CCCCCC;padding:0.15rem 0.4rem;border-radius:6px;font-size:0.75rem'>{trigger_type}</span>" if trigger_type else ""
        st.markdown(
            f"<div style='padding:0.6rem 0;border-bottom:1px solid #222222'><div><span style='color:#888888'>{timestamp}</span> <strong style='color:{color}'>{sender}</strong> {badge}</div><div style='margin-top:0.3rem'>{message}</div></div>",
            unsafe_allow_html=True,
        )


def _format_trigger(trigger_type: str | None) -> str:
    if not trigger_type:
        return ""
    return trigger_type.replace("_", " ").title()
