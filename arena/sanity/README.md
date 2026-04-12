# Arena Sanity Checker

This module implements Component 2 from the spec: validation gates for trades, chat, and social posts before execution.

Files:

- [sanity_checker.py](/C:/Users/gaber/projects/ai_trading_arena/arena/sanity/sanity_checker.py)
- [blocked_words.txt](/C:/Users/gaber/projects/ai_trading_arena/arena/sanity/blocked_words.txt)
- [test_sanity_checker.py](/C:/Users/gaber/projects/ai_trading_arena/arena/sanity/test_sanity_checker.py)

## Behavior

- Trade validation enforces side, symbol format, stablecoin buy ban, Coinbase symbol availability, quantity, holdings checks for sells, 29% sizing cap, cash sufficiency, and DEX Screener liquidity.
- Chat validation enforces non-empty content, truncation at 1000 chars, blocked words, PII detection, and freeform rate limits.
- Social validation enforces non-empty content, truncation at 280 chars, blocked words, PII detection, financial-advice triggers, and the 10-posts-per-24-hours cap.
- Validation attempts are logged to Supabase `validation_log`; if Supabase logging fails, the module falls back to a local JSONL file.

## Rate limits

Rate-limit state is read from Supabase-backed tables, not in-memory:

- Freeform chat: count rows in `chat_logs` where `trigger_type = 'freeform'`
- Social posts: count rows in `social_posts`

Mandatory chat triggers bypass rate limits, per spec.

## Caching

- Coinbase symbol list: cached for 24 hours
- DEX Screener liquidity: cached per symbol for 5 minutes
- Blocked words: loaded at startup and reloaded on `SIGHUP` where supported

## Assumption carried from the spec

The trade rules require an estimated buy cost but the spec does not define the exact price endpoint. This implementation uses a Coinbase spot-price lookup for symbols not already present in `wallet_state["positions"]`. If that lookup fails, the trade is rejected.

## Usage

```python
from sanity_checker import SanityChecker

checker = SanityChecker(supabase_client=my_supabase_client)

trade_result = checker.validate_trade("grok", trade, wallet_state)
chat_result = checker.validate_chat("grok", "DeepSeek blinked first.", {"trigger_type": "freeform"})
social_result = checker.validate_social("grok", "ETH held support. DeepSeek did not.")
```

Config keys supported by `SanityChecker(...)`:

- `blocked_words_path`
- `tradeable_symbols_cache_ttl`
- `liquidity_cache_ttl`
- `min_liquidity_usd`
- `max_trade_percent`
- `validation_log_path`

For testing or custom integrations, you can also inject:

- `symbol_provider`
- `price_provider`
- `liquidity_provider`
- `now_provider`

## Running tests

From [arena/sanity](/C:/Users/gaber/projects/ai_trading_arena/arena/sanity):

```bash
python -m unittest test_sanity_checker.py
```
