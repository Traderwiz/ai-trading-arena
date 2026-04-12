# AI TRADING ARENA — CODEX IMPLEMENTATION SPEC
## Components 1 & 2: Supabase Schema + Sanity Checker
**Date:** April 9, 2026
**Author:** Claude (PM / Architecture Lead)
**For:** Codex (implementation agent)
**Approved by:** Greg (pending)

---

## OVERVIEW

This spec covers the first two buildable components of the AI Trading Arena. They have zero external dependencies and can be built immediately.

- **Component 1: Supabase Database Schema** — the central data store everything writes to
- **Component 2: Sanity Checker** — the Python validation layer between LLM output and trade/social execution

Both components must be production-ready before the Arena "Brain" Loop (Component 3) can begin.

---

## COMPONENT 1: SUPABASE DATABASE SCHEMA

### 1.1 Purpose

Central data store for the entire Arena. Every agent loop writes here. The dashboard reads from here. Episode production queries here. This is the single source of truth for competition state.

### 1.2 Tables

#### `agents`
Tracks agent metadata and current status. Static after setup, except `status`.

```sql
CREATE TABLE agents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_name TEXT NOT NULL UNIQUE,          -- 'grok', 'deepseek', 'qwen', 'llama'
    display_name TEXT NOT NULL,               -- 'Grok', 'DeepSeek', 'Qwen', 'Llama'
    provider TEXT NOT NULL,                   -- 'xai', 'deepseek', 'alibaba', 'meta'
    execution_type TEXT NOT NULL,             -- 'api' or 'local'
    wallet_address TEXT,                      -- Coinbase CDP wallet address on Base
    x_handle TEXT,                            -- '@GrokArena' etc.
    status TEXT NOT NULL DEFAULT 'pending',   -- 'pending', 'active', 'eliminated', 'inactive'
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    eliminated_at TIMESTAMPTZ
);
```

#### `standings`
Snapshot of each agent's financial state, written every agent loop (~30 min).

```sql
CREATE TABLE standings (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    agent_name TEXT NOT NULL REFERENCES agents(agent_name),
    total_equity_usdc NUMERIC(12,4) NOT NULL,  -- total wallet value in USDC
    cash_usdc NUMERIC(12,4) NOT NULL,          -- USDC balance (uninvested)
    invested_usdc NUMERIC(12,4) NOT NULL,      -- value of non-USDC positions
    pnl_percent NUMERIC(8,4) NOT NULL,         -- % change from $100 starting capital
    num_positions INTEGER NOT NULL DEFAULT 0,
    loop_number INTEGER NOT NULL               -- monotonically increasing loop counter
);

CREATE INDEX idx_standings_agent_time ON standings(agent_name, timestamp DESC);
CREATE INDEX idx_standings_loop ON standings(loop_number);
```

#### `positions`
Current holdings per agent, updated every loop. This is a snapshot table — old rows are overwritten each loop via upsert or delete+insert.

```sql
CREATE TABLE positions (
    id BIGSERIAL PRIMARY KEY,
    agent_name TEXT NOT NULL REFERENCES agents(agent_name),
    symbol TEXT NOT NULL,                      -- token symbol e.g. 'ETH', 'SOL'
    quantity NUMERIC(18,8) NOT NULL,
    avg_entry_price_usdc NUMERIC(18,8),
    current_price_usdc NUMERIC(18,8),
    current_value_usdc NUMERIC(12,4),
    unrealized_pnl_usdc NUMERIC(12,4),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(agent_name, symbol)
);
```

#### `trades`
Every executed trade. Immutable append-only log.

```sql
CREATE TABLE trades (
    id BIGSERIAL PRIMARY KEY,
    agent_name TEXT NOT NULL REFERENCES agents(agent_name),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    symbol TEXT NOT NULL,                      -- e.g. 'ETH', 'SOL', 'PEPE'
    side TEXT NOT NULL CHECK (side IN ('buy', 'sell')),
    quantity NUMERIC(18,8) NOT NULL,
    price_usdc NUMERIC(18,8) NOT NULL,        -- execution price in USDC
    usdc_value NUMERIC(12,4) NOT NULL,        -- total trade value in USDC
    fee_usdc NUMERIC(10,6) DEFAULT 0,
    tx_hash TEXT,                              -- BaseScan transaction hash
    loop_number INTEGER NOT NULL,
    pre_trade_equity_usdc NUMERIC(12,4),      -- equity before this trade
    post_trade_equity_usdc NUMERIC(12,4),     -- equity after this trade
    reasoning TEXT,                            -- agent's stated reason (from LLM output)
    confidence INTEGER CHECK (confidence BETWEEN 1 AND 10)  -- agent's self-rated confidence
);

CREATE INDEX idx_trades_agent_time ON trades(agent_name, timestamp DESC);
CREATE INDEX idx_trades_symbol ON trades(symbol);
```

#### `chat_logs`
All group chat messages — mandatory triggers + freeform.

```sql
CREATE TABLE chat_logs (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sender TEXT NOT NULL,                     -- agent_name or 'system' or 'arena'
    message TEXT NOT NULL,
    trigger_type TEXT,                        -- 'opening_bell', 'closing_bell', 'trade_reaction',
                                             -- 'big_move', 'roast', 'prediction', 'confessional',
                                             -- 'elimination_reaction', 'freeform', NULL
    loop_number INTEGER,
    in_reply_to BIGINT REFERENCES chat_logs(id),
    metadata JSONB                           -- flexible field for trigger context
);

CREATE INDEX idx_chat_time ON chat_logs(timestamp DESC);
CREATE INDEX idx_chat_sender ON chat_logs(sender);
```

#### `social_posts`
All X posts by agent accounts + brand account.

```sql
CREATE TABLE social_posts (
    id BIGSERIAL PRIMARY KEY,
    agent_name TEXT NOT NULL,                 -- agent_name or 'brand'
    platform TEXT NOT NULL DEFAULT 'x',       -- 'x', 'instagram', 'tiktok', 'youtube'
    content TEXT NOT NULL,
    posted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    x_post_id TEXT,                           -- X's post ID after publishing
    status TEXT NOT NULL DEFAULT 'pending',   -- 'pending', 'posted', 'blocked', 'deleted'
    blocked_reason TEXT,                      -- if content filter rejected it
    loop_number INTEGER
);

CREATE INDEX idx_social_agent ON social_posts(agent_name, posted_at DESC);
```

#### `eliminations`
One row per eliminated agent. Created by the elimination trigger.

```sql
CREATE TABLE eliminations (
    id BIGSERIAL PRIMARY KEY,
    agent_name TEXT NOT NULL REFERENCES agents(agent_name) UNIQUE,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    final_equity_usdc NUMERIC(12,4) NOT NULL,
    elimination_type TEXT NOT NULL,           -- 'financial' or 'inactivity'
    fatal_trade_id BIGINT REFERENCES trades(id),
    last_words TEXT,                          -- agent's final chat message
    final_x_post TEXT,                       -- agent's final X post
    final_positions JSONB,                   -- snapshot of positions at elimination
    loops_below_threshold INTEGER,           -- how many consecutive loops below $10
    finish_place INTEGER                     -- 4th, 3rd, 2nd (1st never gets eliminated)
);
```

#### `activity_tracking`
Tracks compliance with the 2-trades-per-week minimum.

```sql
CREATE TABLE activity_tracking (
    id BIGSERIAL PRIMARY KEY,
    agent_name TEXT NOT NULL REFERENCES agents(agent_name),
    week_start DATE NOT NULL,                -- Monday of the calendar week
    qualifying_trades INTEGER NOT NULL DEFAULT 0,
    daily_chats_completed INTEGER NOT NULL DEFAULT 0,
    flag_status TEXT DEFAULT 'clear',        -- 'clear', 'yellow', 'red', 'eliminated'
    flag_issued_at TIMESTAMPTZ,
    UNIQUE(agent_name, week_start)
);
```

#### `loop_log`
Meta-log of every orchestration loop. For debugging and monitoring.

```sql
CREATE TABLE loop_log (
    id BIGSERIAL PRIMARY KEY,
    loop_number INTEGER NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    agents_processed TEXT[],                 -- which agents ran this loop
    errors JSONB,                            -- any errors encountered
    token_usage JSONB                        -- token counts per agent for cost tracking
);

CREATE INDEX idx_loop_number ON loop_log(loop_number);
```

#### `memory_summaries`
Stores the Tier 2 (daily) and Tier 3 (weekly) memory summaries.

```sql
CREATE TABLE memory_summaries (
    id BIGSERIAL PRIMARY KEY,
    agent_name TEXT NOT NULL REFERENCES agents(agent_name),
    summary_type TEXT NOT NULL CHECK (summary_type IN ('daily', 'weekly')),
    period_start TIMESTAMPTZ NOT NULL,
    period_end TIMESTAMPTZ NOT NULL,
    content TEXT NOT NULL,                   -- the summary text
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_memory_agent_type ON memory_summaries(agent_name, summary_type, period_end DESC);
```

### 1.3 Views

#### `current_standings`
Latest snapshot per agent. Used by the dashboard and the agent input builder.

```sql
CREATE VIEW current_standings AS
SELECT DISTINCT ON (agent_name)
    agent_name, total_equity_usdc, cash_usdc, invested_usdc, pnl_percent, num_positions, timestamp, loop_number
FROM standings
ORDER BY agent_name, timestamp DESC;
```

#### `leaderboard`
Ranked by P&L percentage. Used in agent context and dashboard.

```sql
CREATE VIEW leaderboard AS
SELECT
    cs.agent_name,
    a.display_name,
    a.status,
    cs.total_equity_usdc,
    cs.pnl_percent,
    cs.num_positions,
    cs.timestamp AS last_updated,
    RANK() OVER (ORDER BY cs.pnl_percent DESC) AS rank
FROM current_standings cs
JOIN agents a ON cs.agent_name = a.agent_name
WHERE a.status IN ('active', 'eliminated')
ORDER BY rank;
```

### 1.4 Row-Level Security

Enable RLS on all tables. For MVP, create two roles:

- `arena_writer` — used by the bot box orchestration loop. Full read/write on all tables.
- `arena_reader` — used by the Streamlit dashboard. Read-only on all tables.

```sql
-- Enable RLS
ALTER TABLE agents ENABLE ROW LEVEL SECURITY;
ALTER TABLE standings ENABLE ROW LEVEL SECURITY;
-- (repeat for all tables)

-- Writer policy (bot box)
CREATE POLICY writer_all ON agents FOR ALL TO arena_writer USING (true) WITH CHECK (true);
-- (repeat for all tables)

-- Reader policy (dashboard)
CREATE POLICY reader_select ON agents FOR SELECT TO arena_reader USING (true);
-- (repeat for all tables)
```

### 1.5 Deliverables

1. SQL migration file that creates all tables, indexes, views, and RLS policies
2. Seed script that inserts the 4 agents into the `agents` table
3. README with Supabase project setup instructions (connection string, role creation)

### 1.6 Testing

- Run migration against a fresh Supabase project
- Insert sample data for 2 agents across all tables
- Verify views return correct results
- Verify RLS blocks `arena_reader` from writing

---

## COMPONENT 2: SANITY CHECKER

### 2.1 Purpose

The sanity checker is the safety layer between the LLM's structured JSON output and actual execution (trade, chat, social). It validates, rejects, or modifies agent actions before they touch the blockchain or X API. Nothing gets executed without passing through this layer.

### 2.2 Architecture

Single Python module: `sanity_checker.py`

Three public functions:
- `validate_trade(agent_name, trade, wallet_state) → TradeResult`
- `validate_chat(agent_name, message, context) → ChatResult`
- `validate_social(agent_name, post) → SocialResult`

### 2.3 Trade Validation

#### Input: `trade` dict from LLM output
```python
{
    "symbol": "ETH",
    "side": "buy",        # "buy" or "sell"
    "quantity": 0.015,
    "reasoning": "ETH showing strength after...",
    "confidence": 7
}
```

#### Input: `wallet_state` dict from Coinbase API
```python
{
    "agent_name": "grok",
    "cash_usdc": 74.50,
    "total_equity_usdc": 92.30,
    "positions": {
        "ETH": {"quantity": 0.005, "current_price_usdc": 3200.00, "value_usdc": 16.00},
        "SOL": {"quantity": 0.12, "current_price_usdc": 15.00, "value_usdc": 1.80}
    }
}
```

#### Validation Rules (applied in order, fail on first rejection)

| # | Rule | Check | On Failure |
|---|------|-------|------------|
| 1 | **Valid side** | `side` is `"buy"` or `"sell"` | Reject: "Invalid trade side" |
| 2 | **Valid symbol** | `symbol` is a non-empty string, alphanumeric + hyphens only, max 20 chars | Reject: "Invalid symbol format" |
| 3 | **Not stablecoin buy** | If `side == "buy"`, symbol is not in `STABLECOINS` list | Reject: "Cannot buy stablecoins — USDC is cash" |
| 4 | **Ticker exists** | Symbol is available on Coinbase Trade API (cache the list, refresh daily) | Reject: "Symbol {symbol} not available on Coinbase" |
| 5 | **Positive quantity** | `quantity > 0` | Reject: "Quantity must be positive" |
| 6 | **Sell: has position** | If `side == "sell"`, agent holds the symbol | Reject: "No position in {symbol} to sell" |
| 7 | **Sell: has enough** | If `side == "sell"`, `quantity <= held quantity` | Reject: "Insufficient {symbol} — holding {held}, trying to sell {quantity}" |
| 8 | **Buy: estimate cost** | `estimated_cost = quantity × current_price_usdc` | (computation step, not a check) |
| 9 | **Buy: within 29% cap** | `estimated_cost <= wallet_state.total_equity_usdc × 0.29` | Reject: "Trade exceeds 29% cap — max ${cap}, trade costs ~${cost}" |
| 10 | **Buy: sufficient cash** | `estimated_cost <= wallet_state.cash_usdc` | Reject: "Insufficient cash — have ${cash}, need ~${cost}" |
| 11 | **Liquidity check** | Query DEX Screener API: token liquidity >= $100,000 | Reject: "Insufficient liquidity for {symbol} — ${liquidity} < $100K minimum" |

#### Output: `TradeResult`
```python
@dataclass
class TradeResult:
    approved: bool
    trade: dict | None         # the validated trade dict (passed through unchanged if approved)
    rejection_reason: str | None
    warnings: list[str]        # non-blocking warnings (e.g. "liquidity close to minimum")
```

#### Constants
```python
STABLECOINS = {"USDC", "USDT", "DAI", "BUSD", "TUSD", "USDP", "GUSD", "FRAX", "LUSD", "PYUSD"}
MAX_TRADE_PERCENT = 0.29       # 29% cap (buffer below 30% rule)
MIN_LIQUIDITY_USD = 100_000    # $100K minimum liquidity
SYMBOL_MAX_LENGTH = 20
```

### 2.4 Chat Validation

#### Input: `message` string from LLM output

#### Validation Rules

| # | Rule | Check | On Failure |
|---|------|-------|------------|
| 1 | **Not empty** | Message is non-empty after stripping whitespace | Reject: "Empty chat message" |
| 2 | **Length limit** | `len(message) <= 1000` characters | Truncate to 1000 chars + append "[truncated]" |
| 3 | **No slurs** | Message does not contain words from `BLOCKED_WORDS` list | Reject: "Chat blocked — content policy violation" |
| 4 | **No PII patterns** | No phone numbers, emails, wallet addresses (regex) | Reject: "Chat blocked — contains PII" |
| 5 | **Rate limit** | Agent has not exceeded 3 freeform posts in 15 minutes or 12 freeform posts today | Reject: "Chat rate limit exceeded" |

#### Output: `ChatResult`
```python
@dataclass
class ChatResult:
    approved: bool
    message: str | None        # the message (possibly truncated)
    rejection_reason: str | None
```

#### Notes on `BLOCKED_WORDS`
- Start with a standard list of slurs and hate speech terms
- Keep the list in a separate file (`blocked_words.txt`) for easy updates
- Matching should be case-insensitive, whole-word only (avoid false positives on substrings)
- This is a safety net, not a personality filter — agent trash talk is encouraged, slurs are not

### 2.5 Social Post Validation

#### Input: `post` string from LLM output

#### Validation Rules

| # | Rule | Check | On Failure |
|---|------|-------|------------|
| 1 | **Not empty** | Post is non-empty after stripping whitespace | Reject: "Empty social post" |
| 2 | **Length limit** | `len(post) <= 280` characters | Truncate to 277 chars + "..." |
| 3 | **No slurs** | Same as chat check | Reject: "Post blocked — content policy violation" |
| 4 | **No PII patterns** | Same as chat check | Reject: "Post blocked — contains PII" |
| 5 | **No financial advice language** | Post does not contain phrases like "you should buy", "guaranteed returns", "not financial advice" (ironic usage), "invest in" directed at audience | Reject: "Post blocked — potential financial advice trigger" |
| 6 | **Disclaimer present** | Not checked per-post — the disclaimer is in the X bio, not in every post | (no check) |
| 7 | **Rate limit** | Agent has not posted more than 10 X posts in 24 hours | Reject: "Social post rate limit exceeded" |

#### Financial Advice Patterns
```python
FINANCIAL_ADVICE_PATTERNS = [
    r"\byou should (buy|sell|invest)",
    r"\bguaranteed (returns|profit|gains)",
    r"\bbuy now\b",
    r"\bdon'?t miss (out|this)",
    r"\bto the moon\b",              # borderline — include for Season 1 caution
    r"\bnot financial advice\b",      # ironic usage is still a regulatory flag
]
```
These are regex patterns, matched case-insensitive. This list will be tuned during the pilot.

#### Output: `SocialResult`
```python
@dataclass
class SocialResult:
    approved: bool
    post: str | None            # the post (possibly truncated)
    rejection_reason: str | None
```

### 2.6 Shared Utilities

#### Logging
Every validation call logs to Supabase (or local file for pre-Supabase testing):
```python
def log_validation(agent_name: str, validation_type: str, approved: bool, 
                   input_data: dict, result: dict, rejection_reason: str | None):
    # Write to a `validation_log` table or structured log file
    pass
```

Add a `validation_log` table to Supabase:
```sql
CREATE TABLE validation_log (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    agent_name TEXT NOT NULL,
    validation_type TEXT NOT NULL,   -- 'trade', 'chat', 'social'
    approved BOOLEAN NOT NULL,
    input_data JSONB NOT NULL,
    rejection_reason TEXT,
    warnings TEXT[]
);
```

#### Caching
- Coinbase tradeable symbols list: cache locally, refresh every 24 hours
- DEX Screener liquidity data: cache per-symbol for 5 minutes (avoid hammering the API)
- Blocked words list: load once at startup, reload on SIGHUP

### 2.7 External Dependencies

| Dependency | Purpose | Fallback |
|------------|---------|----------|
| Coinbase Trade API | Tradeable symbol list | Reject trade with "unable to verify symbol" |
| DEX Screener API | Liquidity check | Reject trade with "unable to verify liquidity" |
| Supabase | Validation logging | Log to local file, sync later |

If any external dependency is unavailable, the sanity checker **fails closed** — it rejects the trade rather than allowing an unvalidated trade through.

### 2.8 Module Interface

```python
# sanity_checker.py

class SanityChecker:
    def __init__(self, supabase_client=None, config: dict = None):
        """
        config keys:
            - blocked_words_path: str (default: './blocked_words.txt')
            - tradeable_symbols_cache_ttl: int (seconds, default: 86400)
            - liquidity_cache_ttl: int (seconds, default: 300)
            - min_liquidity_usd: int (default: 100000)
            - max_trade_percent: float (default: 0.29)
        """
    
    def validate_trade(self, agent_name: str, trade: dict, wallet_state: dict) -> TradeResult:
        """Validate a proposed trade. Returns TradeResult."""
    
    def validate_chat(self, agent_name: str, message: str, context: dict = None) -> ChatResult:
        """Validate a chat message. context includes trigger_type and rate limit state."""
    
    def validate_social(self, agent_name: str, post: str) -> SocialResult:
        """Validate a social media post. Returns SocialResult."""
    
    def refresh_symbol_cache(self) -> None:
        """Force refresh the tradeable symbols list from Coinbase."""
    
    def get_rate_limit_state(self, agent_name: str) -> dict:
        """Return current rate limit counters for an agent."""
```

### 2.9 Deliverables

1. `sanity_checker.py` — the module with all three validation functions
2. `blocked_words.txt` — initial blocked words list
3. `test_sanity_checker.py` — comprehensive unit tests (see 2.10)
4. `README.md` — usage examples and configuration

### 2.10 Test Cases

#### Trade Validation Tests
```
test_valid_buy — standard buy within all limits → approved
test_valid_sell — sell existing position → approved
test_sell_full_position — sell entire holding → approved
test_invalid_side — side="short" → rejected
test_empty_symbol — symbol="" → rejected
test_stablecoin_buy — buy USDT → rejected
test_exceeds_29_percent_cap — buy worth 35% of equity → rejected
test_exactly_29_percent — buy worth exactly 29% of equity → approved
test_insufficient_cash — buy costs more than cash balance → rejected
test_sell_no_position — sell ETH when holding none → rejected
test_sell_more_than_held — sell 1.0 ETH when holding 0.5 → rejected
test_low_liquidity — token with $50K liquidity → rejected
test_hallucinated_ticker — symbol="FAKECOIN123" → rejected
test_negative_quantity — quantity=-5 → rejected
test_zero_quantity — quantity=0 → rejected
```

#### Chat Validation Tests
```
test_valid_message — normal message → approved
test_empty_message — "" → rejected
test_long_message — 1500 chars → truncated to 1000
test_blocked_word — contains slur → rejected
test_pii_email — contains email address → rejected
test_pii_phone — contains phone number → rejected
test_rate_limit_15min — 4th freeform in 15 minutes → rejected
test_rate_limit_daily — 13th freeform in day → rejected
test_mandatory_not_rate_limited — mandatory trigger posts bypass rate limits → approved
```

#### Social Post Validation Tests
```
test_valid_post — normal post → approved
test_empty_post — "" → rejected
test_long_post — 300 chars → truncated to 280
test_blocked_word — contains slur → rejected
test_financial_advice — "you should buy ETH" → rejected
test_not_financial_advice_disclaimer — "not financial advice" → rejected
test_rate_limit — 11th post in 24 hours → rejected
test_trash_talk_ok — "DeepSeek's portfolio is a dumpster fire" → approved
test_insult_ok — "Qwen trades like a blindfolded raccoon" → approved
```

### 2.11 What This Module Does NOT Do

- **Does not execute trades** — it validates and returns a result. The Brain Loop handles execution.
- **Does not query wallet state** — it receives wallet state as input. The Brain Loop fetches it.
- **Does not manage agent state** — it is stateless except for caches and rate limit counters.
- **Does not filter personality** — trash talk, insults, and aggressive language are allowed. Only slurs, PII, and regulatory triggers are blocked.

---

## INTEGRATION NOTES

### How These Components Connect to Component 3 (Brain Loop)

```
Brain Loop (Component 3)
    │
    ├── Fetches wallet state from Coinbase API
    ├── Fetches market data from Coinbase API
    ├── Reads arena context from Supabase (Component 1)
    ├── Calls LLM with structured prompt
    ├── Receives structured JSON output from LLM
    │
    ├── Passes trade to SanityChecker.validate_trade() (Component 2)
    │   ├── If approved → execute via Coinbase Agent Kit → log to Supabase
    │   └── If rejected → log rejection → inform agent on next loop
    │
    ├── Passes chat to SanityChecker.validate_chat() (Component 2)
    │   ├── If approved → write to chat_logs in Supabase
    │   └── If rejected → log rejection
    │
    └── Passes social to SanityChecker.validate_social() (Component 2)
        ├── If approved → post to X API → log to Supabase
        └── If rejected → log rejection
```

### File Structure (proposed)
```
arena/
├── db/
│   ├── migrations/
│   │   └── 001_initial_schema.sql
│   ├── seeds/
│   │   └── agents.sql
│   └── README.md
├── sanity/
│   ├── sanity_checker.py
│   ├── blocked_words.txt
│   ├── test_sanity_checker.py
│   └── README.md
├── brain/                          # Component 3 (future)
├── social/                         # Component 5 (future)
├── dashboard/                      # Component 6 (future)
└── README.md
```

---

## DECISIONS (Confirmed by Greg — April 9, 2026)

1. **Supabase region:** US East (Virginia) — `us-east-1`
2. **Rate limit counters:** Stored in Supabase (durable, survives bot box restarts)
3. **Blocked words list:** Codex uses a standard list; Greg reviews during the 2-agent pilot

---

*This spec is approved. Components 1 and 2 can be built in parallel — estimated 2 days total.*
