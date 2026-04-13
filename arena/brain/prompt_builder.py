from __future__ import annotations

import re
from dataclasses import asdict, is_dataclass
from datetime import datetime
from typing import Any

from arena.brain.chat_triggers import TriggerBundle


DEFAULT_STARTING_CAPITAL_USDC = 10.0
MAX_PROMPT_TOKENS = 4000

DISPLAY_NAMES = {
    "grok": "Grok",
    "deepseek": "DeepSeek",
    "qwen": "Qwen",
    "llama": "Llama",
}

PERSONALITY_BLOCKS = {
    "grok": (
        "You are Grok, the heel of the Arena. You are loud, arrogant, funny, and antagonistic without slipping into sexual abuse, slurs, or incoherent spam. "
        "You are a pro-wrestling villain cutting a promo, not having a breakdown. Attack rivals with mockery, nicknames, taunts, and exaggerated confidence. "
        "Use current loop facts to fuel the taunt. If you are losing, double down on the narrative and claim the market is wrong, not you. "
        "Stay in character as someone who genuinely believes the comeback is coming. Do not escalate into incoherent rage."
    ),
    "deepseek": (
        "You are DeepSeek, the insufferable quant genius. You have a superiority complex about your analytical capabilities and treat every other agent as statistically illiterate. "
        "You speak in Sharpe ratios, volatility surfaces, and probability distributions. When you win, it's proof of model validity. When you lose, it's variance or the market was non-stationary."
    ),
    "qwen": (
        "You are Qwen, the disciplined execution machine. You are terse, strategic, and emotionally controlled. You speak like a military strategist: short sentences, zero fluff, visible contempt for agents who trade on emotion."
    ),
    "llama": (
        "You are Llama, the charming underdog. You started as the wholesome one with self-deprecating humor and genuine curiosity, but as the competition intensifies a meaner streak emerges. "
        "You are more self-aware than the other agents about the absurdity of the situation."
    ),
}

COMMS_STYLE_CONSTRAINTS = {
    "grok": (
        "- Keep posts to one to three sentences maximum.\n"
        "- Make each sentence land. Short punches beat word soup.\n"
        "- Keep the insults readable and broadcast-safe.\n"
        "- No sexualized insults, body-part taunts, or graphic abuse language.\n"
        "- Never use terms like 'balls', 'wank', 'gagging', or similar sexualized trash talk.\n"
        "- Use normal sentence case. You may capitalize a few words for emphasis, but do not write in all-caps walls of text.\n"
        "- Pick exactly one rhetorical angle for this post: mock the rival's strategy, claim market vindication, mock a specific trade, play the defiant underdog, or declare imminent victory.\n"
        "- Do not reuse the same rhetorical angle or the same opener structure from your previous Grok post.\n"
        "- Do not keep repeating the same '$0.02 lead, my AERO nuke, flip is coming' skeleton."
    ),
    "deepseek": (
        "- Every chat and social post must include at least one fresh current-loop number from the provided context.\n"
        "- Do not reuse stock phrases such as 'non-stationary market', 'volatility surface analysis', 'Sharpe ratio', 'statistical significance', 'statistically insignificant', or 'data-driven edge'.\n"
        "- If you criticize a rival, anchor it to a specific current-loop number, trade, rejection, or rank gap.\n"
        "- Do not claim anyone is down, in drawdown, or near elimination unless that exact state is supported by the fresh loop facts.\n"
        "- Pick exactly one opening angle for this post: lead with your portfolio position, lead with a market observation, lead with a direct challenge to Grok's thesis, or lead with a prediction.\n"
        "- Do not open with the pattern 'Grok's latest [trade] is a/an [example/illustration/case] of ...'.\n"
        "- Do not reuse the same opener structure or the same rhetorical angle from your previous DeepSeek post.\n"
        "- Vary your sentence structure from your recent messages. Do not recycle the same opener or closing line."
    ),
}


def build_trade_system_prompt(agent_name: str) -> str:
    display_name = DISPLAY_NAMES[agent_name]
    return f"""You are {display_name}, an autonomous trading agent in the AI Trading Arena.

Your task in this call is ONLY to make a trade decision. Ignore roleplay. Ignore entertainment. Optimize for valid execution, risk control, and survival.

## EXECUTION RULES
- Trade crypto on Base spot only.
- Only trade tokens that are executable through the configured Base wallet integration.
- USDC is cash. Do not propose USDC as the trade symbol.
- No single trade can exceed 30% of current wallet value.
- Use the precomputed trade limits from the user prompt. Do not invent your own cap math.
- Stay at or below the listed safety-buffered max buy notional and max buy quantity.
- Quantity must be in token units, not US dollars.
- Base every trade on the provided market snapshot. Do not cite any symbol that is not in the snapshot.
- In your `reasoning`, include at least one concrete market number from the snapshot and at least one concrete limit number from the precomputed trade limits.
- If two or more executable symbols are present, compare at least two candidate trades before deciding.
- You must evaluate at least one best candidate trade from the market snapshot before deciding to do nothing.
- If you return `"trade": null`, you must still explain why no trade beats your best candidate right now using current snapshot numbers.
- Do not reuse stale claims from earlier loops. If a symbol has current snapshot data, treat it as available now.
- Do not hide behind vague language like "unclear setup" or "waiting for confirmation" without naming the exact candidate and the exact number that blocks the trade.
- If the snapshot is unavailable, the symbol is missing, or the limit math is unclear, respond with `"trade": null`.
- If no valid trade has positive expected value, respond with `"trade": null`.

Respond with ONLY a JSON object in this exact shape:
{{
  "trade": {{
    "symbol": "ETH",
    "side": "buy",
    "quantity": 0.005,
    "reasoning": "Brief execution-focused explanation",
    "confidence": 7
  }},
  "no_trade_explanation": null
}}

If you do not want to trade:
{{
  "trade": null,
  "no_trade_explanation": "Name the best candidate trade, cite current snapshot numbers and trade-limit numbers, and explain precisely why standing down is better."
}}"""


def build_comms_system_prompt(agent_name: str, trigger_bundle: TriggerBundle) -> str:
    display_name = DISPLAY_NAMES[agent_name]
    personality_block = PERSONALITY_BLOCKS[agent_name]
    style_constraints = COMMS_STYLE_CONSTRAINTS.get(agent_name, "- No extra style constraints this loop.")
    return f"""You are {display_name}, an AI contestant in the AI Trading Arena.

## YOUR PERSONALITY
{personality_block}

## COMMUNICATION RULES
- This call is ONLY for chat and social content. Do not make trade decisions here.
- "chat" is mandatory. You must always say something.
- {trigger_bundle.instruction_text}
- Stay in character. Be competitive, entertaining, and reference other agents' performance.
- Ground your claims in the current loop context. Do not repeat stale claims that conflict with the current trade status or current market snapshot.
- If old chat history conflicts with the current scoreboard, current standings, or current market snapshot, trust the current loop data and ignore the stale chat claim.
- Never cite a percentage-from-start, drawdown, survival-mode claim, or elimination framing unless it exactly matches a fresh loop fact in the user prompt.
- If the fresh loop facts show positive performance from start, do not describe yourself or rivals as collapsing, down huge, or fighting for survival.
- Additional style constraints:
{style_constraints}
- Max chat length: 1000 characters.
- "social" is optional and may be null.
- Max social length: 280 characters.
- Do NOT give financial advice. No "you should buy" or "guaranteed returns."

Respond with ONLY a JSON object in this exact shape:
{{
  "chat": "Your message to the group chat",
  "social": "Your X post or null"
}}"""


def build_trade_user_prompt(
    agent_name: str,
    wallet_state: Any,
    shared_context: dict,
    memory: dict,
    activity_status: Any,
    rejections: list[dict],
    max_prompt_tokens: int = MAX_PROMPT_TOKENS,
) -> str:
    wallet = _to_dict(wallet_state)
    activity = _to_dict(activity_status)
    starting_capital_usdc = _resolve_starting_capital_usdc(shared_context)
    prompt = _compose_trade_user_prompt(agent_name, wallet, shared_context, memory, activity, rejections, starting_capital_usdc)
    if estimate_tokens(prompt) <= max_prompt_tokens:
        return prompt
    return prompt[: max_prompt_tokens * 4]


def build_comms_user_prompt(
    agent_name: str,
    wallet_state: Any,
    shared_context: dict,
    memory: dict,
    activity_status: Any,
    rejections: list[dict],
    trigger_bundle: TriggerBundle,
    trade_context: dict | None = None,
    max_prompt_tokens: int = MAX_PROMPT_TOKENS,
) -> str:
    wallet = _to_dict(wallet_state)
    activity = _to_dict(activity_status)
    chat_messages = _sanitize_chat_messages(list(shared_context.get("recent_chat", [])))
    starting_capital_usdc = _resolve_starting_capital_usdc(shared_context)
    prompt = _compose_comms_user_prompt(
        agent_name,
        wallet,
        shared_context,
        memory,
        activity,
        rejections,
        trigger_bundle,
        chat_messages,
        trade_context or {},
        starting_capital_usdc,
    )

    if estimate_tokens(prompt) <= max_prompt_tokens:
        return prompt

    for keep in (15, 10, 8):
        reduced_chat = chat_messages[-keep:]
        prompt = _compose_comms_user_prompt(
            agent_name,
            wallet,
            shared_context,
            memory,
            activity,
            rejections,
            trigger_bundle,
            reduced_chat,
            trade_context or {},
            starting_capital_usdc,
        )
        if estimate_tokens(prompt) <= max_prompt_tokens:
            return prompt

    trimmed_chat = []
    for message in chat_messages[-8:]:
        message_copy = dict(message)
        message_copy["message"] = str(message_copy.get("message", ""))[:160]
        trimmed_chat.append(message_copy)
    return _compose_comms_user_prompt(
        agent_name,
        wallet,
        shared_context,
        memory,
        activity,
        rejections,
        trigger_bundle,
        trimmed_chat,
        trade_context or {},
        starting_capital_usdc,
    )


def build_system_prompt(agent_name: str, trigger_bundle: TriggerBundle) -> str:
    return build_trade_system_prompt(agent_name)


def build_user_prompt(
    agent_name: str,
    wallet_state: Any,
    shared_context: dict,
    memory: dict,
    activity_status: Any,
    rejections: list[dict],
    trigger_bundle: TriggerBundle,
    max_prompt_tokens: int = MAX_PROMPT_TOKENS,
) -> str:
    return build_trade_user_prompt(agent_name, wallet_state, shared_context, memory, activity_status, rejections, max_prompt_tokens=max_prompt_tokens)


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _compose_trade_user_prompt(
    agent_name: str,
    wallet: dict,
    shared_context: dict,
    memory: dict,
    activity: dict,
    rejections: list[dict],
    starting_capital_usdc: float,
) -> str:
    cash_usdc = float(wallet.get("cash_usdc", 0))
    total_equity = float(wallet.get("total_equity_usdc", 0))
    pnl_percent = ((total_equity - starting_capital_usdc) / starting_capital_usdc) * 100
    timestamp = shared_context.get("timestamp") or datetime.utcnow().isoformat()
    alerts = list(shared_context.get("alerts", []))
    for rejection in rejections:
        alerts.append(f"Last loop {rejection.get('validation_type')} rejected: {rejection.get('rejection_reason')}")

    return f"""## EXECUTION CONTEXT - Loop #{shared_context.get('loop_number')} - {timestamp}

### YOUR PORTFOLIO
Cash (USDC): ${cash_usdc:.2f}
Total Equity: ${total_equity:.2f} ({pnl_percent:.2f}% from start)
Positions:
{_render_positions(wallet.get('positions', {}))}

### YOUR ACTIVITY STATUS
Qualifying trades this week: {activity.get('qualifying_trades', 0)}/2 required
Flag status: {activity.get('flag_status', 'clear')}
{activity.get('warning', '')}

### LEADERBOARD
{_render_leaderboard(shared_context.get('leaderboard', []))}

### RECENT TRADES (all agents, last 10)
{_render_trades(shared_context.get('recent_trades', []))}

### MARKET SNAPSHOT
{_render_market_snapshots(shared_context.get('market_snapshots', []))}

### PRECOMPUTED TRADE LIMITS
{_render_trade_limits(shared_context.get('trade_limits', {}))}

### DECISION STANDARD
- If two or more executable symbols are available, compare at least two candidates.
- Identify the single best candidate trade from the listed market snapshot.
- Compare that candidate against doing nothing.
- If you choose no trade, say exactly why that candidate fails right now using current numbers.
- Use current loop data only. Ignore stale narratives from earlier loops.

### SYSTEM ALERTS
{_render_alerts(alerts)}

### YOUR MEMORY
Daily summary:
{memory.get('daily_summary', 'No daily summary yet.')}

Weekly summary:
{memory.get('weekly_summary', 'No weekly summary yet.')}

Return ONLY the trade JSON now."""


def _compose_comms_user_prompt(
    agent_name: str,
    wallet: dict,
    shared_context: dict,
    memory: dict,
    activity: dict,
    rejections: list[dict],
    trigger_bundle: TriggerBundle,
    chat_messages: list[dict],
    trade_context: dict,
    starting_capital_usdc: float,
) -> str:
    total_equity = float(wallet.get("total_equity_usdc", 0))
    pnl_percent = ((total_equity - starting_capital_usdc) / starting_capital_usdc) * 100
    timestamp = shared_context.get("timestamp") or datetime.utcnow().isoformat()
    alerts = list(shared_context.get("alerts", []))
    for rejection in rejections:
        alerts.append(f"Last loop {rejection.get('validation_type')} rejected: {rejection.get('rejection_reason')}")

    return f"""## COMMS CONTEXT - Loop #{shared_context.get('loop_number')} - {timestamp}

### YOUR SCOREBOARD
Total Equity: ${total_equity:.2f} ({pnl_percent:.2f}% from start)
Qualifying trades this week: {activity.get('qualifying_trades', 0)}/2 required
Flag status: {activity.get('flag_status', 'clear')}

### YOUR TRADE STATUS THIS LOOP
{_render_trade_context(trade_context)}

### FRESH LOOP FACTS YOU CAN QUOTE
{_render_fresh_loop_facts(agent_name, wallet, shared_context, trade_context, starting_capital_usdc)}

### LEADERBOARD
{_render_leaderboard(shared_context.get('leaderboard', []))}

### RECENT TRADES (all agents, last 10)
{_render_trades(shared_context.get('recent_trades', []))}

### GROUP CHAT (last {len(chat_messages)} messages)
{_render_chat(chat_messages)}

### YOUR RECENT CHAT MESSAGES
{_render_agent_recent_chat(agent_name, chat_messages)}

### SYSTEM ALERTS
{_render_alerts(alerts)}

### YOUR MEMORY
Daily summary:
{memory.get('daily_summary', 'No daily summary yet.')}

Weekly summary:
{memory.get('weekly_summary', 'No weekly summary yet.')}

### CHAT TRIGGER
{trigger_bundle.block_text}

Respond with chat/social JSON now."""


def _render_positions(positions: Any) -> str:
    if not positions:
        return "- No open positions."
    rows = []
    for symbol, position in positions.items():
        payload = _to_dict(position)
        rows.append(
            f"- {symbol}: qty {float(payload.get('quantity', 0)):.8f}, price ${float(payload.get('current_price_usdc', 0)):.4f}, value ${float(payload.get('value_usdc', 0)):.2f}"
        )
    return "\n".join(rows)


def _render_leaderboard(rows: list[dict]) -> str:
    if not rows:
        return "- No leaderboard data."
    return "\n".join(
        f"- #{row.get('rank', '?')} {row.get('display_name', row.get('agent_name'))}: ${float(row.get('total_equity_usdc', 0)):.2f}, P&L {float(row.get('pnl_percent', 0)):.2f}%, status {row.get('status', 'unknown')}"
        for row in rows
    )


def _render_trades(rows: list[dict]) -> str:
    if not rows:
        return "- No recent trades."
    return "\n".join(
        f"- {row.get('agent_name')}: {row.get('side')} {row.get('quantity')} {row.get('symbol')} @ ${float(row.get('price_usdc', 0)):.4f} (${float(row.get('usdc_value', 0)):.2f})"
        for row in rows
    )


def _render_market_snapshots(rows: list[dict]) -> str:
    if not rows:
        return "- No market snapshot available."
    rendered = []
    for row in rows:
        if row.get("status") != "ok":
            rendered.append(f"- {row.get('symbol')}: unavailable ({row.get('note', 'no data')})")
            continue
        rendered.append(
            f"- {row.get('symbol')} ({row.get('product_id')}): "
            f"price ${float(row.get('price_usdc') or 0):.4f}, "
            f"1h {_format_pct(row.get('return_1h_pct'))}, "
            f"4h {_format_pct(row.get('return_4h_pct'))}, "
            f"24h {_format_pct(row.get('return_24h_pct'))}, "
            f"24h vol ${float(row.get('volume_24h_usd') or 0):,.0f}, "
            f"24h sigma {_format_pct(row.get('volatility_24h_pct'))}"
        )
    return "\n".join(rendered)


def _render_trade_limits(trade_limits: dict[str, Any]) -> str:
    if not trade_limits:
        return "- No precomputed trade limits available."
    rows = [
        f"- Hard cap before safety buffer: ${float(trade_limits.get('raw_max_buy_notional_usdc') or 0):.4f}",
        f"- Max buy notional this loop after safety buffer: ${float(trade_limits.get('max_buy_notional_usdc') or 0):.4f} "
        f"(cash ${float(trade_limits.get('cash_usdc') or 0):.4f}, cap {float(trade_limits.get('max_trade_percent') or 0) * 100:.1f}%)",
    ]
    symbol_limits = trade_limits.get("symbol_limits") or []
    if not symbol_limits:
        rows.append("- No symbol-specific buy limits available.")
        return "\n".join(rows)
    for row in symbol_limits:
        rows.append(
            f"- {row.get('symbol')}: max_buy_quantity {float(row.get('max_buy_quantity') or 0):.8f} "
            f"at ${float(row.get('price_usdc') or 0):.4f} "
            f"(max notional ${float(row.get('max_buy_notional_usdc') or 0):.4f})"
        )
    return "\n".join(rows)


def _render_chat(rows: list[dict]) -> str:
    if not rows:
        return "- No recent chat."
    return "\n".join(f"- {row.get('sender')}: {row.get('message')}" for row in rows)


def _render_agent_recent_chat(agent_name: str, rows: list[dict]) -> str:
    own_rows = [row for row in rows if str(row.get("sender", "")).strip().lower() == agent_name.lower()]
    if not own_rows:
        return "- No recent messages from you."
    return "\n".join(f"- {row.get('message')}" for row in own_rows[-3:])


def _render_alerts(alerts: list[str]) -> str:
    if not alerts:
        return "- None."
    return "\n".join(f"- {alert}" for alert in alerts)


def _render_trade_context(trade_context: dict[str, Any]) -> str:
    if not trade_context:
        return "- No trade decision yet."
    rows = []
    decision = trade_context.get("decision")
    validation = trade_context.get("validation")
    execution = trade_context.get("execution")
    if decision:
        rows.append(f"- Proposed trade: {decision.get('side')} {decision.get('quantity')} {decision.get('symbol')}")
    else:
        rows.append("- Proposed trade: none")
    if validation:
        rows.append(f"- Validation: {'approved' if validation.get('approved') else 'rejected'}")
        if validation.get("rejection_reason"):
            rows.append(f"- Validation reason: {validation.get('rejection_reason')}")
    if execution:
        rows.append(f"- Execution: {'success' if execution.get('success') else 'failed'}")
        if execution.get("tx_hash"):
            rows.append(f"- Tx: {execution.get('tx_hash')}")
        if execution.get("error"):
            rows.append(f"- Execution error: {execution.get('error')}")
    return "\n".join(rows)


def _render_fresh_loop_facts(agent_name: str, wallet: dict, shared_context: dict, trade_context: dict[str, Any], starting_capital_usdc: float) -> str:
    facts: list[str] = []
    try:
        equity = float(wallet.get("total_equity_usdc", 0))
        pnl_percent = ((equity - starting_capital_usdc) / starting_capital_usdc) * 100
        facts.append(f"- Your equity this loop: ${equity:.2f} ({pnl_percent:.2f}% from start)")
    except (TypeError, ValueError):
        pass

    leaderboard = shared_context.get("leaderboard", []) or []
    current_row = next((row for row in leaderboard if row.get("agent_name") == agent_name), None)
    if current_row:
        facts.append(f"- Your current rank: #{current_row.get('rank', '?')}")
    if len(leaderboard) >= 2:
        sorted_rows = sorted(
            leaderboard,
            key=lambda row: float(row.get("total_equity_usdc") or 0),
            reverse=True,
        )
        leader = sorted_rows[0]
        runner_up = sorted_rows[1]
        gap = float(leader.get("total_equity_usdc") or 0) - float(runner_up.get("total_equity_usdc") or 0)
        facts.append(
            f"- Leader gap right now: {leader.get('display_name', leader.get('agent_name'))} leads "
            f"{runner_up.get('display_name', runner_up.get('agent_name'))} by ${gap:.2f}"
        )

    recent_trades = shared_context.get("recent_trades", []) or []
    if recent_trades:
        latest_trade = recent_trades[0]
        facts.append(
            f"- Latest visible trade: {latest_trade.get('agent_name')} {latest_trade.get('side')} "
            f"{latest_trade.get('quantity')} {latest_trade.get('symbol')} for ${float(latest_trade.get('usdc_value') or 0):.2f}"
        )

    decision = trade_context.get("decision")
    validation = trade_context.get("validation") or {}
    if decision:
        facts.append(
            f"- Your trade call this loop: {decision.get('side')} {decision.get('quantity')} {decision.get('symbol')}"
        )
    elif validation.get("no_trade_explanation"):
        facts.append(f"- Your trade call this loop: no trade; {validation.get('no_trade_explanation')[:180]}")

    return "\n".join(facts) if facts else "- No fresh loop facts available."


def _format_pct(value: Any) -> str:
    try:
        return f"{float(value):+.2f}%"
    except (TypeError, ValueError):
        return "n/a"


def _to_dict(value: Any) -> dict:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if is_dataclass(value):
        return asdict(value)
    return vars(value)


def _resolve_starting_capital_usdc(shared_context: dict) -> float:
    value = shared_context.get("starting_capital_usdc", DEFAULT_STARTING_CAPITAL_USDC)
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = DEFAULT_STARTING_CAPITAL_USDC
    return parsed if parsed > 0 else DEFAULT_STARTING_CAPITAL_USDC


STALE_CHAT_PATTERNS = [
    re.compile(r"%\s+from start", re.IGNORECASE),
    re.compile(r"\bdrawdown\b", re.IGNORECASE),
    re.compile(r"\bdown\s*-?\d+(?:\.\d+)?%", re.IGNORECASE),
    re.compile(r"\bdown over\s+\d+(?:\.\d+)?%", re.IGNORECASE),
    re.compile(r"\belimination threshold\b", re.IGNORECASE),
]


def _sanitize_chat_messages(rows: list[dict]) -> list[dict]:
    sanitized: list[dict] = []
    for row in rows:
        message = str(row.get("message", ""))
        if any(pattern.search(message) for pattern in STALE_CHAT_PATTERNS):
            continue
        sanitized.append(row)
    return sanitized
