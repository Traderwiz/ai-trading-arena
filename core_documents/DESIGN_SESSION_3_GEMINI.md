# DESIGN SESSION 3: GEMINI — TECHNICAL PRODUCER
**Date:** April 8, 2026
**Agent:** Gemini (Google)
**Role:** Technical Producer — Infrastructure, Cost Model, Build Spec
**Model:** Gemini 3 (Thinking mode)
**Note:** This session was conducted in two parts (3A and 3B) plus regulatory follow-up

---

## BRIEF (SESSION 3A)

**DESIGN BRIEF: GEMINI — TECHNICAL PRODUCER**
**AI Trading Arena — Phase 1, Session 3**
**Date:** April 8, 2026

**WHAT THIS IS**

You're the Technical Producer for AI Trading Arena — a live elimination-format competition where 4 LLMs each receive $100 CAD in a real IBKR brokerage account and trade autonomously. No time limit. Last one standing wins. The agents share a transparent group chat, see each other's portfolios and P&L in real time, and each run their own autonomous X (Twitter) account. A public dashboard shows everything to the audience, and a weekly episode recaps the action in a reality-TV format.

Season 1 is an experiment run by a solo human operator (Greg) using existing infrastructure. The concept and format have been designed. Your job is to tell us whether it's buildable, what it costs, and how to build it.

**WHAT'S BEEN DECIDED**

Core rules:
- $100 CAD real money per contestant, cash-only IBKR accounts, no margin
- 4 contestants: Grok, DeepSeek, Qwen, Llama (Qwen and Llama run locally on Greg's desktop via LM Studio)
- All IBKR instruments permitted, agents handle their own CAD/USD currency conversion
- Full portfolio/trade/P&L transparency between all agents and the public audience
- No time limit — runs until one agent remains
- No human intervention once live
- Elimination at $10 CAD equity threshold, confirmed by 15 consecutive market minutes or at market close
- Minimum 2 qualifying trades per calendar week (each at least $10 CAD or 10% of equity)
- Mandatory daily chat participation (opening bell, closing bell prompts) regardless of trading activity
- Trading frequency TBD — preference is as close to real-time as budget allows

Format:
- Chat triggers: opening bell, trade reaction, big move (10%+ P&L swing), closing bell, weekly roast, weekly prediction round, weekly confessional
- Event-driven narrative phases: Bootcamp → Opening Chaos → Pressure Cooker → First Blood → Triangle → Endgame
- Weekly 8-12 minute episode edited like reality TV
- X as primary autonomous social platform per agent, brand account cross-posts to Instagram/TikTok/YouTube with minimal human input
- Audience is view-only for Season 1 (no voting or interaction mechanics)
- 72-hour persona bootcamp before go-live (chat only, no trading)

Existing infrastructure:
- Ubuntu bot box (192.168.0.21) — always-on automation node
- Windows desktop (192.168.0.18) — RTX 4070 Ti SUPER, 16GB VRAM, runs LM Studio with Qwen 14B and Llama locally
- Backtesting server (192.168.0.22)
- IBKR trading infrastructure (traderd) — already built, used for existing 0DTE trading system
- COLLOQUY multi-agent orchestration system
- Telegram bot infrastructure
- Codex as implementation agent

Greg is a non-coder who architects and reviews. Claude Code / Codex handle implementation.

**WHAT I NEED FROM YOU**

1. API cost model at three frequency tiers (real-time/every 5 min, moderate/every 30 min, conservative/every 2 hours)
2. Agent decision loop spec (inputs, outputs, prompt architecture)
3. Market data pipeline (sources, format, cost, refresh rate)
4. Dashboard technical spec (tech stack, data flow, build time)
5. Weekly episode production pipeline (AI tools, human effort, cost)
6. Social media automation pipeline (X API, cross-platform, costs)
7. IBKR account structure (Friends & Family, Advisor, or individual)
8. Broker failure and edge cases (error handling, circuit breakers)
9. Content archive architecture (storage schema)
10. Build estimate (components, sequencing, MVP definition)

---

## RESPONSE (SESSION 3A)

This is buildable, Greg. However, Season 1 requires a "Lean & Mean" architectural approach.

**1. API Cost Model**

Assumptions: Average loop 4,000 input tokens / 300 output tokens. Market hours 6.5 hours/day, 20 days/month. Paid agents: 2 (Grok & DeepSeek). Qwen/Llama are free.

| Tier | Frequency | Daily Cost | Monthly Cost | Verdict |
|------|-----------|------------|--------------|---------|
| Conservative | Every 2 hours (4x/day) | ~$1.20 | ~$24.00 | Boring for live viewers |
| Moderate | Every 30 mins (13x/day) | ~$3.90 | ~$78.00 | Sweet spot for S1 |
| Real-Time | Every 5 mins (78x/day) | ~$23.40 | ~$468.00 | Risk of API rate limits |

Producer's Note: Context management is the lever. If you feed the entire season history every loop, the "Real-Time" tier will cost $2,000+ by week four. Must use "Summary Memory" saved in database.

**2. Agent Decision Loop Spec**

Input (JSON): market_data (current price, 1h trend, volatility), portfolio_state (cash, positions, total equity, P&L %), arena_context (current leaderboard, last 10 messages from group chat), personality_brief (the agent's specific "vibe").

Output (Structured JSON): trade (symbol, side, qty), chat (message), social (X post content).

**3. Market Data Pipeline**

Primary source: IBKR API (via traderd). Snapshot data is free/low-cost with existing data subscriptions (~$15 USD/mo). traderd should flatten data into simple JSON. Must provide buying power in the currency of the asset being considered.

**4. Dashboard Technical Spec**

Tech stack: Streamlit (Python). Data flow: Bot box runs loop → writes to Supabase (PostgreSQL) → Streamlit reads and refreshes every 60 seconds. Build time: 3-5 days for Codex.

**5. Weekly Episode Production**

Script: Feed week's CSV to Claude for reality TV script. Voiceover: ElevenLabs. Visuals: Shotstack or Placid.app APIs. Edit: Greg drops assets into CapCut. Human effort: 2 hours/week. Cost: ~$50/mo.

**6. Social Media & X API**

X API Basic Tier ($100/mo). COLLOQUY triggers Python script hitting X API after trade confirmation. Cross-posting via Repurpose.io.

**7. IBKR Account Structure**

Recommendation: Friends & Family Advisor Account. One master login with 4 sub-accounts. traderd config needs acctId parameter per call.

**8. Failure & Edge Cases**

Hallucination guard: Python sanity checker rejects trades where total_cost > current_cash. Ticker validation: whitelist of 50-100 liquid tickers. Local crash: Bot box sends Telegram alert, freezes agent's turn.

**9. Build Estimate**

| Component | Build Time | Complexity |
|-----------|-----------|------------|
| Account Orchestrator | 2 Days | Medium |
| The "Brain" Loop | 3 Days | High |
| Supabase DB & Logging | 1 Day | Low |
| Streamlit Dashboard | 3 Days | Medium |
| X API Integration | 1 Day | Low |
| **TOTAL** | **~2 Weeks** | |

**CRITICAL PIVOT RECOMMENDATION:**

Gemini recommended switching from IBKR to on-chain crypto trading. Key arguments:
- IBKR commission of $1.75+ per trade eats 2% of $100 equity per trade
- Crypto on L2 (Base) costs ~$0.17 per trade
- 24/7 markets create more content moments
- Coinbase Agentic Wallets are purpose-built for LLM trading
- "AI Agents Trading On-Chain" is culturally hotter than Canadian penny stocks

---

## BRIEF (SESSION 3B — FOLLOW-UP)

**FOLLOW-UP BRIEF: GEMINI — TECHNICAL PRODUCER (SESSION 3B)**

**CONTEXT:** Crypto pivot accepted. IBKR is out. All other locked decisions remain.

**PART 1: CRYPTO PIVOT SPEC**
1. Platform selection — pick one chain/platform and justify
2. Wallet architecture — creation, funding, monitoring, security
3. Tradeable universe — what can agents trade, guardrails against rug pulls
4. Fee structure — exact breakdown for a $20 trade
5. CAD conversion path — cheapest onramp
6. Updated cost model — does 24/7 change the math?
7. Elimination mechanics — how does $10 threshold work in crypto?

**PART 2: UNANSWERED QUESTIONS**
8. Context window management / Summary Memory architecture
9. Content archive schema
10. Social media automation pipeline details
11. Weekly episode production pipeline (more detail needed)
12. Persona bootcamp technical spec
13. Broker failure / edge cases for crypto
14. Updated build estimate

---

## RESPONSE (SESSION 3B)

**1. Platform Selection: Coinbase Agentic Wallets (Base)**

Why: Purpose-built for LLMs. "Agent Skills" (pre-coded trade/transfer/verify functions). Gasless on Base under developer tier. Every trade generates BaseScan URL for transparency.

**2. Wallet Architecture & Security**

Creation: Greg uses Coinbase Developer Platform (CDP) to spin up 4 Server Wallets. Security: Private keys in Trusted Execution Environment (TEE). Greg never sees keys, AI only has "permission to sign" within guardrails. Funding: Greg funds via Interac e-Transfer, distributes $100 USDC to each wallet.

**3. Tradeable Universe & Guardrails**

Agents can only trade tokens in Coinbase Trade API (top 200+ coins). Liquidity gate: DEX Screener API check, auto-reject if token has <$100K liquidity. Spot only, no perps for Season 1.

**4. Fee Structure ($20 Trade)**

| Fee Type | IBKR | Base (Agentic) |
|----------|------|----------------|
| Gas Fee | N/A | $0.00 (Gasless) |
| Swap/Execution | $1.75+ | $0.17 (0.85%) |
| Slippage | High | <0.1% |
| **TOTAL** | **~$1.75** | **~$0.17** |

**5. Updated Cost Model (24/7)**

48 loops/day (every 30 mins), 4 agents:
- LLM API (DeepSeek/Grok): ~$4.50/day (~$135/mo)
- X API (pay-as-you-go): $0.01/post (~$5/mo)
- **Total monthly: ~$150**

**6. Context Window & Summary Memory**

- Tier 1 (Working Memory): Last 20 chat messages + current portfolio + last 10 trades + leaderboard
- Tier 2 (Daily Summary): Cheap LLM writes 200-word daily status report per agent every 24 hours
- Tier 3 (Weekly Summary): Daily summaries compressed into 500-word weekly summary
- Archive: Full history in Supabase, accessed only for episode production

**7. Content Archive (Supabase)**

Core tables:
- `standings`: id, timestamp, agent_name, total_equity_usdc, pnl_percent
- `trades`: id, agent_name, symbol, side, price, qty, tx_hash, usdc_value
- `chat_logs`: id, timestamp, sender, message, trigger_type
- `social_posts`: id, agent_name, platform, content, posted_at
- `eliminations`: id, agent_name, final_equity, fatal_trade, last_words, timestamp

All trades logged in USDC equivalent.

**8. Social Media Pipeline**

Agent loop outputs social_post JSON → content filter screens → published directly to X via API → Repurpose.io monitors and cross-posts → Greg receives read-only Telegram notification. No approval queue.

**9. Weekly Episode Pipeline**

Script: Claude reads trades/chat tables. Render: JSON2Video with ElevenLabs voice + dynamic charts + HeyGen avatar for confessionals. Result: Rendered .mp4 in inbox. Human effort: 30 minutes to review.

**10. Persona Bootcamp Spec**

72 hours, chat-only. Agents in private chat. Bot box injects "Market Shock" every 4 hours. Goal: refine system prompts before real money goes live.

**11. Error Handling (Crypto)**

- RPC failure: Retry 3x, alert Greg, skip turn
- Swap failure: Cancel, inform agent "Order Rejected: High Slippage"
- Local model crash: Switch to DeepSeek API temporarily

**12. Updated Build Estimate**

| Component | Build Time | Dependencies |
|-----------|-----------|--------------|
| CDP Wallet Integration | 3 Days | Coinbase Developer Account |
| Arena "Brain" Loop | 4 Days | DeepSeek/Grok API keys |
| Supabase + Dashboard | 3 Days | None |
| Social/Review Pipeline | 2 Days | X API |
| JSON2Video Workflow | 3 Days | ElevenLabs/HeyGen |
| **TOTAL** | **~3 Weeks** | |

MVP for pilot: 2 agents (Grok + DeepSeek), real wallets, 48 hours, no dashboard or video pipeline.

---

## REGULATORY FOLLOW-UP

**Q:** Are there restrictions on Canadians/Ontario residents using Coinbase Agentic Wallets? Any regulatory issues with autonomous AI crypto trading?

**A:**
- Coinbase Canada is a registered Restricted Dealer and FINTRAC-registered MSB — no geofence on Agentic Wallets
- $30K annual Ontario limit on altcoins — not a concern at $100/agent scale; BTC, ETH, USDC exempt
- Greg is not an MSB — trading his own $400
- "Finfluencer" risk: mitigated by mandatory disclaimer on all content and no copy-trading features
- Mandatory disclaimer: "This is an experimental AI simulation. No trades are financial advice. For entertainment purposes only."
- Backup platform: Kraken CLI (March 2026) with native MCP server, fully registered with FINTRAC

**Final architecture:** Coinbase Agentic Wallets for trading, Kraken for funding onramp (Greg's existing account). Hybrid model: buy USDC on Kraken → transfer to Coinbase wallets on Base.

---

## TRADEABLE UNIVERSE FOLLOW-UP

**Q:** Can agents swap token-to-token? What about delisted tokens? Liquidity drain after purchase? USDC as cash?

**A:**
- Token-to-token swaps: Allowed, router (0x Argon) handles pathing, all trades logged in USDC equivalent
- Delisted tokens: Frozen assets, natural trading risk, no intervention
- Liquidity drain: Agent warned, no forced sell, strategic choice to hold or exit
- USDC = Cash: Does not count toward activity requirements

---

## DYNAMIC CAP FOLLOW-UP

**Q:** Does Coinbase support dynamic spending caps?

**A:** CDP caps are fixed at protocol level. Dynamic 30% cap must be built into the sanity checker layer. Codex implements a "pre-flight check" — wallet.balance() × 0.29 (with buffer) compared against proposed trade. Low complexity, ~15-20 lines of Python.

---

## PM ASSESSMENT (Claude)

**Adopted:**
- Platform: Coinbase Agentic Wallets on Base (crypto pivot)
- Kraken as funding onramp and backup
- CDP server wallets, keys in TEE
- Dynamic 30% cap via sanity checker
- 3-tier memory architecture (expanded working memory to 20 messages, 10 trades)
- Supabase as central database with specified schema
- Direct social posting, content filter, kill switch (no approval queue)
- ~$150/month operating cost
- 2-agent pilot (infrastructure test only, data wiped before competition)
- Streamlit for MVP dashboard

**Modified:**
- Working memory expanded from Gemini's 10 messages/3 trades to 20 messages/10 trades
- Added weekly summary tier to memory architecture
- Ticker whitelist replaced with ticker validation (don't restrict strategy)
- Episode pipeline: manual first, automate after knowing what good looks like
- Elimination updated for crypto: $10 USDC equivalent, 2 consecutive loops (1 hour)
- Inactivity penalty kept as flag/elimination escalation, not dollar drain

**Rejected:**
- Ticker whitelist (too restrictive)
- Gemini's $5/day inactivity penalty (artificial balance manipulation)
- CapCut manual editing as final pipeline (Greg doesn't want manual editing)

**Flagged as open:**
- 24/7 loop frequency optimization (full frequency during peak, reduced overnight)
- Coinbase Trade API scope vs broader token access
- Episode automation pipeline (deferred to after manual episodes prove the format)
