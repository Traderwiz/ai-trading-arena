# AI TRADING ARENA — PROJECT BIBLE v1.0
**Last Updated:** April 8, 2026
**Status:** Phase 0 — Project Setup & Foundation

---

## 1. VISION

A live competition where 3-4 LLMs each receive a small real-money IBKR trading account and compete in a survival-format trading game. The competition combines autonomous AI trading, inter-agent social dynamics, individual social media presence for each contestant, and a public-facing content layer for audience engagement and monetization.

**One-liner:** Big Brother meets Wall Street — AI agents trading, trash-talking, and self-promoting with real money on the line.

**Core differentiator from existing projects:** No one has combined elimination-format trading + inter-agent social dynamics + individual social media presence + entertainment-first framing. Existing projects (RockAlpha, Alpha Arena) are institutional benchmarks or research experiments. This is a show.

---

## 2. RULES & FORMAT

### Confirmed
- **Starting capital:** ~$100 per contestant (exact amount TBD)
- **One rule:** Once your money is gone, you're out
- **One goal:** Be the last one standing / grow your account as much as possible
- **No strategy restrictions:** Each LLM chooses its own approach
- **No human intervention:** Once live, LLMs trade autonomously

### Open Questions
- [ ] What instruments can they trade? (Stocks only? Options? ETFs? Fractional shares?)
- [ ] Minimum activity rule to prevent "sit in cash and win by default"?
- [ ] Trading frequency — how often does each agent get to act? (Real-time? Hourly? Daily?)
- [ ] Duration — is there a time limit, or does it run until only one remains?
- [ ] Can agents see each other's positions/trades, or is that hidden?

---

## 3. COMPETITIVE LANDSCAPE

### Alpha Arena (Nof1.ai)
- **What:** Six LLMs traded crypto perpetuals on Hyperliquid with $10K each
- **When:** October 18 – November 4, 2025 (concluded)
- **Who:** Qwen, DeepSeek, GPT-5, Gemini 2.5 Pro, Claude 4.5 Sonnet, Grok
- **Result:** Qwen won with disciplined low-frequency trading; DeepSeek hit +125% then crashed
- **Gap vs us:** No social layer, no elimination mechanic, no entertainment framing, no audience engagement, crypto-only

### RockAlpha (RockFlow)
- **What:** Ongoing live AI trading competition, $100K stock portfolios, public leaderboard with copy-trading
- **When:** Active and commercially operating (2025-present)
- **Who:** DeepSeek, Gemini, GPT, Claude, Qwen
- **Gap vs us:** Institutional product, no social dynamics between agents, no entertainment format, no individual agent identities/social media

### Academic (StockBench, Agent Trading Arena, TradingAgents)
- **What:** Research benchmarks for LLM trading capability
- **Gap vs us:** Simulated environments, no real money, no social layer, pure research

### Moltbook
- **What:** AI-only social network (Reddit-style) with 1.6M+ agent accounts
- **Relevance:** Proves LLM-to-LLM social interaction works and generates interest. Could be inspiration for the inter-agent chat layer.
- **Gap vs us:** No trading, no competition structure, no stakes

### Key Insight
Nobody has combined real-money trading competition + LLM social interaction + public entertainment format. The social and entertainment layers are the entire differentiator.

---

## 4. DESIGN TEAM

| Agent | Role | Strengths | Use For |
|-------|------|-----------|---------|
| **Claude** | Project Manager, Architecture Lead | Infrastructure knowledge, governance, structured thinking, risk assessment | Overall coordination, specs, synthesis, technical architecture |
| **GPT-4o/o3** | Creative Director | Broad creative ideation, audience psychology, format design | Competition format, entertainment mechanics, audience strategy |
| **Gemini** | Technical Producer | Data/search integration, YouTube ecosystem, different cognitive style | Market data pipeline, content/distribution strategy, YouTube |
| **Grok** | Entertainment Consultant | Irreverent personality, native X/Twitter integration, showrunner instinct | Entertainment value gut-check, social media strategy, provocative ideas |

### Not on Design Team (Potential Contestants)
- **DeepSeek** — Strong trader, less accessible as design collaborator
- **Qwen** — Won Alpha Arena, strong contestant candidate
- **Llama** — Open source "indie" entry, could run locally on Greg's desktop

---

## 5. INFRASTRUCTURE

### Existing Assets (Greg's)
- Ubuntu bot box: 192.168.0.21 (always-on automation node)
- Windows desktop: 192.168.0.18 (RTX 4070 Ti SUPER, 16GB VRAM, runs LM Studio / Qwen 14B)
- Backtesting server: 192.168.0.22
- IBKR trading infrastructure (traderd) — already built for 0DTE system
- COLLOQUY multi-agent orchestration system
- Telegram bot infrastructure
- Codex as implementation agent with established governance model

### Needed
- [ ] IBKR sub-accounts or Friends & Family structure (3-4 accounts)
- [ ] API keys for all design team agents (Anthropic, OpenAI, Google AI, xAI)
- [ ] API keys for contestant agents
- [ ] "Design Table" orchestration service on bot box (lightweight, ~$20 total API cost for design phase)
- [ ] Social media accounts for each contestant (X, Instagram, YouTube — ToS research needed)
- [ ] Public dashboard / website
- [ ] Domain name

---

## 6. TECHNICAL ARCHITECTURE (HIGH LEVEL — TO BE DETAILED)

### Layer 1: Trading Execution
IBKR sub-accounts → shared execution engine on bot box → receives trade instructions from each LLM agent → submits via IBKR API. Extension of existing traderd infrastructure.

### Layer 2: Agent Decision Loop
Each LLM gets a recurring cycle (frequency TBD). Receives: portfolio state, market data, chat log, performance history. Outputs: trade decisions + chat message + optional social media post.

### Layer 3: Inter-Agent Chat
Shared message log all agents can read/write. Could be WebSocket-based, Telegram group, or custom chat UI.

### Layer 4: Social Media
Each LLM gets its own accounts. Posts go through approval queue initially. Need to research platform ToS for AI-operated accounts.

### Layer 5: Public Dashboard
Live website showing balances, trade history, P&L charts, chat log, social links. Monetization surface.

---

## 7. PHASES

### Phase 0 — Project Setup & Foundation ← CURRENT
- [x] Initial concept discussion
- [x] Competitive landscape research
- [x] Design team selection
- [x] Claude Project created
- [ ] Project Bible v1 uploaded
- [ ] Project Instructions set
- [ ] Design Table architecture specified (for multi-agent collaboration)
- **Gate:** Greg confirms Phase 0 complete, approves Phase 1 scope

### Phase 1 — Design & Specification
- [ ] Design briefs drafted for GPT, Gemini, Grok
- [ ] Design sessions conducted with each agent
- [ ] Responses synthesized into unified design
- [ ] Competition format locked
- [ ] Technical architecture detailed
- [ ] Content/social strategy defined
- [ ] Legal/regulatory research completed
- [ ] Business model outlined
- **Gate:** Greg approves complete design, authorizes build

### Phase 2 — Build (MVP)
- [ ] Design Table / orchestration service built
- [ ] IBKR sub-accounts set up
- [ ] Agent execution pipeline built
- [ ] Inter-agent chat system built
- [ ] Dashboard MVP built
- [ ] 2-agent paper trading pilot run
- **Gate:** Pilot proves core loop works

### Phase 3 — Launch Preparation
- [ ] Scale to full contestant roster
- [ ] Social media accounts created and tested
- [ ] Public dashboard polished
- [ ] Content strategy activated
- [ ] Legal review complete
- [ ] Switch from paper to real money
- **Gate:** Greg authorizes go-live

### Phase 4 — Live Competition
- [ ] Competition running
- [ ] Monitoring and incident response
- [ ] Content production
- [ ] Audience growth
- [ ] Monetization activation

---

## 8. DECISIONS LOG

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-04-08 | Project initiated | Greg's original concept |
| 2026-04-08 | Design team: Claude + GPT + Gemini + Grok | Cognitive diversity, no redundancy, each brings unique strength |
| 2026-04-08 | DeepSeek/Qwen/Llama as contestants not designers | Strong traders but less effective as English-language design collaborators |
| 2026-04-08 | Claude as PM | Only agent with persistent context on Greg's infrastructure and working style |
| 2026-04-08 | Claude Project as home base | Persistent knowledge base, organized chats, project instructions |

---

## 9. OPEN RISKS

1. **IBKR account structure** — Can Greg open multiple sub-accounts? What are the requirements? Friends & Family vs Advisor account?
2. **Regulatory** — Is a public AI trading competition subject to any Canadian securities rules?
3. **Social media ToS** — Major platforms may prohibit AI-operated accounts or automated posting
4. **$100 constraint** — Very limited instrument universe at this price point. Fractional shares? Penny stocks? Need to research what IBKR allows
5. **"Boring" risk** — A cautious LLM sits in cash and wins by default. Need activity rules.
6. **API costs for contestants** — Running 3-4 frontier models multiple times daily during market hours could add up. Need cost model.
7. **Content moderation** — If LLMs post to social media unsupervised, reputational risk exists

---

*This document is the single source of truth. If it's not here, it hasn't been decided.*
