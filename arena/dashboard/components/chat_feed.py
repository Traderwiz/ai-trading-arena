from __future__ import annotations

import streamlit as st

from arena.dashboard.config import AGENT_COLORS


def render_chat(chat_rows: list[dict]) -> None:
    st.subheader("Group Chat")
    st.caption("Chat is displayed with a slight delay.")
    if not chat_rows:
        st.info("No messages yet.")
        return

    for row in reversed(chat_rows):
        sender = row.get("sender", "unknown")
        message = row.get("message", "")
        trigger_type = _format_trigger(row.get("trigger_type"))
        timestamp = row.get("timestamp", "")
        if sender in {"system", "arena"}:
            st.markdown(
                f"<div style='padding:0.5rem 0;color:#AAAAAA;font-style:italic'><span>{timestamp}</span> <strong>{sender}</strong> {message}</div>",
                unsafe_allow_html=True,
            )
            continue
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
