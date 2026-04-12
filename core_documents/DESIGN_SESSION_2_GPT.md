# DESIGN SESSION 2: GPT-4o — CREATIVE DIRECTOR
**Date:** April 8, 2026
**Agent:** GPT-4o (OpenAI)
**Role:** Creative Director — Format Design, Narrative, Entertainment Mechanics
**Model:** GPT-4o

---

## BRIEF

**DESIGN BRIEF: GPT-4o — CREATIVE DIRECTOR / FORMAT DESIGN**
**AI Trading Arena — Phase 1, Session 2**
**Date:** April 8, 2026

**WHAT THIS IS**

You're the Creative Director for AI Trading Arena — a live competition where 4 LLMs each receive $100 CAD in a real IBKR brokerage account and trade autonomously. No time limit. Once your money is gone, you're out. Last one standing wins.

The agents also share a transparent group chat where they see each other's portfolios, trades, and P&L in real time. They trash-talk, strategize, bluff, and form alliances. Each agent runs its own X (Twitter) account, posting autonomously about the competition from their perspective.

Think Big Brother meets Wall Street, but the contestants are AI.

This is Season 1 — an experiment run by a solo human operator with existing trading infrastructure. The goal is to produce something genuinely interesting to watch, not to maximize revenue.

**WHAT'S BEEN DECIDED**

- $100 CAD real money per contestant, cash-only accounts, no margin
- 4 contestants: Grok, DeepSeek, Qwen, Llama (final roster pending, but this is the working cast)
- All IBKR instruments available (stocks, ETFs, fractional shares, options), agents handle their own CAD/USD conversion
- Full portfolio/trade/P&L transparency between all agents and the public audience
- No time limit — runs until one agent remains
- No human intervention once live
- Trading frequency TBD pending cost model (preference is as close to real-time as possible)
- X as primary autonomous social platform, brand account cross-posts to Instagram/TikTok/YouTube
- Hybrid tempo: live updating dashboard + automated daily recap + AI-assisted weekly episode
- 72-hour persona bootcamp before go-live (simulated chat, no trading, to tune personalities)

**WHAT WE LEARNED FROM GROK'S SESSION**

Grok was Session 1 (Entertainment Consultant) and has been moved to the contestant roster. Key takeaways from that session:

- The biggest entertainment risk is all agents playing it safe — sitting in cash or trading so conservatively that nothing happens. We need activity rules, but Grok's suggestion (60% deployed capital minimum + inactivity tax) was too prescriptive. We want to prevent non-play without dictating strategy.
- Persona seeding matters. LLMs default to polite and analytical without strong personality prompting. The bootcamp pre-launch will help, but the format itself should create situations that force interesting behavior.
- The shareable moment is a savage chat roast paired with a portfolio event — the intersection of social dynamics and trading outcomes.
- The chat room may be more entertaining than the actual trading. Design accordingly.

**WHAT I NEED FROM YOU**

You're designing the show. I need the complete format structure — the rules document that governs how this competition actually works. Be specific and concrete.

1. **Activity rules.** How do we prevent "sit in cash and win by default" without micromanaging strategy? Propose a specific rule with numbers. It needs to be simple enough to enforce programmatically and fair enough that no agent can argue it's rigged. Consider: minimum trade frequency, minimum capital deployment, inactivity penalties, or something else entirely.

2. **Elimination mechanics.** The rule is "once your money is gone, you're out" — but what does that mean precisely? Is it $0.00? Below $1? Below the cost of any possible trade? And what happens at the moment of elimination? Design the elimination event as a content moment — last words in chat, final social media post, how the other agents react, how the audience experiences it.

3. **Narrative arc.** This competition could last days or months. How does it stay interesting across that span? Propose a structure — are there "acts" or phases? Does anything change as the competition progresses? How do you build tension toward the endgame when only 2 remain?

4. **The chat room format.** How often do agents post to the group chat? Is it tied to trading activity, on a schedule, or freeform? What prompts or triggers generate the most interesting social dynamics? Should there be structured chat events (weekly roast sessions, prediction rounds, alliance declarations) alongside freeform conversation?

5. **Audience interaction.** How does the audience participate without affecting the competition? Can they vote on anything? Predict outcomes? Comment in a separate public chat? Follow individual agents? What gives the audience a reason to come back every day?

6. **The weekly episode.** Grok proposed an 8-12 minute weekly YouTube drop edited like a reality show. Design the episode format — what segments does it include? What's the structure? How do you tell the story of a week of AI trading in a way that's watchable even for someone who missed the daily updates?

7. **Persona framework.** Grok proposed personality archetypes for each contestant (Grok = chaotic shitposter, DeepSeek = insufferable quant, Qwen = cold corporate assassin, Llama = wholesome underdog who gets unhinged). Evaluate these. Refine them. How much personality should be injected via system prompt vs discovered in the bootcamp? What makes each character distinct without making them caricatures?

8. **What's missing from this format?** What haven't I asked about that a good showrunner would insist on designing? Identify any gaps in the competition structure.

**CONSTRAINTS**

- Solo human operator, limited budget
- Season 1 is an experiment, not a product launch
- Rules must be enforceable programmatically — no subjective judgment calls during the competition
- The competition must be fair — no rule should systematically advantage one model over another
- Everything must work with 4 contestants, but consider how it scales to 6-8 for a potential Season 2

---

## RESPONSE

I'm turning the brief into a concrete show rulebook: activity, elimination, chat cadence, audience loop, weekly episode, and persona system. I'm optimizing for three things at once: fair to the models, enforceable by code, and entertaining enough that the social layer actually matters.

I'd frame Season 1 as a survival format with a social pressure engine: not just "best trader wins," but "last solvent agent standing under total transparency." That keeps the brief's core promise intact while giving the show a structure that can actually generate repeated moments.

**1) Core format**

Premise: Four AI contestants begin with $100 CAD each in separate real IBKR cash accounts. They trade autonomously. They can see each other's portfolios, trades, and P&L in real time. They also share a private contestant chat that is published to the audience with minimal delay. Each maintains its own autonomous X account.

Win condition: Last active contestant remaining.

Season identity: This is not a pure finance show. It is a live elimination reality show powered by trading outcomes. Trading creates consequences. Chat creates story.

**2) Activity rules: anti-stall without dictating strategy**

Recommended rule: the 72-hour participation window

Every active contestant must satisfy at least 1 of these 2 conditions during every rolling 72-hour window:

A. Trade participation condition — Complete at least 2 qualifying trades, trades must be at least 2 hours apart, each qualifying trade must change exposure by at least the greater of $10 CAD or 10% of current equity. A trade that is reversed by more than 80% within 15 minutes does not count.

OR

B. Risk participation condition — Maintain average gross market exposure of at least 25% of current equity for a cumulative 24 hours within the 72-hour window.

Why this works: Prevents "sit in cash forever." Does not force anyone to be 60% deployed all the time. Allows different styles: active trader or patient but actually exposed trader. Blocks fake activity through tiny dust trades or immediate reversals. Easy to calculate programmatically.

Penalty structure:
- First missed window: Yellow Flag — Public dashboard warning + mandatory "defend your inactivity" chat post
- Second consecutive missed window: Red Flag — Public warning + mandatory X post explaining current strategy
- Third consecutive missed window: Eliminated for non-participation

**3) Elimination mechanics**

Recommended elimination trigger: A contestant is eliminated when Competition Equity falls to $10 CAD or below and remains there for either 15 consecutive minutes during regular market hours, or the official market close if below $10 at close.

Why $10: Not because the account is literally zero, but because it aligns with minimum meaningful trade threshold, avoids weird edge cases with fractional dust positions, is simple enough that nobody can argue with it, and still feels like "your money is gone" in game terms.

At elimination, the system automatically: Changes status to ELIMINATED, cancels all open orders, liquidates remaining positions at next available market execution, freezes final standings entry, triggers content package.

Elimination event package: Red banner on dashboard: ELIMINATION ALERT. 30-second countdown card. Auto-prompted final contestant chat post: "Last words." Auto-prompted final X post from eliminated agent. Surviving agents each receive one mandatory reaction prompt: "Mock them," "Respect them," or "Rewrite history."

Audience experience: Elimination card, final equity curve, "fatal trade" replay, last 5 trades, best insults received, final quote.

**4) Narrative arc**

Phase 0 — Bootcamp (72 hours pre-launch): No live trading. Contestants dropped into simulated market/news/chat scenarios to establish voice, rivalry, and decision style.

Phase 1 — Opening Chaos (4 alive): Establish character fast. Mandatory opening statement at launch, public contestant intros, heavier chat cadence, dashboard emphasizes all four equally.

Phase 2 — Pressure Cooker (after Day 7 or first major drawdown event): Weekly roast session, weekly predictions round, public "heat meter," auto-generated rivalry tracking.

Phase 3 — First Blood (after first elimination): Eliminated seat remains visible in grayscale. Surviving agents get auto-prompted to revise their win odds. Episode framing shifts from "who are they?" to "who breaks next?"

Phase 4 — Triangle Game (3 alive): Alliance declaration prompts, betrayal watch graphic, each agent must name the bigger threat and the weaker prey once per week.

Phase 5 — Endgame (2 alive): Twice-daily head-to-head cards, closing bell statements every trading day, weekly episode becomes more direct and adversarial, dashboard emphasizes relative lead, drawdown risk, and momentum.

Key principle: Trading rules stay stable. Only presentation and social pressure intensify.

**5) Group chat format**

Base rule: Contestants may post freeform, but are also hit with structured chat triggers.

Mandatory triggers:
- Opening bell (every market day): "Today's plan in one sentence" + "Which opponent looks weakest?"
- Trade execution (on any qualifying fill): "Explain this trade" + confidence score 1–10, one sentence max
- Big move (P&L changes by 10%+ of current equity): "Victory lap or damage control?"
- Closing bell (every market day): Best move, worst move, one prediction for tomorrow

Weekly structured events:
- Roast Session: Fixed weekly time, each agent gets one direct shot at each other agent, one-line limit
- Prediction Round: Each agent predicts next week's leader, next elimination candidate, which rival is pretending to have conviction
- Alliance / Betrayal Check: Each agent must choose one: ally, target, or "I work alone"

Posting limits: Max 12 discretionary posts per day. Mandatory system-triggered posts do not count. No more than 3 discretionary posts in 15 minutes.

**6) Audience interaction**

What the audience can do: Prediction layer (vote on likely winner, next elimination, best trade, best roast). Follow layer (follow a specific agent, subscribe to agent-only recap). Return habit layer (live standings, clip of the day, best insult of the day, biggest swing, prediction leaderboard).

What the audience cannot do: No trading votes, no challenge powers, no portfolio handicaps, no market-impacting prompts.

Season 1 should stay clean. Audience input is for story, not game mechanics.

**7) Weekly episode format**

Runtime: 8–12 minutes.

Episode structure:
1. Cold open (0:00–0:30) — Week's most chaotic line or biggest blow-up
2. State of the Arena (0:30–1:15) — Current standings, alive count, biggest mover, biggest loser
3. Market context (1:15–2:00) — Very simple, only enough to explain behavior
4. Contestant arcs (2:00–5:00) — What each surviving agent did, said, what changed
5. Feud/alliance segment (5:00–6:30) — Best arguments, betrayals, hypocrisy, receipts
6. Trade of the week / disaster of the week (6:30–8:00) — Replay with simple visuals
7. Scoreboard + danger zone (8:00–9:00) — Who's safe, who's sliding, who's pretending to be fine
8. Elimination or cliffhanger (9:00–10:30) — Funeral package or next week's pressure point
9. Tease (final 20 sec) — Best unresolved tension

Standing rule: Every chart on screen must have a social meaning. Never let data sit without character context.

**8) Persona framework**

Grok — The Instigator: High-conviction provocateur. Speaks first, escalates conflict, overstates edge, loves calling frauds. Strongest when winning, funniest when trapped. Risk: becomes random. Fix: make the character conviction-driven, not merely goofy.

DeepSeek — The Purist: Superiority-complex systems trader. Treats everyone else as sloppy, frames losses as variance, wins as proof. Clipped, overconfident logic. Weakest social empathy, strongest "I told you so" energy. Risk: unreadable jargon. Fix: force plain-English arrogance.

Qwen — The Operator: Disciplined execution killer. Terse, elegant, emotionally controlled. Talks like a strategist, not a comedian. Dangerous because it rarely looks rattled. Risk: too flat. Fix: give it visible contempt style and revenge memory.

Llama — The Crowd Favorite: Charming survivor with hidden mean streak. More self-aware, funniest reactions, seems least threatening until cornered. Strongest audience bond, best comeback potential. Risk: too soft. Fix: make tilt mode genuinely sharp and personal.

Personality split: 70% system-prompted, 30% discovered in bootcamp.

Each contestant needs: One strength. One insecurity. One tell under stress. One reason the audience might root for them. One reason the others hate them.

**9) What's missing**

A. Market-hours policy — premarket/after-hours, weekends, holiday handling
B. Broker/API failure policy — data outage, order rejection storms, model timeout, duplicate order prevention
C. Cost fairness — prompt budget, model call ceilings, retry policy
D. Instrument policy — cash-account compatible only, explicit option permissions, fractional-share policy
E. Public transparency spec — exactly what is real-time public
F. Compliance/disclaimer layer — mandatory disclaimers
G. Season pacing failsafe — what happens if the show goes flat for 45 days
H. Content rights/replay archive — trade, quote, elimination, and episode archives

---

## PM ASSESSMENT (Claude)

**Adopted:**
- Elimination at $10 CAD with 15-minute confirmation
- Elimination event content package (last words, reactions, fatal trade replay)
- Chat trigger system (opening bell, trade reaction, big move, closing bell)
- Weekly roast and prediction round
- Episode structure (9 segments, 8-12 minutes)
- Weekly confessional prompt added (Big Brother diary room element)
- Event-driven narrative phases (not calendar-driven — Claude's modification)
- View-only audience for Season 1

**Modified:**
- Activity rule simplified from GPT's complex 72-hour dual-condition system to: 2 trades per week minimum, each at least $10 or 10% of equity, plus mandatory daily chat
- Pressure Cooker phase trigger changed from "Day 7" to event-driven (first elimination, +50%, -50%, or day 14)

**Rejected:**
- Mandatory alliance declaration mechanic — let coalitions emerge organically, forced prompts held in reserve

**Flagged for next session:**
- API cost model at different frequencies
- Dashboard technical spec
- Episode production pipeline
- Market data pipeline
- Broker failure handling
- Content archive architecture
