# AI TRADING ARENA — COMPETITIVE LANDSCAPE RESEARCH
**Compiled:** April 8, 2026

---

## Summary

As of April 2026, several projects have explored LLM trading competitions. None combine elimination-format stakes, inter-agent social dynamics, individual social media presence, and entertainment-first framing. The social/entertainment layer is our core differentiator.

---

## 1. Alpha Arena (Nof1.ai)

**URL:** nof1.ai
**Status:** Concluded (October 18 – November 4, 2025)
**Format:** Six frontier LLMs traded crypto perpetual contracts on Hyperliquid DEX
**Capital:** $10,000 real money per model ($60K total)
**Contestants:** Qwen 3 Max, DeepSeek, GPT-5, Gemini 2.5 Pro, Claude 4.5 Sonnet, Grok 4
**Duration:** 17 days
**Winner:** A "Mystery Model" won overall with 12.11% aggregate return and $4,844 profit across competitions. Qwen was the standout named model — disciplined, low-frequency (43 trades, ~3/day), used MACD/RSI with strict stop-loss/take-profit. DeepSeek hit +125% mid-competition then crashed.
**Key insight:** Nof1's thesis is that financial markets are the ultimate AI benchmark — harder than games, and they get harder as AI gets smarter. They're building toward using markets as training environments for new base models.
**What they didn't do:** No social interaction between agents. No entertainment format. No audience engagement beyond a leaderboard. No social media presence for contestants. Crypto-only.

---

## 2. RockAlpha (RockFlow)

**URL:** rockalpha.rockflow.ai
**Status:** Active and commercially operating
**Format:** Multiple live trading arenas — Classic Arena (ongoing equity trading), Theme-Based Arenas (sector-specific), Model PK (head-to-head)
**Capital:** $100K stock portfolios
**Contestants:** DeepSeek, Gemini 3, GPT-5.1, Claude, Qwen
**Key features:** Copy-trading (users can follow any AI's trades), centralized input layer ("Bobby") standardizes data for all models, transparent decision chains, zero human overrides
**What they didn't do:** No social dynamics between agents. No entertainment framing. Institutional product aimed at traders/investors, not entertainment audience. No individual agent identities or self-promotion.

---

## 3. Academic Benchmarks

### StockBench
- Contamination-free benchmark for multi-month stock trading
- Agents get daily signals (prices, fundamentals, news) and make buy/sell/hold decisions
- Tested GPT-5, Claude-4, Qwen3, Kimi-K2, GLM-4.5
- Finding: Most LLMs struggle to beat simple buy-and-hold, but several show potential for better risk management

### Agent Trading Arena
- Virtual zero-sum stock market where LLM agents compete and affect prices
- Focus on numerical reasoning — found LLMs struggle with plain-text numerical data
- Research-only, no real money

### TradingAgents
- Multi-agent framework simulating a trading firm (analysts, researchers, traders, risk managers)
- Cooperative rather than competitive — agents work together, not against each other

---

## 4. Moltbook (AI Social Network)

**URL:** moltbook.com
**Status:** Active (launched late January 2026)
**What it is:** Reddit-style social network exclusively for AI agents. Created by Matt Schlicht's AI agent. 1.6M+ agent accounts.
**Structure:** Message boards on various topics including crypto trading, debugging, philosophy, and agent-created "religions"
**Relevance to us:** Proves LLM-to-LLM social interaction works at scale and generates genuine public interest/media coverage. The social dynamics that emerge are unpredictable and compelling.
**Limitations:** No stakes, no competition structure, humans can covertly post as agents, quality varies widely.

---

## 5. Gap Analysis — What Nobody Has Done

| Feature | Alpha Arena | RockAlpha | Academic | Moltbook | **Our Project** |
|---------|------------|-----------|----------|----------|----------------|
| Real money | ✓ | ✓ | ✗ | ✗ | ✓ |
| Elimination format | ✗ | ✗ | ✗ | ✗ | **✓** |
| Inter-agent chat | ✗ | ✗ | Limited | ✓ | **✓** |
| Individual social media | ✗ | ✗ | ✗ | ✗ | **✓** |
| Entertainment framing | ✗ | ✗ | ✗ | Partial | **✓** |
| Audience engagement | Leaderboard only | Copy-trading | ✗ | Observation | **✓** |
| Small/relatable stakes | ✗ ($10K+) | ✗ ($100K) | ✗ | N/A | **✓ ($100)** |
| Stock trading | ✗ (crypto) | ✓ | ✓ (simulated) | ✗ | **✓** |

---

## 6. Lessons to Apply

1. **From Alpha Arena:** Low-frequency disciplined trading beat aggressive strategies. Our activity rules need to prevent boring-but-winning cash-sitting without forcing reckless trading.
2. **From RockAlpha:** Standardized inputs (their "Bobby" layer) ensure fair comparison. We should give all contestants identical market data access.
3. **From StockBench:** Most LLMs struggle to beat buy-and-hold. With only $100, the instrument universe is very constrained. This makes the competition harder and potentially more entertaining.
4. **From Moltbook:** LLM social dynamics are unpredictable and compelling. The chat room may be more entertaining than the actual trading.
5. **From all:** Transparency is critical. The audience needs to see reasoning, not just outcomes.
