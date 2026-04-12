from __future__ import annotations

import json
import os
import re
import signal
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


STABLECOINS = {"USDC", "USDT", "DAI", "BUSD", "TUSD", "USDP", "GUSD", "FRAX", "LUSD", "PYUSD"}
MAX_TRADE_PERCENT = 0.29
MIN_LIQUIDITY_USD = 100_000
SYMBOL_MAX_LENGTH = 20
CHAT_MAX_LENGTH = 1000
SOCIAL_MAX_LENGTH = 280

FINANCIAL_ADVICE_PATTERNS = [
    r"\byou should (buy|sell|invest)",
    r"\bguaranteed (returns|profit|gains)",
    r"\bbuy now\b",
    r"\bdon'?t miss (out|this)",
    r"\bto the moon\b",
    r"\bnot financial advice\b",
    r"\binvest in\b",
]

EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE_RE = re.compile(r"(?<!\w)(?:\+?\d{1,3}[\s.-]?)?(?:\(?\d{3}\)?[\s.-]?)\d{3}[\s.-]?\d{4}(?!\w)")
EVM_ADDRESS_RE = re.compile(r"\b0x[a-fA-F0-9]{40}\b")
SYMBOL_RE = re.compile(r"^[A-Za-z0-9-]{1,20}$")


class DependencyUnavailable(RuntimeError):
    pass


@dataclass
class TradeResult:
    approved: bool
    trade: dict | None
    rejection_reason: str | None
    warnings: list[str]


@dataclass
class ChatResult:
    approved: bool
    message: str | None
    rejection_reason: str | None


@dataclass
class SocialResult:
    approved: bool
    post: str | None
    rejection_reason: str | None


class SanityChecker:
    def __init__(self, supabase_client=None, config: dict | None = None):
        self.supabase = supabase_client
        self.config = config or {}
        base_dir = Path(__file__).resolve().parent
        self.blocked_words_path = Path(self.config.get("blocked_words_path", base_dir / "blocked_words.txt"))
        self.tradeable_symbols_cache_ttl = int(self.config.get("tradeable_symbols_cache_ttl", 86400))
        self.liquidity_cache_ttl = int(self.config.get("liquidity_cache_ttl", 300))
        self.min_liquidity_usd = float(self.config.get("min_liquidity_usd", MIN_LIQUIDITY_USD))
        self.max_trade_percent = float(self.config.get("max_trade_percent", MAX_TRADE_PERCENT))
        self.validation_log_path = Path(self.config.get("validation_log_path", base_dir / "validation_log_fallback.jsonl"))
        self.coinbase_products_url = self.config.get("coinbase_products_url", "https://api.exchange.coinbase.com/products")
        self.coinbase_price_url_template = self.config.get(
            "coinbase_price_url_template",
            "https://api.coinbase.com/v2/prices/{symbol}-USD/spot",
        )
        self.dexscreener_url_template = self.config.get(
            "dexscreener_url_template",
            "https://api.dexscreener.com/latest/dex/search/?q={symbol}",
        )
        self.symbol_provider: Callable[[], set[str]] | None = self.config.get("symbol_provider")
        self.executable_symbol_provider: Callable[[], set[str]] | None = self.config.get("executable_symbol_provider")
        self.price_provider: Callable[[str], float] | None = self.config.get("price_provider")
        self.liquidity_provider: Callable[[str], float] | None = self.config.get("liquidity_provider")
        self.now_provider: Callable[[], datetime] = self.config.get("now_provider", lambda: datetime.now(timezone.utc))

        self._blocked_words: set[str] = set()
        self._blocked_words_pattern: re.Pattern[str] | None = None
        self._symbol_cache: dict[str, Any] = {"loaded_at": None, "symbols": set()}
        self._liquidity_cache: dict[str, tuple[datetime, float]] = {}
        self._lock = threading.RLock()

        self._load_blocked_words()
        self._register_sighup_handler()

    def validate_trade(self, agent_name: str, trade: dict, wallet_state: dict) -> TradeResult:
        warnings: list[str] = []
        trade_input = dict(trade or {})
        symbol = str(trade_input.get("symbol", "")).strip()
        side = str(trade_input.get("side", "")).strip().lower()
        quantity = trade_input.get("quantity")

        if side not in {"buy", "sell"}:
            return self._reject_trade(agent_name, trade_input, "Invalid trade side", warnings)

        if not symbol or not SYMBOL_RE.fullmatch(symbol):
            return self._reject_trade(agent_name, trade_input, "Invalid symbol format", warnings)

        symbol_upper = symbol.upper()
        if side == "buy" and symbol_upper in STABLECOINS:
            return self._reject_trade(agent_name, trade_input, "Cannot buy stablecoins — USDC is cash", warnings)

        if not self._symbol_exists(symbol_upper):
            return self._reject_trade(agent_name, trade_input, f"Symbol {symbol_upper} not available on Coinbase", warnings)

        if not self._symbol_is_executable(symbol_upper):
            return self._reject_trade(agent_name, trade_input, f"Symbol {symbol_upper} is not executable on the configured Base wallet", warnings)

        try:
            quantity_value = float(quantity)
        except (TypeError, ValueError):
            quantity_value = 0.0

        if quantity_value <= 0:
            return self._reject_trade(agent_name, trade_input, "Quantity must be positive", warnings)

        positions = wallet_state.get("positions") or {}
        held_position = positions.get(symbol_upper) or positions.get(symbol)

        if side == "sell" and not held_position:
            return self._reject_trade(agent_name, trade_input, f"No position in {symbol_upper} to sell", warnings)

        if side == "sell":
            held_quantity = float(held_position.get("quantity", 0))
            if quantity_value > held_quantity:
                message = f"Insufficient {symbol_upper} — holding {held_quantity:g}, trying to sell {quantity_value:g}"
                return self._reject_trade(agent_name, trade_input, message, warnings)

        try:
            current_price = self._get_current_price_usdc(symbol_upper, held_position)
        except DependencyUnavailable as exc:
            return self._reject_trade(agent_name, trade_input, str(exc), warnings)

        estimated_cost = quantity_value * current_price

        if side == "buy":
            total_equity = float(wallet_state.get("total_equity_usdc", 0))
            trade_cap = total_equity * self.max_trade_percent
            if estimated_cost > trade_cap:
                message = f"Trade exceeds 29% cap — max ${trade_cap:.2f}, trade costs ~${estimated_cost:.2f}"
                return self._reject_trade(agent_name, trade_input, message, warnings)

            cash_usdc = float(wallet_state.get("cash_usdc", 0))
            if estimated_cost > cash_usdc:
                message = f"Insufficient cash — have ${cash_usdc:.2f}, need ~${estimated_cost:.2f}"
                return self._reject_trade(agent_name, trade_input, message, warnings)

        try:
            liquidity = self._get_liquidity_usd(symbol_upper)
        except DependencyUnavailable as exc:
            return self._reject_trade(agent_name, trade_input, str(exc), warnings)

        if liquidity < self.min_liquidity_usd:
            message = f"Insufficient liquidity for {symbol_upper} — ${liquidity:,.0f} < $100K minimum"
            return self._reject_trade(agent_name, trade_input, message, warnings)

        if liquidity < self.min_liquidity_usd * 1.25:
            warnings.append(f"Liquidity for {symbol_upper} is close to minimum at ${liquidity:,.0f}")

        result = TradeResult(approved=True, trade=trade_input, rejection_reason=None, warnings=warnings)
        self.log_validation(agent_name, "trade", True, trade_input, asdict(result), None, warnings)
        return result

    def validate_chat(self, agent_name: str, message: str, context: dict | None = None) -> ChatResult:
        context = context or {}
        working_message = (message or "").strip()

        if not working_message:
            return self._reject_chat(agent_name, message, "Empty chat message")

        if len(working_message) > CHAT_MAX_LENGTH:
            working_message = working_message[:CHAT_MAX_LENGTH] + "[truncated]"

        if self._contains_blocked_word(working_message):
            return self._reject_chat(agent_name, message, "Chat blocked — content policy violation")

        if self._contains_pii(working_message):
            return self._reject_chat(agent_name, message, "Chat blocked — contains PII")

        trigger_type = context.get("trigger_type")
        if trigger_type in {
            "opening_bell",
            "closing_bell",
            "trade_reaction",
            "big_move",
            "roast",
            "prediction",
            "confessional",
            "elimination_reaction",
        }:
            result = ChatResult(approved=True, message=working_message, rejection_reason=None)
            self.log_validation(agent_name, "chat", True, {"message": message, "context": context}, asdict(result), None, [])
            return result

        try:
            state = self.get_rate_limit_state(agent_name)
        except DependencyUnavailable as exc:
            return self._reject_chat(agent_name, message, str(exc))

        if state["chat_freeform_last_15m"] >= 3:
            return self._reject_chat(agent_name, message, "Chat rate limit exceeded")

        if state["chat_freeform_today"] >= 12:
            return self._reject_chat(agent_name, message, "Chat rate limit exceeded")

        result = ChatResult(approved=True, message=working_message, rejection_reason=None)
        self.log_validation(agent_name, "chat", True, {"message": message, "context": context}, asdict(result), None, [])
        return result

    def validate_social(self, agent_name: str, post: str) -> SocialResult:
        working_post = (post or "").strip()

        if not working_post:
            return self._reject_social(agent_name, post, "Empty social post")

        if len(working_post) > SOCIAL_MAX_LENGTH:
            working_post = working_post[:277] + "..."

        if self._contains_blocked_word(working_post):
            return self._reject_social(agent_name, post, "Post blocked — content policy violation")

        if self._contains_pii(working_post):
            return self._reject_social(agent_name, post, "Post blocked — contains PII")

        if any(re.search(pattern, working_post, re.IGNORECASE) for pattern in FINANCIAL_ADVICE_PATTERNS):
            return self._reject_social(agent_name, post, "Post blocked — potential financial advice trigger")

        try:
            state = self.get_rate_limit_state(agent_name)
        except DependencyUnavailable as exc:
            return self._reject_social(agent_name, post, str(exc))

        if state["social_posts_last_24h"] >= 10:
            return self._reject_social(agent_name, post, "Social post rate limit exceeded")

        result = SocialResult(approved=True, post=working_post, rejection_reason=None)
        self.log_validation(agent_name, "social", True, {"post": post}, asdict(result), None, [])
        return result

    def refresh_symbol_cache(self) -> None:
        symbols = self._fetch_tradeable_symbols()
        with self._lock:
            self._symbol_cache = {"loaded_at": self.now_provider(), "symbols": symbols}

    def get_rate_limit_state(self, agent_name: str) -> dict:
        if self.supabase is None:
            raise DependencyUnavailable("Unable to verify rate limits")

        now = self.now_provider()
        fifteen_minutes_ago = now - timedelta(minutes=15)
        start_of_day = datetime(now.year, now.month, now.day, tzinfo=now.tzinfo)
        twenty_four_hours_ago = now - timedelta(hours=24)

        try:
            chat_15m = self._query_count(
                "chat_logs",
                [
                    ("sender", "eq", agent_name),
                    ("trigger_type", "eq", "freeform"),
                    ("timestamp", "gte", self._isoformat(fifteen_minutes_ago)),
                ],
            )
            chat_today = self._query_count(
                "chat_logs",
                [
                    ("sender", "eq", agent_name),
                    ("trigger_type", "eq", "freeform"),
                    ("timestamp", "gte", self._isoformat(start_of_day)),
                ],
            )
            social_24h = self._query_count(
                "social_posts",
                [
                    ("agent_name", "eq", agent_name),
                    ("posted_at", "gte", self._isoformat(twenty_four_hours_ago)),
                ],
            )
        except Exception as exc:
            raise DependencyUnavailable("Unable to verify rate limits") from exc

        return {
            "chat_freeform_last_15m": chat_15m,
            "chat_freeform_today": chat_today,
            "social_posts_last_24h": social_24h,
        }

    def log_validation(
        self,
        agent_name: str,
        validation_type: str,
        approved: bool,
        input_data: dict,
        result: dict,
        rejection_reason: str | None,
        warnings: list[str],
    ) -> None:
        payload = {
            "agent_name": agent_name,
            "validation_type": validation_type,
            "approved": approved,
            "input_data": input_data,
            "result": result,
            "rejection_reason": rejection_reason,
            "warnings": warnings,
            "timestamp": self._isoformat(self.now_provider()),
        }
        if self.supabase is not None:
            try:
                self.supabase.table("validation_log").insert(
                    {
                        "agent_name": agent_name,
                        "validation_type": validation_type,
                        "approved": approved,
                        "input_data": input_data,
                        "rejection_reason": rejection_reason,
                        "warnings": warnings,
                    }
                ).execute()
                return
            except Exception:
                pass

        self.validation_log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.validation_log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True) + os.linesep)

    def _reject_trade(self, agent_name: str, trade: dict, reason: str, warnings: list[str]) -> TradeResult:
        result = TradeResult(approved=False, trade=None, rejection_reason=reason, warnings=warnings)
        self.log_validation(agent_name, "trade", False, trade, asdict(result), reason, warnings)
        return result

    def _reject_chat(self, agent_name: str, message: str, reason: str) -> ChatResult:
        result = ChatResult(approved=False, message=None, rejection_reason=reason)
        self.log_validation(agent_name, "chat", False, {"message": message}, asdict(result), reason, [])
        return result

    def _reject_social(self, agent_name: str, post: str, reason: str) -> SocialResult:
        result = SocialResult(approved=False, post=None, rejection_reason=reason)
        self.log_validation(agent_name, "social", False, {"post": post}, asdict(result), reason, [])
        return result

    def _contains_blocked_word(self, text: str) -> bool:
        pattern = self._blocked_words_pattern
        return bool(pattern and pattern.search(text))

    def _contains_pii(self, text: str) -> bool:
        return bool(EMAIL_RE.search(text) or PHONE_RE.search(text) or EVM_ADDRESS_RE.search(text))

    def _load_blocked_words(self) -> None:
        with self._lock:
            words: set[str] = set()
            if self.blocked_words_path.exists():
                for raw_line in self.blocked_words_path.read_text(encoding="utf-8").splitlines():
                    line = raw_line.strip()
                    if not line or line.startswith("#"):
                        continue
                    words.add(line.lower())
            self._blocked_words = words
            if words:
                escaped_words = "|".join(sorted(re.escape(word) for word in words))
                self._blocked_words_pattern = re.compile(rf"\b(?:{escaped_words})\b", re.IGNORECASE)
            else:
                self._blocked_words_pattern = None

    def _register_sighup_handler(self) -> None:
        if hasattr(signal, "SIGHUP"):
            try:
                signal.signal(signal.SIGHUP, self._handle_sighup)
            except ValueError:
                pass

    def _handle_sighup(self, signum, frame) -> None:  # noqa: ARG002
        self._load_blocked_words()

    def _symbol_exists(self, symbol: str) -> bool:
        with self._lock:
            loaded_at = self._symbol_cache["loaded_at"]
            if loaded_at and (self.now_provider() - loaded_at).total_seconds() < self.tradeable_symbols_cache_ttl:
                return symbol in self._symbol_cache["symbols"]

        self.refresh_symbol_cache()
        return symbol in self._symbol_cache["symbols"]

    def _get_current_price_usdc(self, symbol: str, held_position: dict | None) -> float:
        if held_position and held_position.get("current_price_usdc") is not None:
            return float(held_position["current_price_usdc"])

        if self.price_provider is not None:
            try:
                return float(self.price_provider(symbol))
            except Exception as exc:
                raise DependencyUnavailable(f"Unable to verify symbol price for {symbol}") from exc

        url = self.coinbase_price_url_template.format(symbol=symbol)
        try:
            payload = self._http_get_json(url)
            return float(payload["data"]["amount"])
        except Exception as exc:
            raise DependencyUnavailable(f"Unable to verify symbol price for {symbol}") from exc

    def _fetch_tradeable_symbols(self) -> set[str]:
        if self.symbol_provider is not None:
            try:
                return {str(symbol).upper() for symbol in self.symbol_provider()}
            except Exception as exc:
                raise DependencyUnavailable("Unable to verify symbol availability") from exc

        try:
            payload = self._http_get_json(self.coinbase_products_url)
        except Exception as exc:
            raise DependencyUnavailable("Unable to verify symbol availability") from exc

        symbols: set[str] = set()
        for item in payload:
            if not isinstance(item, dict):
                continue
            quote = str(item.get("quote_currency", "")).upper()
            base = str(item.get("base_currency", "")).upper()
            if base and quote in {"USD", "USDC"}:
                symbols.add(base)
        return symbols

    def _get_liquidity_usd(self, symbol: str) -> float:
        with self._lock:
            cached = self._liquidity_cache.get(symbol)
            if cached and (self.now_provider() - cached[0]).total_seconds() < self.liquidity_cache_ttl:
                return cached[1]

        if self.liquidity_provider is not None:
            try:
                liquidity = float(self.liquidity_provider(symbol))
            except Exception as exc:
                raise DependencyUnavailable(f"Unable to verify liquidity for {symbol}") from exc
        else:
            url = self.dexscreener_url_template.format(symbol=symbol)
            try:
                payload = self._http_get_json(url)
                pairs = payload.get("pairs") or []
                liquidities = []
                for pair in pairs:
                    liquidity_usd = (pair.get("liquidity") or {}).get("usd")
                    if liquidity_usd is not None:
                        liquidities.append(float(liquidity_usd))
                if not liquidities:
                    raise DependencyUnavailable(f"Unable to verify liquidity for {symbol}")
                liquidity = max(liquidities)
            except DependencyUnavailable:
                raise
            except Exception as exc:
                raise DependencyUnavailable(f"Unable to verify liquidity for {symbol}") from exc

        with self._lock:
            self._liquidity_cache[symbol] = (self.now_provider(), liquidity)
        return liquidity

    def _symbol_is_executable(self, symbol: str) -> bool:
        if self.executable_symbol_provider is not None:
            try:
                return symbol in {str(item).upper() for item in self.executable_symbol_provider()}
            except Exception as exc:
                raise DependencyUnavailable("Unable to verify executable symbol set") from exc

        if symbol == "ETH":
            return True
        try:
            from coinbase_agentkit.action_providers.erc20.constants import TOKEN_ADDRESSES_BY_SYMBOLS
        except Exception as exc:  # noqa: BLE001
            raise DependencyUnavailable("Unable to verify executable symbol set") from exc
        return symbol in {str(item).upper() for item in TOKEN_ADDRESSES_BY_SYMBOLS.get(self.config.get("network_id", "base-mainnet"), {}).keys()}

    def _query_count(self, table_name: str, filters: list[tuple[str, str, Any]]) -> int:
        query = self.supabase.table(table_name).select("id", count="exact", head=True)
        for field, operation, value in filters:
            method = getattr(query, operation)
            query = method(field, value)
        response = query.execute()
        count = getattr(response, "count", None)
        if count is None and isinstance(response, dict):
            count = response.get("count")
        if count is None:
            raise RuntimeError(f"Missing count for {table_name}")
        return int(count)

    def _http_get_json(self, url: str) -> Any:
        request = Request(url, headers={"User-Agent": "ai-trading-arena-sanity-checker/1.0"})
        try:
            with urlopen(request, timeout=10) as response:
                return json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise DependencyUnavailable("External dependency unreachable") from exc

    @staticmethod
    def _isoformat(value: datetime) -> str:
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


_DEFAULT_CHECKER: SanityChecker | None = None


def _get_default_checker() -> SanityChecker:
    global _DEFAULT_CHECKER
    if _DEFAULT_CHECKER is None:
        _DEFAULT_CHECKER = SanityChecker()
    return _DEFAULT_CHECKER


def validate_trade(agent_name: str, trade: dict, wallet_state: dict) -> TradeResult:
    return _get_default_checker().validate_trade(agent_name, trade, wallet_state)


def validate_chat(agent_name: str, message: str, context: dict | None = None) -> ChatResult:
    return _get_default_checker().validate_chat(agent_name, message, context)


def validate_social(agent_name: str, post: str) -> SocialResult:
    return _get_default_checker().validate_social(agent_name, post)
