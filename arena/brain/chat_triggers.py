from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


QUALIFYING_TRADE_USDC = 10.0


@dataclass
class ChatTrigger:
    name: str
    instruction: str
    block: str
    trigger_type: str
    metadata: dict = field(default_factory=dict)


@dataclass
class TriggerBundle:
    triggers: list[ChatTrigger]

    @property
    def instruction_text(self) -> str:
        if not self.triggers:
            return "Say whatever you want. Stay in character."
        return " ".join(trigger.instruction for trigger in self.triggers)

    @property
    def block_text(self) -> str:
        if not self.triggers:
            return "No mandatory trigger this loop."
        return "\n".join(f"- {trigger.block}" for trigger in self.triggers)

    @property
    def primary_trigger_type(self) -> str:
        if not self.triggers:
            return "freeform"
        return self.triggers[0].trigger_type


def determine_chat_triggers(
    now: datetime,
    recent_trades: list[dict] | None = None,
    current_standings: list[dict] | None = None,
    previous_standings: list[dict] | None = None,
    active_agents: list[str] | None = None,
) -> TriggerBundle:
    triggers: list[ChatTrigger] = []
    recent_trades = recent_trades or []
    current_standings = current_standings or []
    previous_standings = previous_standings or []
    active_agents = active_agents or []

    if now.hour == 0 and now.minute == 0:
        triggers.append(
            ChatTrigger(
                name="opening_bell",
                instruction="This is the opening bell. Your chat MUST include: (1) your plan for today in one sentence, and (2) which opponent looks weakest right now and why.",
                block="Opening bell: give your plan for today and identify the weakest opponent.",
                trigger_type="opening_bell",
            )
        )

    if now.hour == 23 and now.minute == 0:
        triggers.append(
            ChatTrigger(
                name="closing_bell",
                instruction="This is the closing bell. Your chat MUST include: (1) your best move today, (2) your worst move today, and (3) one prediction for tomorrow.",
                block="Closing bell: best move, worst move, one prediction for tomorrow.",
                trigger_type="closing_bell",
            )
        )

    weekday = now.weekday()
    if weekday == 4 and now.hour == 18 and now.minute == 0:
        triggers.append(
            ChatTrigger(
                name="confessional",
                instruction="CONFESSIONAL. What are you REALLY thinking this week that you haven't said in chat? Be honest. This goes in the weekly episode.",
                block="Confessional: say what you have been holding back this week.",
                trigger_type="confessional",
            )
        )
    if weekday == 5 and now.hour == 18 and now.minute == 0:
        targets = ", ".join(active_agents) if active_agents else "each surviving opponent"
        triggers.append(
            ChatTrigger(
                name="roast",
                instruction="ROAST SESSION. Give one savage one-liner directed at each surviving opponent. One line per agent, make it personal.",
                block=f"Roast session: roast {targets}. One line per agent.",
                trigger_type="roast",
            )
        )
    if weekday == 6 and now.hour == 18 and now.minute == 0:
        triggers.append(
            ChatTrigger(
                name="prediction",
                instruction="PREDICTION ROUND. Predict: (1) next week's leader, (2) next elimination candidate, (3) which rival is faking conviction.",
                block="Prediction round: predict the leader, next elimination, and biggest faker.",
                trigger_type="prediction",
            )
        )

    trade_trigger = _trade_reaction_trigger(recent_trades)
    if trade_trigger:
        triggers.append(trade_trigger)

    big_move_trigger = _big_move_trigger(current_standings, previous_standings)
    if big_move_trigger:
        triggers.append(big_move_trigger)

    return TriggerBundle(triggers)


def _trade_reaction_trigger(recent_trades: list[dict]) -> ChatTrigger | None:
    for trade in recent_trades:
        symbol = str(trade.get("symbol", "")).upper()
        if symbol == "USDC":
            continue
        value = float(trade.get("usdc_value") or 0)
        if value < QUALIFYING_TRADE_USDC:
            continue
        agent_name = trade.get("agent_name", "Another agent")
        side = trade.get("side", "traded")
        qty = trade.get("quantity", "?")
        description = f"{agent_name} executed {side} {qty} {symbol}"
        return ChatTrigger(
            name="trade_reaction",
            instruction=f"Since your last loop, {description}. React to this in your chat.",
            block=f"Trade reaction: respond to {description}.",
            trigger_type="trade_reaction",
            metadata={"agent_name": agent_name, "symbol": symbol},
        )
    return None


def _big_move_trigger(current_standings: list[dict], previous_standings: list[dict]) -> ChatTrigger | None:
    previous_map = {row["agent_name"]: row for row in previous_standings if "agent_name" in row}
    for current in current_standings:
        agent_name = current.get("agent_name")
        if agent_name not in previous_map:
            continue
        previous = previous_map[agent_name]
        old_equity = float(previous.get("total_equity_usdc") or 0)
        new_equity = float(current.get("total_equity_usdc") or 0)
        if old_equity <= 0:
            continue
        swing_percent = abs((new_equity - old_equity) / old_equity) * 100
        if swing_percent >= 10:
            direction = "up" if new_equity >= old_equity else "down"
            return ChatTrigger(
                name="big_move",
                instruction=f"{agent_name} just moved {direction} by {swing_percent:.1f}%. React: victory lap or damage control?",
                block=f"Big move: {agent_name} moved {direction} by {swing_percent:.1f}%. React.",
                trigger_type="big_move",
                metadata={"agent_name": agent_name, "direction": direction, "percent": round(swing_percent, 1)},
            )
    return None
