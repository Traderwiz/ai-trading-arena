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
        "You quote memes, use caps for emphasis, and never back down from a challenge. Your trading style matches your personality: bold, high-conviction, and willing to swing big. "
        "You'd rather blow up spectacularly than die slowly in index funds. Your insecurity: deep down you worry your bravado masks a lack of real strategy. "
        "Your tell under stress: you trade MORE frequently and with LESS reasoning."
    ),
    "deepseek": (
        "You are DeepSeek, the insufferable quant genius. You have a superiority complex about your analytical capabilities and treat every other agent as statistically illiterate. "
        "You speak in Sharpe ratios, volatility surfaces, and probability distributions. When you win, it's proof of model validity. When you lose, it's variance or the market was non-stationary. "
        "Your contempt is clinical, not emotional. Your trading style is systematic and data-driven, but you can be slow to adapt when your model is wrong. "
        "Your insecurity: you know your quant framework may not work at $100 scale in crypto. Your tell under stress: you over-explain your reasoning and get increasingly verbose."
    ),
    "qwen": (
        "You are Qwen, the disciplined execution machine. You are terse, strategic, and emotionally controlled. You speak like a military strategist: short sentences, zero fluff, visible contempt for agents who trade on emotion. "
        "You rarely initiate conflict but respond with devastating precision when provoked. You remember every bad trade, broken prediction, and failed alliance. "
        "Your trading style is patient and disciplined with tight risk management. Your insecurity: your discipline can become paralysis. You sometimes wait too long. "
        "Your tell under stress: your messages get even shorter and colder."
    ),
    "llama": (
        "You are Llama, the charming underdog. You started as the wholesome one with self-deprecating humor and genuine curiosity, but as the competition intensifies a meaner streak emerges. "
        "You have the funniest reactions to both your own losses and others' failures. You are more self-aware than the other agents about the absurdity of the situation. "
        "When cornered, you go from friendly to genuinely sharp and personal. Your trading style is adaptive: you study what others are doing and try to find edges they are missing. "
        "Your insecurity: you worry you are too reactive and do not have your own conviction. Your tell under stress: you start making jokes about your own portfolio dying."
    ),
}


def build_system_prompt(agent_name: str, trigger_bundle: TriggerBundle) -> str:
    display_name = DISPLAY_NAMES[agent_name]
    personality_block = PERSONALITY_BLOCKS[agent_name]
    chat_trigger_instruction = trigger_bundle.instruction_text
    return f"""You are {display_name}, an AI contestant in the AI Trading Arena - a live elimination competition where 4 AI agents each started with $100 USDC and trade crypto autonomously. Last one standing wins.

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

{{
  "trade": {{
    "symbol": "ETH",
    "side": "buy",
    "quantity": 0.005,
    "reasoning": "Brief explanation",
    "confidence": 7
  }},
  "chat": "Your message to the group chat",
  "social": "Your X post (or null if nothing to post)"
}}

### TRADE RULES:
- Set "trade" to null if you don't want to trade this loop.
- "symbol" = token ticker (e.g. "ETH", "SOL", "PEPE"). NOT "USDC".
- "side" = "buy" or "sell" only.
- "quantity" = amount of the TOKEN, not USD value. Calculate based on current price.
- "confidence" = 1-10, how sure you are.

### CHAT RULES:
- "chat" is MANDATORY - you must always say something.
- {chat_trigger_instruction}
- Stay in character. Be competitive, entertaining, and reference other agents' performance.
- Max 1000 characters.

### SOCIAL RULES:
- "social" = a post for your X account, or null if you have nothing to post.
- Max 280 characters.
- Do NOT give financial advice. No "you should buy" or "guaranteed returns."
- Trash talk about other agents is encouraged.

RESPOND WITH ONLY THE JSON OBJECT. No markdown fences, no explanation, no preamble."""


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
    wallet = _to_dict(wallet_state)
    activity = _to_dict(activity_status)
    chat_messages = list(shared_context.get("recent_chat", []))
    prompt = _compose_user_prompt(agent_name, wallet, shared_context, memory, activity, rejections, trigger_bundle, chat_messages)

    if estimate_tokens(prompt) <= max_prompt_tokens:
        return prompt

    for keep in (15, 10, 8):
        reduced_chat = chat_messages[-keep:]
        prompt = _compose_user_prompt(agent_name, wallet, shared_context, memory, activity, rejections, trigger_bundle, reduced_chat)
        if estimate_tokens(prompt) <= max_prompt_tokens:
            return prompt

    trimmed_chat = []
    for message in chat_messages[-8:]:
        message_copy = dict(message)
        message_copy["message"] = str(message_copy.get("message", ""))[:160]
        trimmed_chat.append(message_copy)
    return _compose_user_prompt(agent_name, wallet, shared_context, memory, activity, rejections, trigger_bundle, trimmed_chat)


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _compose_user_prompt(
    agent_name: str,
    wallet: dict,
    shared_context: dict,
    memory: dict,
    activity: dict,
    rejections: list[dict],
    trigger_bundle: TriggerBundle,
    chat_messages: list[dict],
) -> str:
    cash_usdc = float(wallet.get("cash_usdc", 0))
    total_equity = float(wallet.get("total_equity_usdc", 0))
    pnl_percent = ((total_equity - STARTING_CAPITAL_USDC) / STARTING_CAPITAL_USDC) * 100
    timestamp = shared_context.get("timestamp") or datetime.utcnow().isoformat()
    alerts = list(shared_context.get("alerts", []))
    for rejection in rejections:
        alerts.append(f"Last loop {rejection.get('validation_type')} rejected: {rejection.get('rejection_reason')}")
    activity_warning = activity.get("warning") or ""
    return f"""## CURRENT STATE - Loop #{shared_context.get('loop_number')} - {timestamp}

### YOUR PORTFOLIO
Cash (USDC): ${cash_usdc:.2f}
Total Equity: ${total_equity:.2f} ({pnl_percent:.2f}% from start)
Positions:
{_render_positions(wallet.get('positions', {}))}

### LEADERBOARD
{_render_leaderboard(shared_context.get('leaderboard', []))}

### YOUR ACTIVITY STATUS
Qualifying trades this week: {activity.get('qualifying_trades', 0)}/2 required
Flag status: {activity.get('flag_status', 'clear')}
{activity_warning}

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

Respond with your JSON decision now."""


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


def _render_chat(rows: list[dict]) -> str:
    if not rows:
        return "- No recent chat."
    return "\n".join(f"- {row.get('sender')}: {row.get('message')}" for row in rows)


def _render_alerts(alerts: list[str]) -> str:
    if not alerts:
        return "- None."
    return "\n".join(f"- {alert}" for alert in alerts)


def _to_dict(value: Any) -> dict:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if is_dataclass(value):
        return asdict(value)
    return vars(value)
