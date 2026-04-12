# Arena Brain Loop

Files:

- [main.py](/C:/Users/gaber/projects/ai_trading_arena/arena/brain/main.py)
- [llm_client.py](/C:/Users/gaber/projects/ai_trading_arena/arena/brain/llm_client.py)
- [prompt_builder.py](/C:/Users/gaber/projects/ai_trading_arena/arena/brain/prompt_builder.py)
- [response_parser.py](/C:/Users/gaber/projects/ai_trading_arena/arena/brain/response_parser.py)
- [chat_triggers.py](/C:/Users/gaber/projects/ai_trading_arena/arena/brain/chat_triggers.py)
- [elimination.py](/C:/Users/gaber/projects/ai_trading_arena/arena/brain/elimination.py)
- [activity_tracker.py](/C:/Users/gaber/projects/ai_trading_arena/arena/brain/activity_tracker.py)
- [memory_manager.py](/C:/Users/gaber/projects/ai_trading_arena/arena/brain/memory_manager.py)
- [telegram_notifier.py](/C:/Users/gaber/projects/ai_trading_arena/arena/brain/telegram_notifier.py)
- [x_client.py](/C:/Users/gaber/projects/ai_trading_arena/arena/brain/x_client.py)
- [arena_config.yaml](/C:/Users/gaber/projects/ai_trading_arena/arena/brain/arena_config.yaml)

## What this implements

- Sequential 30-minute agent loop with randomized order each cycle
- Shared context loading from Supabase
- Prompt construction from portfolio, leaderboard, chat, trades, market snapshots, memory, activity, alerts, and trigger state
- Unified LLM routing through the OpenAI SDK
- LM Studio fallback to DeepSeek for local-model outages
- Sanity checker validation before trade/chat/social execution
- Wallet-manager execution for approved trades
- Activity tracking, elimination watch, and memory-summary hooks
- Telegram notifications and X posting
- Coinbase public-market snapshots for recent/held reference symbols
- Per-agent loop diagnostics written into `loop_log.errors.agent_diagnostics`
- LLM usage metadata written into `loop_log.token_usage` when the provider returns it

## Important persistence choices

The current schema from Components 1-2 does not define a dedicated elimination-watch table or a pending-rejections table. This implementation handles those requirements without adding schema drift:

- Elimination watch recovery is reconstructed from recent `standings` rows on startup.
- Pending rejections are read from the existing `validation_log` table.

## Integration harness

The test harness includes a mock loop run and supports live Supabase mode when credentials are available. It was only verified here in mocked mode because no Supabase credentials were present in the workspace.

## Running tests

From [arena/brain](/C:/Users/gaber/projects/ai_trading_arena/arena/brain):

```bash
python -m unittest test_response_parser.py test_chat_triggers.py test_prompt_builder.py test_activity_tracker.py test_elimination.py test_mock_loop_integration.py
```
