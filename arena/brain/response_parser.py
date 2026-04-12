from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any


class AgentParseError(ValueError):
    pass


@dataclass
class AgentDecision:
    trade: dict | None
    chat: str
    social: str | None


@dataclass
class TradeDecision:
    trade: dict | None


@dataclass
class CommsDecision:
    chat: str
    social: str | None


def parse_agent_response(raw_json: str | dict[str, Any]) -> AgentDecision:
    payload = _parse_payload(raw_json)
    return AgentDecision(
        trade=_normalize_trade(payload.get("trade")),
        chat=_normalize_chat(payload.get("chat")),
        social=_normalize_social(payload.get("social")),
    )


def parse_trade_response(raw_json: str | dict[str, Any]) -> TradeDecision:
    payload = _parse_payload(raw_json)
    trade_payload = payload.get("trade") if "trade" in payload else payload
    return TradeDecision(trade=_normalize_trade(trade_payload))


def parse_comms_response(raw_json: str | dict[str, Any]) -> CommsDecision:
    payload = _parse_payload(raw_json)
    return CommsDecision(
        chat=_normalize_chat(payload.get("chat")),
        social=_normalize_social(payload.get("social")),
    )


def _parse_payload(raw_json: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(raw_json, dict):
        payload = raw_json
    else:
        cleaned = _clean_raw_json(str(raw_json))
        try:
            payload = json.loads(cleaned)
        except json.JSONDecodeError:
            try:
                payload = json.loads(_remove_trailing_commas(cleaned))
            except json.JSONDecodeError as exc:
                raise AgentParseError("Unable to parse agent response as JSON") from exc

    if not isinstance(payload, dict):
        raise AgentParseError("Agent response must be a JSON object")
    return payload


def _clean_raw_json(raw: str) -> str:
    stripped = raw.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped, flags=re.IGNORECASE)
        stripped = re.sub(r"\s*```$", "", stripped)
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise AgentParseError("Unable to find JSON object in agent response")
    return stripped[start : end + 1]


def _remove_trailing_commas(raw: str) -> str:
    return re.sub(r",(\s*[}\]])", r"\1", raw)


def _normalize_trade(value: Any) -> dict | None:
    if value in (None, "", False):
        return None
    if not isinstance(value, dict):
        return None

    symbol = str(value.get("symbol", "")).strip().upper()
    side = str(value.get("side", "")).strip().lower()
    reasoning = str(value.get("reasoning", "")).strip()
    confidence = value.get("confidence")
    quantity = value.get("quantity")

    try:
        confidence_value = int(confidence) if confidence is not None else None
    except (TypeError, ValueError):
        confidence_value = None

    try:
        quantity_value = float(quantity) if quantity is not None else None
    except (TypeError, ValueError):
        quantity_value = None

    normalized = {
        "symbol": symbol,
        "side": side,
        "quantity": quantity_value,
        "reasoning": reasoning,
        "confidence": confidence_value,
    }
    if not symbol or side not in {"buy", "sell"} or quantity_value is None:
        return None
    return normalized


def _normalize_chat(value: Any) -> str:
    if value is None:
        return "..."
    if isinstance(value, (dict, list)):
        return json.dumps(value)
    text = str(value).strip()
    return text or "..."


def _normalize_social(value: Any) -> str | None:
    if value in (None, "", False):
        return None
    if isinstance(value, (dict, list)):
        return json.dumps(value)
    text = str(value).strip()
    return text or None
