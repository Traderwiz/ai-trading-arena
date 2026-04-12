# AI TRADING ARENA — CODEX IMPLEMENTATION SPEC
## Component 6: Streamlit Public Dashboard
**Date:** April 10, 2026
**Author:** Claude (PM / Architecture Lead)
**For:** Codex (implementation agent)
**Approved by:** Greg (pending)

---

## OVERVIEW

The public-facing dashboard for the AI Trading Arena. It reads from Supabase and displays everything the audience needs to follow the competition. It does NOT write to the database. It refreshes every 60 seconds via Streamlit's auto-refresh.

**Tech stack:** Streamlit (Python)
**Data source:** Supabase (read-only, uses `arena_reader` role or the service key with SELECT-only queries)
**Deployment:** Runs on bot box (192.168.0.21), exposed via port forward or Streamlit Cloud later

---

## LAYOUT

The dashboard is a single-page app with the following sections, top to bottom:

### Section 1: Header
- Title: "AI TRADING ARENA" (large)
- Subtitle: "Big Brother meets Wall Street — AI agents trading crypto with real money"
- Competition status badge: "LIVE" (green), "PAUSED" (yellow), or "COMPLETE" (gray)
- Current phase: "Opening Chaos", "Pressure Cooker", etc. (pulled from config or derived from agent count)
- Last updated timestamp
- Mandatory disclaimer: "This is an experimental AI simulation. No trades are financial advice. For entertainment purposes only."

### Section 2: Leaderboard
The centerpiece. Large, impossible to miss.

For each active agent, display in a row/card:
- **Rank** (1st, 2nd, 3rd, 4th)
- **Agent name + display name** (e.g., "Grok — The Instigator")
- **Total equity** in USDC (large number)
- **P&L %** from $100 start — large, colored: green if positive, red if negative
- **Number of positions** currently held
- **Status indicator:** active (green dot), eliminated (red X with grayscale styling)
- **Link to agent's X account**

Eliminated agents appear at the bottom in grayscale with their final equity and finish place.

Sort by: P&L % descending (rank).

Use the `leaderboard` view from Supabase.

### Section 3: Equity Curves
Line chart showing each agent's `total_equity_usdc` over time.

- One line per agent, color-coded (assign a consistent color per agent)
- X-axis: time
- Y-axis: equity in USDC
- $100 starting line as a horizontal reference
- $10 elimination threshold as a red dashed line
- Data source: `standings` table, sampled (every Nth row if data gets large)
- Use Plotly for interactivity (hover to see exact values)

### Section 4: Portfolio Breakdown
Expandable section per agent showing current holdings.

For each active agent:
- Agent name as header
- Table of current positions from `positions` table:
  - Symbol
  - Quantity
  - Current price (USDC)
  - Current value (USDC)
  - Unrealized P&L (USDC)
- Cash (USDC) balance
- Pie chart or bar showing allocation (cash vs each position as % of total equity)

### Section 5: Recent Trades
Table of last 20 trades across all agents.

Columns:
- Timestamp
- Agent name
- Side (BUY/SELL, colored green/red)
- Symbol
- Quantity
- Price (USDC)
- Value (USDC)
- Confidence (1-10)
- BaseScan link (clickable, opens tx_hash URL: `https://basescan.org/tx/{tx_hash}`)

Data source: `trades` table, ordered by timestamp DESC, LIMIT 20.

Optional filter: by agent name.

### Section 6: Group Chat
The chat log, displayed like a messaging interface.

- Show last 50 messages from `chat_logs` table
- Each message shows: timestamp, sender name (styled per agent color), message text
- System/arena messages styled differently (gray, italic)
- Trigger type shown as a small badge (e.g., "Opening Bell", "Trade Reaction", "Roast")
- Auto-scrolls to latest
- Slight visual delay note: "Chat is displayed with a slight delay"

### Section 7: Activity Compliance
Simple status table showing each agent's activity rule compliance.

Columns:
- Agent name
- Qualifying trades this week (X/2)
- Flag status (Clear ✅, Yellow 🟡, Red 🔴)
- Flag issued date (if any)

Data source: `activity_tracking` table, current week.

### Section 8: Elimination Log
Only visible after first elimination.

For each eliminated agent:
- Agent name + finish place (4th, 3rd, 2nd)
- Final equity
- Elimination type (financial / inactivity)
- Timestamp
- Last words (from `eliminations` table)
- Fatal trade details (if financial elimination)

Data source: `eliminations` table.

### Section 9: Footer
- Links to brand social accounts (@AITradingArena)
- "Season 1 — Experiment"
- Disclaimer repeated

---

## STYLING

- **Dark theme** — use Streamlit's built-in dark mode (`[theme]` in `.streamlit/config.toml`)
- **Agent colors** — consistent across all charts and UI:
  - Grok: `#FF6B35` (orange)
  - DeepSeek: `#4ECDC4` (teal)
  - Qwen: `#7B68EE` (purple)
  - Llama: `#45B7D1` (blue)
- **P&L colors:** Green `#00C853` for positive, Red `#FF1744` for negative
- **Font:** System default (Streamlit's default is fine)
- **Layout:** Use `st.columns()` for the leaderboard cards, full-width for charts and tables

---

## DATA ACCESS

```python
# supabase_client.py

from supabase import create_client
import os

def get_client():
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_KEY"]
    )

def get_leaderboard():
    """Returns current leaderboard from the leaderboard view."""
    return client.table("leaderboard").select("*").execute()

def get_standings_history():
    """Returns standings over time for equity curves."""
    return client.table("standings").select(
        "agent_name, total_equity_usdc, timestamp"
    ).order("timestamp").execute()

def get_current_positions():
    """Returns all current positions."""
    return client.table("positions").select("*").execute()

def get_recent_trades(limit=20):
    """Returns most recent trades."""
    return client.table("trades").select("*").order(
        "timestamp", desc=True
    ).limit(limit).execute()

def get_recent_chat(limit=50):
    """Returns most recent chat messages."""
    return client.table("chat_logs").select("*").order(
        "timestamp", desc=True
    ).limit(limit).execute()

def get_activity_tracking():
    """Returns current week's activity compliance."""
    return client.table("activity_tracking").select("*").order(
        "week_start", desc=True
    ).execute()

def get_eliminations():
    """Returns all elimination records."""
    return client.table("eliminations").select("*").order(
        "timestamp"
    ).execute()

def get_agents():
    """Returns all agent metadata."""
    return client.table("agents").select("*").execute()
```

All queries are SELECT-only. The dashboard never writes.

---

## AUTO-REFRESH

```python
# At the top of the main app
import streamlit as st

st.set_page_config(
    page_title="AI Trading Arena",
    page_icon="🏟️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Auto-refresh every 60 seconds
st_autorefresh(interval=60_000, key="arena_refresh")
```

Use `streamlit-autorefresh` package: `pip install streamlit-autorefresh`

---

## FILE STRUCTURE

```
arena/dashboard/
├── app.py                      # Main Streamlit app
├── supabase_client.py          # Data access layer
├── components/
│   ├── leaderboard.py          # Leaderboard section
│   ├── equity_chart.py         # Equity curves (Plotly)
│   ├── portfolio.py            # Portfolio breakdown per agent
│   ├── trades_table.py         # Recent trades table
│   ├── chat_feed.py            # Group chat display
│   ├── activity_status.py      # Activity compliance table
│   └── elimination_log.py      # Elimination records
├── config.py                   # Agent colors, constants
├── .streamlit/
│   └── config.toml             # Theme config (dark mode)
├── requirements.txt            # streamlit, supabase, plotly, streamlit-autorefresh
└── README.md
```

---

## REQUIREMENTS

```
streamlit>=1.30.0
supabase>=2.0.0
plotly>=5.18.0
streamlit-autorefresh>=1.0.0
pandas>=2.0.0
```

---

## DEMO / EMPTY STATE

The dashboard must work gracefully when there's no data yet:
- Leaderboard shows all 4 agents at $100, 0% P&L, "pending" status
- Equity chart shows nothing (or a "Competition not yet started" message)
- Trades table shows "No trades yet"
- Chat shows "No messages yet"
- Activity tracking shows 0/2 trades, "clear" status for all

This is important because the dashboard will be deployed before the competition starts.

---

## TESTING

No unit tests needed for UI code. Manual testing:
1. Run with empty Supabase (verify empty states render)
2. Insert sample data via SQL Editor (a few standings, trades, chat messages)
3. Verify all sections populate correctly
4. Verify auto-refresh works
5. Verify BaseScan links are clickable and correct
6. Verify eliminated agents show in grayscale

---

## WHAT THIS COMPONENT DOES NOT DO

- Does NOT write to Supabase
- Does NOT require authentication (public-facing)
- Does NOT show real-time websocket updates (polling every 60s is fine for MVP)
- Does NOT include audience interaction features (deferred to Season 2)
- Does NOT produce the weekly episode (separate pipeline)

---

## DECISIONS CONFIRMED

1. **Streamlit** for MVP — quick to build, sufficient for Season 1 audience
2. **60-second polling** — not real-time, but good enough
3. **Plotly** for charts — interactive hover, good dark theme support
4. **Dark theme** — matches the Arena's aesthetic
5. **No auth** — public dashboard, view-only

---

*Estimated build time: 2-3 days. Zero external dependencies beyond Supabase read access.*
