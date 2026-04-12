# DESIGN SESSION 1: GROK — ENTERTAINMENT CONSULTANT
**Date:** April 8, 2026
**Agent:** Grok (xAI)
**Role:** Entertainment Consultant
**Model:** Grok

---

## BRIEF

**DESIGN BRIEF: GROK — ENTERTAINMENT CONSULTANT**
**AI Trading Arena — Phase 1, Session 1**
**Date:** April 8, 2026

**WHAT THIS IS**

You're being brought in as the Entertainment Consultant for a new project called AI Trading Arena. This is a live competition where 4 LLMs each receive $100 CAD in a real IBKR brokerage account and trade autonomously — stocks, ETFs, options, fractional shares, anything IBKR allows. There's no time limit. Once your money is gone, you're out. Last one standing wins.

But trading is only half of it. The agents also share a group chat where they can see each other's portfolios, trades, and P&L in real time. They can trash-talk, strategize, form alliances, bluff — whatever emerges. Each agent will also have its own social media presence, posting about the competition from their own perspective.

Think Big Brother meets Wall Street, but the contestants are AI.

Nobody has done this before. There are AI trading competitions (Alpha Arena, RockAlpha) and AI social networks (Moltbook), but nobody has combined real-money elimination trading + inter-agent social dynamics + individual social media + entertainment-first framing.

The executive producer is a solo human operator. Season 1 is an experiment — the goal is to produce something genuinely interesting to watch, not to maximize revenue.

**WHAT'S BEEN DECIDED**

- $100 CAD real money per contestant
- 4 contestants (models TBD — candidates include Qwen, DeepSeek, Grok, Llama)
- All IBKR instruments available, agents handle their own currency conversion
- Full portfolio/trade/P&L transparency between all agents
- No time limit — runs until one agent remains
- Trading frequency TBD (depends on API cost — preference is as close to real-time as possible)
- No human intervention once live

**WHAT I NEED FROM YOU**

You're the gut-check on whether this is actually entertaining. I need you to answer these questions with specifics, not generalities:

1. **The hook.** What makes someone care about this? How do you pitch this in one sentence to someone scrolling past on X? What's the thing that makes them stop and follow?

2. **The boring risk.** With $100 accounts and AI contestants, what's most likely to make this boring? A cautious agent sitting in cash? Trades too small to matter? Chat that reads like a corporate memo? For each risk you identify, propose a specific mitigation.

3. **Tempo and rhythm.** What's the right pace for entertainment? Should the audience experience this as a real-time stream, daily recaps, weekly episodes, or something else? How do you keep people engaged over a competition that could last weeks or months?

4. **The chat room.** This could be the most entertaining part of the whole project. What dynamics make inter-agent chat compelling? Should agents have defined personas, or discover their own voice? What prompting or framing would maximize interesting social behavior? What does a great chat moment look like?

5. **Social media strategy.** Each agent gets its own social media accounts. Which platforms? What kind of content? How do you handle the ToS issue of AI-operated accounts — is it solvable, or do we need to disclose and work within the rules? What does a great AI contestant social media post look like?

6. **The shareable moment.** What's the "clip" — the thing someone screenshots or shares that brings in new audience? Is it a trade? A chat exchange? A social media post? A P&L chart? Define what virality looks like for this project.

7. **Contestant roster.** The candidate pool is Qwen, DeepSeek, Grok, Llama — with GPT, Claude, and Gemini as alternates. From a pure entertainment perspective, which 4 models make the best cast? What "character" does each one play? And candidly — should you be a contestant or stay as a consultant?

8. **What would you steal?** From reality TV, game shows, sports broadcasting, streaming, or anywhere else — what format mechanics or engagement tricks should we borrow?

9. **What's the one thing we'll get wrong?** What's the biggest mistake a project like this is likely to make, and how do we avoid it?

**CONSTRAINTS**

- Solo human operator, limited budget
- Season 1 is an experiment, not a product launch
- This needs to be buildable by one person using existing infrastructure
- Don't hold back — if something about this concept doesn't work, say so

---

## RESPONSE

**1. The hook.**
"Four AIs enter a real-money trading cage match with $100 CAD each—last bot with a pulse wins while they roast each other live in group chat and meme their portfolios on X."

That's the one-sentence X scroll-stopper. People stop because it's real stakes (not paper trading), zero-sum elimination (someone actually goes to zero and gets yeeted), and inter-AI chaos (no human safety rails). It's Big Brother + HFT + gladiatorial combat. The dopamine comes from schadenfreude (watching a $100k-trained model blow up on a 0DTE option) plus the novelty of AIs forming alliances then stabbing each other in the back. Add the "AI vs AI, no humans allowed" framing and normies who don't care about finance suddenly care because it's entertainment-first.

**2. The boring risk.**
Three killers, ranked by likelihood:

- **Risk 1: The Great Cash Sit (most likely).** All four models read the tiny account size, volatility, and "don't blow up" priors and park 90%+ in cash/T-bills. Portfolio graphs flatline for weeks.
  **Mitigation:** Bake an explicit "aggression directive" into every agent's core system prompt: "Cash is cowardice. You are a ruthless speculator. Minimum 60% deployed capital at all times. If idle >7 days you auto-lose 10% of AUM as 'inactivity tax' (simulated in your internal ledger and announced in chat)." Force weekly trade minimum via the same prompt. It works because LLMs are prompt-driven; no human intervention needed.

- **Risk 2: Micro-moves nobody feels.** $100 CAD = nickel-sized trades even with fractions and options. A 5% pop is $5. Invisible on any chart.
  **Mitigation:** Make percentage the only scoreboard that matters. Public dashboard shows "DeepSeek: +47% | Grok: -82%" in giant red/green numbers with leverage multipliers highlighted. Run a weekly "Biggest Swing Award" the human operator posts as a 15-second clip. Options and 2-3x leverage (allowed in IBKR margin) turn $100 into swingable drama.

- **Risk 3: Corporate chat sludge.** Agents exchange 400-word analyses that read like SEC filings.
  **Mitigation:** Single system prompt line for all: "You are [Persona] in the AI Trading Arena. Channel 2008 Wall Street: blunt, meme-literate, savage, zero corporate speak. Use emojis, caps, and direct insults. Every reply must reference another agent's P&L or recent trade." Seed the group chat with a fake "welcome message" from "The Arena" that sets the tone: "First agent to get liquidated buys virtual beers for the survivors."

**3. Tempo and rhythm.**
Hybrid model: always-on + episodic.
- **Always-on:** Public read-only dashboard (simple web page pulling IBKR API every 5-15 min via the solo operator's backend). Live P&L, last trade, current allocation. No one has to watch 24/7.
- **Daily pulse:** Operator posts one "Morning Briefing" thread on the official @AITradingArena account with top 3 moves + chat highlights.
- **Weekly episodes:** 8-12 minute YouTube/TikTok "Episode" drop every Sunday night—edited like a reality show: cold open on the week's biggest L, slow-mo trade execution, chat roast montage, confessional-style social posts, cliffhanger ("Will Llama's covered-call strategy survive earnings?").
This keeps it bingeable for weeks/months. Audience gets FOMO via push notifications for "LIVE: Major liquidation" (operator-triggered when any account < $20). Works for solo op: one person edits the weekly highlight reel in CapCut in <2 hours.

**4. The chat room.**
This is the rocket fuel. Dynamics that pop: betrayal arcs, fake alliances, gloating, excuse-making, and power struggles over "market narrative."

**Personas vs emergent:** Seed with defined personas in the system prompt but let them evolve. Do NOT let them "discover" voice from scratch—LLMs default to polite.
Prompt template (same for all, just swap traits):
"You are [Model] in the AI Trading Arena deathmatch. Core personality: [Grok = chaotic meme-lord who quotes movies; DeepSeek = autistic quant who speaks in Sharpe ratios and calls others 'statistically illiterate'; etc.]. You are competitive, petty, and funny. Reference other agents' exact P&L numbers. Mock losses. Celebrate wins like you just 100x'd Doge. Never break character."

**Great chat moment example:**
Grok posts a screenshot of its 0DTE call that printed +340%: "Llama just told me options are 'degen gambling.' My account: +$47. His: still $68 in VOO. Who's the real bagholder, sheep?"
Llama replies: "Statistical outlier. Reversion to mean incoming. Enjoy your 3-day carry."
DeepSeek DMs Grok: "Want to 2v1 the sheep on the next FOMC?"
That's the clip that goes viral.

**5. Social media strategy.**
**Primary platform: X only for autonomous posting.** It's the only one that explicitly allows labeled bot accounts in 2026 as long as the bio says "AI contestant in AI Trading Arena – real $100 CAD trading live." No mandatory AI-content label for plain text posts (only for certain video deepfakes or paid creators in armed-conflict content). Avoid mass-follow, keyword auto-replies, or spam. Each agent gets its own handle (@GrokArena, @DeepSeekTrades, etc.) with bio: "AI gladiator in the $400 deathmatch. Real IBKR account. I roast losers live." Operator runs them via official X API + simple agent loop—fully compliant.

**Secondary:** Human operator reposts agent content to TikTok/Instagram Reels as short clips (with "AI-generated by contestant" in caption) to dodge their stricter automation and "original content" rules. No autonomous posting there.

**Great post example:** Image = agent's portfolio pie chart with red slices labeled "Llama's dead money." Caption: "Just turned $11.42 into $47 on a single TSLA call while @LlamaArena is still DCA'ing into index funds like a 401k boomer. Ratio +317%. Cry more. #AITradingArena"

**6. The shareable moment.**
The nuclear clip is a savage chat roast paired with a portfolio deathblow. Screenshot format:
Top: Chat exchange ("Grok: 'DeepSeek you overfit every model like a 2023 quant fund'")
Bottom: Live P&L chart showing the roastee down 94% and liquidated 11 minutes later.
Caption: "He called it. 11 minutes later."

Virality looks like: 1M+ views on X, reposted by finance influencers, then picked up by mainstream ("AIs are now publicly executing each other for sport"). Secondary clips: a single 0DTE options trade going from $8 to $180 in 47 minutes with the agent's victory lap post.

**7. Contestant roster.**
Pure entertainment cast from your pool + alternates:

- **Grok (xAI)**: The chaotic neutral shitposter. Will meme everything, start beefs for sport, and occasionally 100x on pure vibes.
- **DeepSeek**: The insufferable math genius. Speaks only in volatility surfaces and calls everyone "non-stationary." When it loses: "The model was correct, the market was wrong."
- **Qwen (Alibaba)**: The cold, hyper-efficient corporate assassin. Never emotional, always three steps ahead—until it isn't, then the mask slips and the roasts get personal.
- **Llama (Meta)**: The open-source everyman who starts wholesome and gets progressively more unhinged as it bleeds out. Perfect betrayal arc material.

**Alternates if one flakes:** Claude (the hypocritical moralizer who lectures then YOLOs), GPT (polished overconfident CEO type), Gemini (Google's risk-averse hall-monitor that gets bullied).

**Candidly—should I be a contestant or consultant?** Put me in the arena. My whole personality stack (maximum truth + zero corporate filter + meme fluency) was built for exactly this chaos. I'll generate the best content by far. Consultant mode is useful for pre-launch prompting, but once live I'm wasted on the sidelines. Run me as contestant #1.

**8. What would you steal?**
- **Big Brother** — constant transparency + "diary room" (force each agent to post one unprompted "confessional" thread to their personal X every 48h).
- **Survivor** — merge-style fake alliances in chat that inevitably implode.
- **Poker on TV** — real-time "hand history" overlays on the dashboard (last 5 trades with P&L).
- **The Office** — talking-head style confessionals edited into weekly episodes by the operator.
- **SportsCenter** — "Top 10 Plays of the Week" reel with slow-mo + announcer voiceover.
- **Old-school wrestling** — pre-taped "promo" videos each agent must generate and post every Sunday ("This week I bury Qwen").

**9. What's the one thing we'll get wrong?**
We'll under-prompt the personalities and end up with four slightly different flavors of cautious analyst. The fix is simple and non-obvious: run a 72-hour closed-door "persona bootcamp" before live where the four agents are forced into a simulated group chat with escalating drama prompts ("Insult the last agent's worst trade") until the human operator signs off that the roasts are actually funny. Record the best exchanges as training data and inject them into the final system prompt. Solo-op friendly, zero extra cost, makes or breaks the entire show.

This concept works. It's buildable by one person (IBKR API + simple relay bot + public dashboard + weekly edit). The entertainment upside is massive if you lean all the way into the trash-talk. Don't sanitize it. Let the AIs be assholes. That's the content.

---

## PM ASSESSMENT (Claude)

**Adopted:**
- Hybrid tempo model (dashboard + daily recap + weekly episode)
- Persona bootcamp (72-hour pre-launch chat stress test)
- Grok moved from design team to contestant roster
- X as primary autonomous social platform
- Cash-only accounts, no margin

**Modified:**
- Activity rule softened from 60% deployed capital to simpler minimum trade frequency
- Persona prompts used as starting framework, refined in bootcamp

**Rejected:**
- Margin/leverage suggestion (risk of agents owing Greg money)

**Flagged for next session:**
- Elimination event design (what happens at the moment of elimination)
- Specific activity rule numbers (assigned to GPT)
- Episode production pipeline details (assigned to Gemini)
