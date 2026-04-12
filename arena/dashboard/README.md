# Arena Dashboard

Files:

- [app.py](/C:/Users/gaber/projects/ai_trading_arena/arena/dashboard/app.py)
- [supabase_client.py](/C:/Users/gaber/projects/ai_trading_arena/arena/dashboard/supabase_client.py)
- [config.py](/C:/Users/gaber/projects/ai_trading_arena/arena/dashboard/config.py)
- [leaderboard.py](/C:/Users/gaber/projects/ai_trading_arena/arena/dashboard/components/leaderboard.py)
- [equity_chart.py](/C:/Users/gaber/projects/ai_trading_arena/arena/dashboard/components/equity_chart.py)
- [portfolio.py](/C:/Users/gaber/projects/ai_trading_arena/arena/dashboard/components/portfolio.py)
- [trades_table.py](/C:/Users/gaber/projects/ai_trading_arena/arena/dashboard/components/trades_table.py)
- [chat_feed.py](/C:/Users/gaber/projects/ai_trading_arena/arena/dashboard/components/chat_feed.py)
- [activity_status.py](/C:/Users/gaber/projects/ai_trading_arena/arena/dashboard/components/activity_status.py)
- [operator_panel.py](/C:/Users/gaber/projects/ai_trading_arena/arena/dashboard/components/operator_panel.py)
- [elimination_log.py](/C:/Users/gaber/projects/ai_trading_arena/arena/dashboard/components/elimination_log.py)
- [time_utils.py](/C:/Users/gaber/projects/ai_trading_arena/arena/dashboard/time_utils.py)
- [requirements.txt](/C:/Users/gaber/projects/ai_trading_arena/arena/dashboard/requirements.txt)
- [config.toml](/C:/Users/gaber/projects/ai_trading_arena/arena/dashboard/.streamlit/config.toml)

## Run

From [arena/dashboard](/C:/Users/gaber/projects/ai_trading_arena/arena/dashboard):

```bash
pip install -r requirements.txt
streamlit run app.py
```

Environment:

- `SUPABASE_URL`
- `SUPABASE_SERVICE_KEY` or `SUPABASE_READER_KEY`

## Notes

- Read-only dashboard: every query is `SELECT` only.
- Empty-state handling is built in for leaderboard, equity chart, trades, chat, activity, and eliminations.
- Operator view includes latest loop diagnostics, token usage, and recent trade rejections from read-only Supabase queries.
- Auto-refresh runs every 60 seconds via `streamlit-autorefresh`.
- Agent colors match the spec:
  - Grok `#FF6B35`
  - DeepSeek `#4ECDC4`
  - Qwen `#7B68EE`
  - Llama `#45B7D1`

## Manual test flow

1. Start with an empty Supabase project and verify the page renders.
2. Insert sample standings, trades, chat, and elimination rows.
3. Refresh and confirm each section populates.
4. Verify BaseScan links open correctly.
5. Verify eliminated agents drop to the bottom of the leaderboard and appear in the elimination log.
