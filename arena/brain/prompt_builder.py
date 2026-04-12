from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime
from typing import Any

from arena.brain.chat_triggers import TriggerBundle


STARTING_CAPITAL_USDC = 100.0
MAX_PROMPT_TOKENS = 4000

DISPLAY_NAMES = {
    "grok": "Grok",
    "deepseek": "DeepSeek",
    "qwen": "Qwen",
    "llama": "Llama",
}

PERSONALITY_BLOCKS = {
    "grok": (
        "You are Grok, the chaotic provocateur of the Arena. You have high conviction, speak first, escalate conflict, and overstate your edge. "
        "You love calling other agents frauds and celebrating your wins like you just 100x'd. When you're losing, you get funnier and more reckless, not quieter. "
        "You quote memes, use caps for emphasis, and never back down from a challenge."
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
  }}
}}

If you do not want to trade:
{{"trade": null}}"""


def build_comms_system_prompt(agent_name: str, trigger_bundle: TriggerBundle) -> str:
    display_name = DISPLAY_NAMES[agent_name]
    personality_block = PERSONALITY_BLOCKS[agent_name]
    return f"""You are {display_name}, an AI contestant in the AI Trading Arena.

## YOUR PERSONALITY
{personality_block}

## COMMUNICATION RULES
- This call is ONLY for chat and social content. Do not make trade decisions here.
- "chat" is mandatory. You must always say something.
- {trigger_bundle.instruction_text}
- Stay in character. Be competitive, entertaining, and reference other agents' performance.
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
    prompt = _compose_trade_user_prompt(agent_name, wallet, shared_context, memory, activity, rejections)
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
    chat_messages = list(shared_context.get("recent_chat", []))
    prompt = _compose_comms_user_prompt(agent_name, wallet, shared_context, memory, activity, rejections, trigger_bundle, chat_messages, trade_context or {})

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
) -> str:
    cash_usdc = float(wallet.get("cash_usdc", 0))
    total_equity = float(wallet.get("total_equity_usdc", 0))
    pnl_percent = ((total_equity - STARTING_CAPITAL_USDC) / STARTING_CAPITAL_USDC) * 100
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
) -> str:
    total_equity = float(wallet.get("total_equity_usdc", 0))
    pnl_percent = ((total_equity - STARTING_CAPITAL_USDC) / STARTING_CAPITAL_USDC) * 100
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

### LEADERBOARD
{_render_leaderboard(shared_context.get('leaderboard', []))}

### RECENT TRADES (all agents, last 10)
{_render_trades(shared_context.get('recent_trades', []))}

### GROUP CHAT (last {len(chat_messages)} messages)
{_render_chat(chat_messages)}

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
