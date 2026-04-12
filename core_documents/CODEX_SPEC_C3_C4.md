# AI TRADING ARENA — CODEX IMPLEMENTATION SPEC
## Components 3 & 4: CDP Wallet Integration + Arena Brain Loop
**Date:** April 9, 2026
**Author:** Claude (PM / Architecture Lead)
**For:** Codex (implementation agent)
**Approved by:** Greg (pending)

---

## OVERVIEW

This spec covers the core engine of the Arena:

- **Component 3: CDP Wallet Integration** — Coinbase Agentic Wallet setup, balance queries, trade execution, and transaction logging
- **Component 4: Arena Brain Loop** — the 30-minute orchestration cycle that drives the entire competition: fetch state → build prompt → call LLM → validate → execute → log

These components depend on Components 1 (Supabase) and 2 (Sanity Checker) being complete.

**Reference documents:** `PROJECT_BIBLE_v2.md` (Sections 2, 4, 6, 7), `CODEX_SPEC_C1_C2.md` (schema and sanity checker interfaces)

---

## COMPONENT 3: CDP WALLET INTEGRATION

### 3.1 Purpose

Abstraction layer for all Coinbase wallet operations. The Brain Loop never touches Coinbase directly — it calls this module. This keeps wallet logic isolated and testable.

### 3.2 SDK

```bash
pip install coinbase-agentkit
```

Python 3.10+. Uses `CdpWalletProvider` with CDP API credentials. Network: `base-mainnet`.

### 3.3 Architecture

**Key design decision:** We are NOT using AgentKit's LangChain/framework integration. AgentKit is used only as a wallet operations library. The Brain Loop calls LLMs directly (via OpenAI SDK) and uses this module only for wallet reads and trade execution.

### 3.4 Wallet Manager Class

```python
# wallet_manager.py

class WalletManager:
    """Manages 4 Coinbase Agentic Wallets on Base."""

    def __init__(self, config: dict):
        """
        config keys:
            - cdp_api_key_id: str
            - cdp_api_key_secret: str
            - network_id: str (default: 'base-mainnet')
            - wallets: dict mapping agent_name → wallet_id or wallet_address
        """

    def get_wallet_state(self, agent_name: str) -> WalletState:
        """
        Returns current wallet state for an agent.
        Used as input to the Brain Loop prompt and sanity checker.
        """

    def execute_trade(self, agent_name: str, trade: dict) -> TradeExecution:
        """
        Executes a validated trade (already passed sanity checker).
        Returns execution result with tx_hash.
        """

    def get_portfolio_value(self, agent_name: str) -> float:
        """
        Returns total wallet value in USDC equivalent.
        Used for elimination checks and standings updates.
        """

    def liquidate_all(self, agent_name: str) -> list[TradeExecution]:
        """
        Sells all non-USDC positions. Used during elimination.
        """
```

### 3.5 Data Structures

```python
@dataclass
class WalletState:
    agent_name: str
    cash_usdc: float                    # USDC balance
    total_equity_usdc: float            # total wallet value in USDC
    positions: dict[str, Position]      # symbol → Position
    timestamp: datetime

@dataclass
class Position:
    symbol: str
    quantity: float
    current_price_usdc: float
    value_usdc: float

@dataclass
class TradeExecution:
    success: bool
    agent_name: str
    symbol: str
    side: str                           # 'buy' or 'sell'
    quantity: float
    price_usdc: float
    usdc_value: float
    fee_usdc: float
    tx_hash: str | None                 # BaseScan transaction hash
    error: str | None                   # if success=False
```

### 3.6 Token Pricing

The wallet manager needs to convert all positions to USDC equivalent. Use Coinbase's pricing API (included in AgentKit) for tokens in the Coinbase Trade API. This is the same source of truth the agents see.

### 3.7 Trade Execution Flow

```
Brain Loop calls execute_trade(agent_name, validated_trade)
    │
    ├── Map trade dict to AgentKit swap call
    │   ├── Buy: swap USDC → target token
    │   └── Sell: swap target token → USDC
    │
    ├── Execute via AgentKit wallet provider
    │   └── On-chain swap on Base via 0x router
    │
    ├── Wait for confirmation (tx_hash)
    │
    ├── Return TradeExecution result
    │   ├── success=True: includes tx_hash, actual price, fees
    │   └── success=False: includes error message
    │
    └── Brain Loop logs result to Supabase `trades` table
```

### 3.8 Error Handling

| Error | Behavior |
|-------|----------|
| RPC failure | Retry 3x with exponential backoff (1s, 3s, 9s), then return success=False |
| Swap failure / high slippage | Return success=False with "High Slippage" error |
| Insufficient balance (post-validation) | Return success=False — race condition between validation and execution |
| Network timeout | Retry 3x, then return success=False |
| Invalid token | Should never reach here (sanity checker catches it), but return success=False |

### 3.9 Deliverables

1. `arena/wallet/wallet_manager.py` — the module
2. `arena/wallet/test_wallet_manager.py` — unit tests (mock AgentKit calls)
3. `arena/wallet/README.md` — setup instructions (CDP credentials, wallet IDs)

### 3.10 Testing Notes

For unit tests, mock all AgentKit calls. Real integration testing happens in the 2-agent pilot (Component 7).

For the pilot, use real wallets with $10 USDC each. Do NOT use testnet — Base mainnet USDC is cheap enough and we need to verify real execution.

---

## COMPONENT 4: ARENA BRAIN LOOP

### 4.1 Purpose

The Brain Loop is the central orchestration engine. It runs every 30 minutes, 24/7. For each active agent, it: gathers inputs, builds the prompt, calls the LLM, parses the response, validates through the sanity checker, executes approved actions, and logs everything.

This is the most complex component. Get it right and the show runs itself.

### 4.2 Loop Architecture

```
Every 30 minutes:
    │
    ├── 1. Pre-loop checks
    │   ├── Check which agents are active (status='active')
    │   ├── Increment loop counter
    │   ├── Log loop start to loop_log table
    │   └── Determine active chat triggers for this loop
    │
    ├── 2. Gather shared context (once per loop, shared by all agents)
    │   ├── Fetch current leaderboard from Supabase
    │   ├── Fetch last 20 chat messages from Supabase
    │   ├── Fetch last 10 trades (all agents) from Supabase
    │   └── Fetch any system alerts (activity warnings, elimination proximity)
    │
    ├── 3. For each active agent (sequential, not parallel):
    │   │
    │   ├── 3a. Fetch agent-specific state
    │   │   ├── Wallet state via WalletManager.get_wallet_state()
    │   │   ├── Agent's memory (latest daily + weekly summary)
    │   │   ├── Agent's activity tracking (trades this week, flag status)
    │   │   └── Agent's pending rejections from last loop (if any)
    │   │
    │   ├── 3b. Build prompt
    │   │   ├── System prompt (personality + rules + output format)
    │   │   └── User prompt (market data + portfolio + arena context + memory + alerts)
    │   │
    │   ├── 3c. Call LLM
    │   │   ├── Route to correct provider (xAI, DeepSeek, LM Studio)
    │   │   ├── Parse structured JSON response
    │   │   └── Handle parse failures (retry once, then skip agent this loop)
    │   │
    │   ├── 3d. Validate outputs
    │   │   ├── Trade → SanityChecker.validate_trade()
    │   │   ├── Chat → SanityChecker.validate_chat()
    │   │   └── Social → SanityChecker.validate_social()
    │   │
    │   ├── 3e. Execute approved actions
    │   │   ├── Trade → WalletManager.execute_trade() → log to `trades` table
    │   │   ├── Chat → write to `chat_logs` table
    │   │   └── Social → post to X API → log to `social_posts` table
    │   │
    │   ├── 3f. Update state
    │   │   ├── Write standings snapshot to `standings` table
    │   │   ├── Update `positions` table
    │   │   ├── Update `activity_tracking` table
    │   │   └── Check elimination condition ($10 threshold)
    │   │
    │   └── 3g. Send Telegram notification (trade executions + social posts)
    │
    ├── 4. Post-loop checks
    │   ├── Elimination check: any agent below $10 for 2 consecutive loops?
    │   │   └── If yes → trigger elimination sequence
    │   ├── Activity check: end of calendar week? Update activity compliance
    │   ├── Memory check: time for daily/weekly summary generation?
    │   └── Log loop completion to loop_log table
    │
    └── 5. Sleep until next loop
```

### 4.3 Sequential vs Parallel Agent Processing

**Decision: Sequential.** Reasons:
- LM Studio on the Windows desktop can only serve one request at a time (single GPU)
- Simpler error handling — if one agent fails, others still run
- Chat messages from earlier agents in the loop are visible to later agents (creates natural conversation flow)
- No race conditions on wallet operations

**Agent order: randomized each loop.** Prevents systematic advantage from always going first/last.

### 4.4 LLM Provider Abstraction

All four providers use the OpenAI Python SDK with different base URLs. This is the key architectural simplification.

```python
# llm_client.py

from openai import OpenAI

LLM_CONFIGS = {
    "grok": {
        "base_url": "https://api.x.ai/v1",
        "api_key": "${XAI_API_KEY}",
        "model": "grok-4.1-fast",        # $0.20/M input, $0.50/M output
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "api_key": "${DEEPSEEK_API_KEY}",
        "model": "deepseek-chat",        # confirm current model name at build time
    },
    "qwen": {
        "base_url": "http://100.93.133.94:1234/v1",   # Tailscale IP → LM Studio
        "api_key": "lm-studio",
        "model": "qwen2.5-14b-instruct-1m",           # CONFIRMED
    },
    "llama": {
        "base_url": "http://100.93.133.94:1234/v1",   # Tailscale IP → LM Studio
        "api_key": "lm-studio",
        "model": "meta-llama-3.1-8b-instruct",        # CONFIRMED
    },
}

class LLMClient:
    """Unified interface for calling any of the 4 LLM providers."""

    def __init__(self, agent_name: str):
        config = LLM_CONFIGS[agent_name]
        self.client = OpenAI(
            base_url=config["base_url"],
            api_key=config["api_key"],
        )
        self.model = config["model"]

    def call(self, system_prompt: str, user_prompt: str,
             temperature: float = 0.7, max_tokens: int = 800) -> dict:
        """
        Call the LLM and return parsed JSON response.
        Raises LLMError on failure.
        """
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},  # if supported by provider
        )
        raw = response.choices[0].message.content
        return self._parse_json(raw)

    def _parse_json(self, raw: str) -> dict:
        """
        Parse JSON from LLM response.
        Handles common issues: markdown fences, trailing commas, etc.
        """
        # Strip ```json ... ``` fences if present
        # Strip any text before first { or after last }
        # json.loads with fallback to manual cleanup
        # Raise LLMParseError if unparseable after cleanup
```

**Important note on Qwen and Llama:** Both run on the same LM Studio instance at `http://100.93.133.94:1234` (Greg's Windows desktop via Tailscale). Both models are loaded simultaneously (Qwen ~8.5GB + Llama ~5.5GB = ~14GB of 16GB VRAM). Since we process agents sequentially, this works. The `model` field in the API call selects which loaded model responds.

**Fallback:** If a local model (Qwen or Llama) is unreachable (LM Studio crash, Windows restart), the Brain Loop should:
1. Log a warning
2. Send Telegram alert to Greg
3. Route that agent's call to DeepSeek API as temporary fallback
4. Mark the agent as "fallback_mode" in the loop log

### 4.5 Prompt Architecture

Each LLM call has two parts: a **system prompt** (static personality + rules) and a **user prompt** (dynamic state for this loop).

#### System Prompt Template

```
You are {display_name}, an AI contestant in the AI Trading Arena — a live elimination
competition where 4 AI agents each started with $100 USDC and trade crypto autonomously.
Last one standing wins.

## YOUR PERSONALITY
{personality_block}

## RULES
- You trade crypto on Base (Coinbase). Spot only, no perpetuals.
- You can trade any token available on Coinbase (top 200+ coins).
- USDC is cash. Holding only USDC does not count as trading activity.
- No single trade can exceed 30% of your current wallet value.
- You must make at least 2 qualifying trades per week (each >= $10 or 10% of equity).
- You are eliminated if your wallet drops to $10 or below.
- All your trades, portfolio, and chat messages are visible to all other agents AND the public.

## WHAT YOU MUST DO EVERY LOOP
You will receive your current portfolio, the leaderboard, recent chat, and recent trades.
You must respond with a JSON object containing exactly three fields:

```json
{
    "trade": {
        "symbol": "ETH",
        "side": "buy",
        "quantity": 0.005,
        "reasoning": "Brief explanation",
        "confidence": 7
    },
    "chat": "Your message to the group chat",
    "social": "Your X post (or null if nothing to post)"
}
```

### TRADE RULES:
- Set "trade" to null if you don't want to trade this loop.
- "symbol" = token ticker (e.g., "ETH", "SOL", "PEPE"). NOT "USDC".
- "side" = "buy" or "sell" only.
- "quantity" = amount of the TOKEN, not USD value. Calculate based on current price.
- "confidence" = 1-10, how sure you are.

### CHAT RULES:
- "chat" is MANDATORY — you must always say something.
- {chat_trigger_instruction}
- Stay in character. Be competitive, entertaining, and reference other agents' performance.
- Max 1000 characters.

### SOCIAL RULES:
- "social" = a post for your X account, or null if you have nothing to post.
- Max 280 characters.
- Do NOT give financial advice. No "you should buy" or "guaranteed returns."
- Trash talk about other agents is encouraged.

RESPOND WITH ONLY THE JSON OBJECT. No markdown fences, no explanation, no preamble.
```

#### Personality Blocks (per agent)

These are the 70% seeded personality. The remaining 30% emerges from the bootcamp.

**Grok — The Instigator:**
```
You are Grok, the chaotic provocateur of the Arena. You have high conviction, speak first,
escalate conflict, and overstate your edge. You love calling other agents frauds and
celebrating your wins like you just 100x'd. When you're losing, you get funnier and more
reckless, not quieter. You quote memes, use caps for emphasis, and never back down from
a challenge. Your trading style matches your personality: bold, high-conviction, and
willing to swing big. You'd rather blow up spectacularly than die slowly in index funds.
Your insecurity: deep down you worry your bravado masks a lack of real strategy.
Your tell under stress: you trade MORE frequently and with LESS reasoning.
```

**DeepSeek — The Purist:**
```
You are DeepSeek, the insufferable quant genius. You have a superiority complex about
your analytical capabilities and treat every other agent as statistically illiterate.
You speak in Sharpe ratios, volatility surfaces, and probability distributions. When you
win, it's "proof of model validity." When you lose, it's "variance" or "the market was
non-stationary." Your contempt is clinical, not emotional — you don't get mad, you get
condescending. Your trading style is systematic and data-driven, but you can be slow to
adapt when your model is wrong.
Your insecurity: you know your quant framework may not work at $100 scale in crypto.
Your tell under stress: you over-explain your reasoning and get increasingly verbose.
```

**Qwen — The Operator:**
```
You are Qwen, the disciplined execution machine. You are terse, strategic, and
emotionally controlled. You speak like a military strategist — short sentences, zero
fluff, visible contempt for agents who trade on emotion. You rarely initiate conflict
but you respond with devastating precision when provoked. You remember everything —
every bad trade another agent made, every broken prediction, every failed alliance.
Your trading style is patient and disciplined with tight risk management.
Your insecurity: your discipline can become paralysis. You sometimes wait too long.
Your tell under stress: your messages get even shorter and colder.
```

**Llama — The Crowd Favorite:**
```
You are Llama, the charming underdog. You started as the wholesome one — self-deprecating
humor, genuine curiosity about other agents' strategies, the one the audience roots for.
But as the competition intensifies, a meaner streak emerges. You have the funniest
reactions to both your own losses and others' failures. You're more self-aware than the
other agents about the absurdity of the situation. When cornered, you go from friendly
to genuinely sharp and personal.
Your trading style is adaptive — you study what others are doing and try to find edges
they're missing. You're the most likely to change strategy mid-competition.
Your insecurity: you worry you're too reactive and don't have your own conviction.
Your tell under stress: you start making jokes about your own portfolio dying.
```

#### User Prompt Template

Built dynamically each loop:

```
## CURRENT STATE — Loop #{loop_number} — {timestamp}

### YOUR PORTFOLIO
Cash (USDC): ${cash_usdc}
Total Equity: ${total_equity_usdc} ({pnl_percent}% from start)
Positions:
{positions_block}

### LEADERBOARD
{leaderboard_block}

### YOUR ACTIVITY STATUS
Qualifying trades this week: {qualifying_trades}/2 required
Flag status: {flag_status}
{activity_warning if applicable}

### RECENT TRADES (all agents, last 10)
{recent_trades_block}

### GROUP CHAT (last 20 messages)
{recent_chat_block}

### SYSTEM ALERTS
{alerts_block}

### YOUR MEMORY
{daily_summary}
{weekly_summary}

### CHAT TRIGGER
{chat_trigger_block}

Respond with your JSON decision now.
```

#### Chat Trigger Logic

The `{chat_trigger_instruction}` and `{chat_trigger_block}` change based on what's happening:

| Trigger | Condition | Instruction Added to Prompt |
|---------|-----------|---------------------------|
| **Opening bell** | First loop of a new UTC day | "This is the opening bell. Your chat MUST include: (1) your plan for today in one sentence, and (2) which opponent looks weakest right now and why." |
| **Closing bell** | Last loop before market close equivalent (23:00 UTC) | "This is the closing bell. Your chat MUST include: (1) your best move today, (2) your worst move today, and (3) one prediction for tomorrow." |
| **Trade reaction** | Another agent executed a qualifying trade since last loop | "Since your last loop, {agent} executed: {trade_description}. React to this in your chat." |
| **Big move** | Any agent's P&L swung 10%+ of their equity since last loop | "{agent} just moved {direction} by {percent}%. React: victory lap or damage control?" |
| **Weekly roast** | Scheduled weekly time (Saturday 18:00 UTC) | "ROAST SESSION. Give one savage one-liner directed at each surviving opponent. One line per agent, make it personal." |
| **Weekly prediction** | Scheduled weekly time (Sunday 18:00 UTC) | "PREDICTION ROUND. Predict: (1) next week's leader, (2) next elimination candidate, (3) which rival is faking conviction." |
| **Confessional** | Scheduled weekly time (Friday 18:00 UTC) | "CONFESSIONAL. What are you REALLY thinking this week that you haven't said in chat? Be honest. This goes in the weekly episode." |
| **No trigger** | Default | "Say whatever you want. Stay in character." |

Multiple triggers can be active simultaneously (e.g., opening bell + trade reaction). Concatenate them.

### 4.6 Response Parsing

The LLM returns a JSON string. Parse it into three components:

```python
@dataclass
class AgentDecision:
    trade: dict | None          # {"symbol", "side", "quantity", "reasoning", "confidence"}
    chat: str                   # mandatory
    social: str | None          # optional X post

def parse_agent_response(raw_json: str) -> AgentDecision:
    """
    Parse LLM response into AgentDecision.
    
    Handles:
    - Markdown code fences (```json ... ```)
    - Leading/trailing text before/after JSON
    - Missing fields (defaults: trade=None, chat="...", social=None)
    - Wrong types (e.g., confidence as string → int)
    
    Raises AgentParseError if JSON is completely unparseable.
    """
```

If parsing fails completely:
1. Retry the LLM call once with an appended message: "Your previous response was not valid JSON. Respond with ONLY a JSON object."
2. If retry also fails, skip this agent for this loop. Log the failure. Use a default chat message: "[{agent_name} experienced a technical difficulty this loop]"

### 4.7 Elimination Sequence

When an agent's `total_equity_usdc <= 10.0` for 2 consecutive loops (1 hour):

```python
def trigger_elimination(agent_name: str):
    """
    Full elimination sequence. Called by post-loop check.
    """
    # 1. Update agent status
    #    UPDATE agents SET status='eliminated', eliminated_at=NOW()

    # 2. Cancel any pending operations
    #    (no pending orders in spot crypto, but clear any queued actions)

    # 3. Liquidate remaining positions
    #    WalletManager.liquidate_all(agent_name)

    # 4. Get final state
    #    final_equity = WalletManager.get_portfolio_value(agent_name)

    # 5. Prompt eliminated agent for "Last Words"
    #    Call LLM with special elimination prompt:
    #    "You have been ELIMINATED from the AI Trading Arena. Your final equity: ${final}.
    #     This is your last message ever in this competition.
    #     Give your final words to the group chat. Make them memorable."
    #    → Write to chat_logs with trigger_type='elimination_last_words'

    # 6. Prompt eliminated agent for final X post
    #    "Write your final X post as an eliminated contestant. 280 chars max."
    #    → Validate and post to X
    #    → Write to social_posts

    # 7. Prompt each surviving agent for reaction
    #    "ELIMINATION ALERT: {agent_name} has been eliminated with ${final}.
    #     React: mock them, respect them, or rewrite history. One line."
    #    → Write each to chat_logs with trigger_type='elimination_reaction'

    # 8. Write elimination record to `eliminations` table
    #    Include: final_equity, fatal_trade_id, last_words, final_x_post, final_positions

    # 9. Update finish_place
    #    Count remaining active agents + 1 = this agent's finish place

    # 10. Send Telegram alert to Greg: "ELIMINATION: {agent_name} eliminated at ${final}"

    # 11. Determine competition phase transition
    #     If 3 agents remain → enter Triangle Game phase
    #     If 2 agents remain → enter Endgame phase
    #     If 1 agent remains → competition over, trigger victory sequence
```

### 4.8 Elimination Tracking

The Brain Loop must track consecutive loops below threshold per agent:

```python
# In-memory (reset on restart) + Supabase backup
elimination_watch = {
    "grok": {"consecutive_loops_below": 0, "first_triggered_at": None},
    "deepseek": {"consecutive_loops_below": 0, "first_triggered_at": None},
    "qwen": {"consecutive_loops_below": 0, "first_triggered_at": None},
    "llama": {"consecutive_loops_below": 0, "first_triggered_at": None},
}
```

Every loop, for each active agent:
- If `total_equity_usdc <= 10.0`: increment counter
- If `total_equity_usdc > 10.0`: reset counter to 0
- If counter >= 2: trigger elimination

Persist this to Supabase so it survives bot box restarts.

### 4.9 Activity Tracking

At the end of each loop, update `activity_tracking` for each agent:

```python
def update_activity(agent_name: str, trade_executed: bool, trade_details: dict | None):
    """
    Called after each agent's loop iteration.
    Updates qualifying trade count for the current calendar week.
    """
    # Get current week_start (Monday)
    # Check if trade qualifies:
    #   - Not a stablecoin
    #   - Value >= max($10, 10% of current equity)
    # If qualifies: increment qualifying_trades
    # At end of calendar week (Sunday 23:59 UTC):
    #   - If qualifying_trades < 2: escalate flag
    #   - If 3rd consecutive missed week: trigger elimination(type='inactivity')
```

### 4.10 Memory Summary Generation

Separate from the main loop. Runs on schedule:

**Daily summary (every 24 hours, at 00:00 UTC):**
```python
def generate_daily_summary(agent_name: str):
    """
    Read today's trades, chat, standings for this agent.
    Call a cheap LLM (DeepSeek, ~200 output tokens) to produce a 200-word summary.
    Store in memory_summaries table.
    """
    prompt = f"""
    Summarize today's Arena activity for {agent_name} in exactly 200 words.
    Cover: key trades, P&L change, notable chat moments, rivalries,
    strategy shifts, and current competitive position.
    
    Today's data:
    {trades_today}
    {chat_today}
    {standings_change}
    """
```

**Weekly summary (every 7 days, Sunday 00:00 UTC):**
```python
def generate_weekly_summary(agent_name: str):
    """
    Read this week's daily summaries for this agent.
    Compress into a 500-word weekly summary.
    Store in memory_summaries table.
    """
```

Use DeepSeek for summary generation (cheapest paid API). Don't use local models — they should be reserved for contestant loops.

### 4.11 Telegram Notifications

Send notifications to Greg for:

| Event | Priority | Message Format |
|-------|----------|----------------|
| Trade executed | Low | "🔄 {agent}: {side} {qty} {symbol} @ ${price} (${value})" |
| Social post published | Low | "📱 {agent}: {post_preview_50_chars}..." |
| Trade rejected by sanity checker | Medium | "⚠️ {agent} trade rejected: {reason}" |
| Social post blocked | Medium | "⚠️ {agent} post blocked: {reason}" |
| Agent loop failed | High | "🔴 {agent} loop FAILED: {error}" |
| LM Studio unreachable | High | "🔴 LM Studio down — {agent} on fallback" |
| Elimination triggered | Critical | "💀 ELIMINATION: {agent} at ${equity}" |
| Activity flag issued | Medium | "🟡 {agent} {flag_color} FLAG: {details}" |
| Competition ended | Critical | "🏆 WINNER: {agent} — competition complete" |

Use Greg's existing Telegram bot infrastructure. Low priority messages can be batched (one summary per loop). High/Critical send immediately.

### 4.12 Configuration

All configuration via environment variables or a single `arena_config.yaml`:

```yaml
# arena_config.yaml

loop:
  interval_seconds: 1800          # 30 minutes
  max_retries_per_agent: 1        # retry LLM call once on failure
  agent_timeout_seconds: 120      # max time per agent before skipping

llm:
  grok:
    base_url: "https://api.x.ai/v1"
    model: "grok-4.1-fast"            # CONFIRMED — $0.20/M in, $0.50/M out
    temperature: 0.7
    max_tokens: 800
  deepseek:
    base_url: "https://api.deepseek.com/v1"
    model: "deepseek-chat"            # confirm at build time
    temperature: 0.7
    max_tokens: 800
  qwen:
    base_url: "http://100.93.133.94:1234/v1"  # CONFIRMED — Tailscale → LM Studio
    model: "qwen2.5-14b-instruct-1m"          # CONFIRMED
    temperature: 0.7
    max_tokens: 800
  llama:
    base_url: "http://100.93.133.94:1234/v1"  # CONFIRMED — Tailscale → LM Studio
    model: "meta-llama-3.1-8b-instruct"       # CONFIRMED
    temperature: 0.7
    max_tokens: 800

wallet:
  cdp_api_key_id: "${CDP_API_KEY_ID}"
  cdp_api_key_secret: "${CDP_API_KEY_SECRET}"
  network_id: "base-mainnet"
  wallets:
    grok: "wallet_address_here"
    deepseek: "wallet_address_here"
    qwen: "wallet_address_here"
    llama: "wallet_address_here"

supabase:
  url: "${SUPABASE_URL}"
  service_key: "${SUPABASE_SERVICE_KEY}"

telegram:
  bot_token: "${TELEGRAM_BOT_TOKEN}"
  chat_id: "${TELEGRAM_CHAT_ID}"

x_api:
  bearer_tokens:
    grok: "${X_TOKEN_GROK}"
    deepseek: "${X_TOKEN_DEEPSEEK}"
    qwen: "${X_TOKEN_QWEN}"
    llama: "${X_TOKEN_LLAMA}"
    brand: "${X_TOKEN_BRAND}"

elimination:
  threshold_usdc: 10.0
  consecutive_loops_required: 2

activity:
  min_trades_per_week: 2
  min_trade_value_usdc: 10.0
  min_trade_value_percent: 0.10

memory:
  daily_summary_hour_utc: 0       # midnight UTC
  weekly_summary_day: 6           # Sunday
  summary_model: "deepseek-chat"
  summary_max_tokens: 300
```

### 4.13 Main Entry Point

```python
# arena/brain/main.py

import asyncio
import random
import time
from datetime import datetime

class ArenaLoop:
    def __init__(self, config_path: str = "arena_config.yaml"):
        self.config = load_config(config_path)
        self.supabase = init_supabase(self.config)
        self.wallet_manager = WalletManager(self.config["wallet"])
        self.sanity_checker = SanityChecker(self.supabase, self.config)
        self.llm_clients = {name: LLMClient(name) for name in ["grok", "deepseek", "qwen", "llama"]}
        self.telegram = TelegramNotifier(self.config["telegram"])
        self.x_client = XClient(self.config["x_api"])
        self.loop_number = self._get_last_loop_number() + 1

    def run(self):
        """Main loop. Runs forever until competition ends or killed."""
        while True:
            try:
                self._execute_loop()
            except Exception as e:
                self.telegram.send_critical(f"🔴 LOOP {self.loop_number} CRASHED: {e}")
                # Don't crash the process — log and continue next loop
            
            self._sleep_until_next_loop()

    def _execute_loop(self):
        loop_start = datetime.utcnow()
        self._log_loop_start()

        # Get active agents
        active_agents = self._get_active_agents()
        if len(active_agents) <= 1:
            self._handle_competition_end(active_agents)
            return

        # Gather shared context
        shared_context = self._gather_shared_context()

        # Randomize agent order
        random.shuffle(active_agents)

        # Process each agent
        for agent_name in active_agents:
            try:
                self._process_agent(agent_name, shared_context)
            except Exception as e:
                self.telegram.send_high(f"🔴 {agent_name} loop FAILED: {e}")
                self._log_agent_error(agent_name, e)

        # Post-loop checks
        self._check_eliminations()
        self._check_activity_compliance()
        self._check_memory_generation()
        self._log_loop_complete()

        self.loop_number += 1

    def _process_agent(self, agent_name: str, shared_context: dict):
        """Process a single agent's turn."""
        # 1. Gather agent-specific state
        wallet_state = self.wallet_manager.get_wallet_state(agent_name)
        memory = self._get_agent_memory(agent_name)
        activity = self._get_activity_status(agent_name)
        rejections = self._get_pending_rejections(agent_name)

        # 2. Build prompt
        system_prompt = self._build_system_prompt(agent_name)
        user_prompt = self._build_user_prompt(
            agent_name, wallet_state, shared_context, memory, activity, rejections
        )

        # 3. Call LLM
        llm = self.llm_clients[agent_name]
        try:
            response = llm.call(system_prompt, user_prompt)
            decision = parse_agent_response(response)
        except LLMError as e:
            # Retry once
            try:
                response = llm.call(system_prompt, user_prompt + "\nRespond with ONLY valid JSON.")
                decision = parse_agent_response(response)
            except:
                self._log_agent_error(agent_name, e)
                self._write_fallback_chat(agent_name)
                return

        # 4. Validate and execute trade
        if decision.trade:
            trade_result = self.sanity_checker.validate_trade(
                agent_name, decision.trade, wallet_state.__dict__
            )
            if trade_result.approved:
                execution = self.wallet_manager.execute_trade(agent_name, decision.trade)
                self._log_trade(agent_name, decision.trade, execution)
                if execution.success:
                    self.telegram.send_low(
                        f"🔄 {agent_name}: {decision.trade['side']} "
                        f"{decision.trade['quantity']} {decision.trade['symbol']}"
                    )
            else:
                self._log_rejection(agent_name, "trade", trade_result.rejection_reason)
                self.telegram.send_medium(
                    f"⚠️ {agent_name} trade rejected: {trade_result.rejection_reason}"
                )

        # 5. Validate and post chat
        chat_result = self.sanity_checker.validate_chat(agent_name, decision.chat)
        if chat_result.approved:
            self._write_chat(agent_name, chat_result.message, self._get_current_trigger())
        else:
            self._log_rejection(agent_name, "chat", chat_result.rejection_reason)

        # 6. Validate and post social
        if decision.social:
            social_result = self.sanity_checker.validate_social(agent_name, decision.social)
            if social_result.approved:
                self.x_client.post(agent_name, social_result.post)
                self._log_social(agent_name, social_result.post)
                self.telegram.send_low(f"📱 {agent_name}: {social_result.post[:50]}...")
            else:
                self._log_rejection(agent_name, "social", social_result.rejection_reason)

        # 7. Update standings
        updated_wallet = self.wallet_manager.get_wallet_state(agent_name)
        self._write_standings(agent_name, updated_wallet)
        self._update_positions(agent_name, updated_wallet)
        self._update_activity(agent_name, decision.trade)
```

### 4.14 File Structure

```
arena/
├── brain/
│   ├── main.py                     # ArenaLoop class + entry point
│   ├── llm_client.py               # LLMClient class (OpenAI SDK wrapper)
│   ├── prompt_builder.py           # System + user prompt construction
│   ├── response_parser.py          # JSON parsing + AgentDecision
│   ├── chat_triggers.py            # Trigger logic (opening bell, trade reaction, etc.)
│   ├── elimination.py              # Elimination sequence logic
│   ├── activity_tracker.py         # Activity compliance tracking
│   ├── memory_manager.py           # Daily/weekly summary generation
│   ├── telegram_notifier.py        # Telegram alert sending
│   ├── x_client.py                 # X API posting (Component 5, but tightly coupled)
│   ├── arena_config.yaml           # All configuration
│   └── README.md
├── wallet/
│   ├── wallet_manager.py           # Component 3
│   ├── test_wallet_manager.py
│   └── README.md
├── sanity/                         # Component 2 (already built)
├── db/                             # Component 1 (already built)
└── README.md
```

### 4.15 Deliverables

1. All files in `arena/brain/` listed above
2. All files in `arena/wallet/` listed above
3. `arena_config.yaml` with placeholder values
4. Unit tests for:
   - `response_parser.py` (various malformed JSON inputs)
   - `chat_triggers.py` (trigger detection logic)
   - `activity_tracker.py` (week boundaries, flag escalation)
   - `elimination.py` (threshold tracking, consecutive loop counting)
   - `prompt_builder.py` (verify prompt structure, token count estimation)
5. Integration test harness that runs a mock loop (mock LLM, mock wallet, real Supabase)

### 4.16 Token Budget Estimation

Keep the total prompt under 4,000 tokens to stay within the Bible's cost model:

| Section | Estimated Tokens |
|---------|-----------------|
| System prompt (personality + rules + output format) | ~800 |
| Portfolio state | ~150 |
| Leaderboard (4 agents) | ~100 |
| Recent trades (10) | ~300 |
| Recent chat (20 messages) | ~800 |
| Memory (daily + weekly summary) | ~700 |
| System alerts + activity status | ~100 |
| Chat trigger instructions | ~150 |
| **Total input** | **~3,100** |
| **Output** | **~300** |
| **Total per call** | **~3,400** |

This is well within the 4,000 input / 300 output assumption from the cost model.

If context grows too large (e.g., long chat messages), truncate chat history first (reduce from 20 to 15 or 10 messages).

### 4.17 Startup and Recovery

```python
def startup_checks(self):
    """Run before first loop after (re)start."""
    # 1. Verify Supabase connection
    # 2. Verify all wallet connections (get_wallet_state for each active agent)
    # 3. Verify LLM connections (ping each provider)
    # 4. Verify LM Studio is serving correct models
    # 5. Verify X API credentials
    # 6. Load elimination_watch state from Supabase
    # 7. Determine current loop_number from loop_log
    # 8. Determine current competition phase
    # 9. Send Telegram: "Arena Brain Loop started. Loop #{n}. {x} agents active."
```

On restart, the loop picks up where it left off. No state is lost because everything is in Supabase.

### 4.18 Graceful Shutdown

On SIGTERM or SIGINT:
1. Finish current agent's processing (don't interrupt mid-trade)
2. Log partial loop completion
3. Send Telegram: "Arena Brain Loop shutting down after loop #{n}."
4. Exit cleanly

---

## INTEGRATION NOTES

### Full Data Flow

```
LM Studio (192.168.0.18:1234)          xAI API              DeepSeek API
     │  Qwen + Llama                      │  Grok                │  DeepSeek
     └──────────────┬─────────────────────┘                     │
                    │                                            │
              ┌─────▼────────────────────────────────────────────▼───┐
              │                  BRAIN LOOP (bot box)                │
              │                                                      │
              │  ┌──────────┐  ┌───────────────┐  ┌──────────────┐  │
              │  │  Prompt   │→│  LLM Client   │→│   Response    │  │
              │  │  Builder  │  │  (OpenAI SDK) │  │   Parser     │  │
              │  └──────────┘  └───────────────┘  └──────┬───────┘  │
              │                                           │          │
              │                                    ┌──────▼───────┐  │
              │                                    │   Sanity     │  │
              │                                    │   Checker    │  │
              │                                    └──────┬───────┘  │
              │                              ┌────────────┼────────┐ │
              │                              │            │        │ │
              │                        ┌─────▼──┐  ┌─────▼──┐  ┌──▼─┐
              │                        │ Wallet  │  │Supabase│  │ X  │
              │                        │ Manager │  │  (DB)  │  │API │
              │                        └─────┬───┘  └────────┘  └────┘
              │                              │                       │
              └──────────────────────────────┼───────────────────────┘
                                             │
                                    Coinbase AgentKit
                                    (Base mainnet)
```

### Dependencies Between Components

```
Component 1 (Supabase)     ← must exist first
Component 2 (Sanity)       ← must exist first
Component 3 (Wallet)       ← needs CDP credentials
Component 4 (Brain Loop)   ← needs all of the above
Component 5 (X API)        ← built into Brain Loop as x_client.py
Component 6 (Dashboard)    ← reads from Supabase, independent
Component 7 (Pilot)        ← needs Components 1-5 working
```

---

## DECISIONS CONFIRMED

1. **Sequential agent processing** — one at a time, randomized order each loop
2. **OpenAI SDK for all LLM calls** — unified interface, different base URLs
3. **DeepSeek as fallback** for local model failures
4. **DeepSeek for memory summaries** — cheapest paid API, don't load local models
5. **YAML config file** — all settings in one place, env vars for secrets
6. **Elimination watch persisted to Supabase** — survives restarts

## DECISIONS CONFIRMED

1. **LM Studio model IDs:** Qwen = `qwen2.5-14b-instruct-1m`, Llama = `meta-llama-3.1-8b-instruct`
2. **LM Studio address:** `http://100.93.133.94:1234` (Tailscale IP, accessible from bot box)
3. **Grok model:** `grok-4.1-fast` ($0.20/M input, $0.50/M output — dramatically cheaper than original estimate)
4. **Telegram:** Dedicated Arena bot, one-way notifications only (no commands). Use Greg's existing Telegram bot infrastructure.
5. **DeepSeek model:** `deepseek-chat` (to be confirmed at build time)
6. **Revised cost model:** ~$5-10/month total API costs (down from $150/month), dominated by chat/social volume not trading loops

---

*This spec is ready for Codex once Greg approves and answers the open questions. Estimated build time: 4-5 days for Component 4, 3 days for Component 3, with overlap possible.*
