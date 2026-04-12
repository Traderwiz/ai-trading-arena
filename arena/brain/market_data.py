from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


DEFAULT_REFERENCE_SYMBOLS = ("ETH", "BTC", "SOL")


@dataclass
class MarketSnapshot:
    symbol: str
    product_id: str
    price_usdc: float | None
    return_1h_pct: float | None
    return_4h_pct: float | None
    return_24h_pct: float | None
    volume_24h_usd: float | None
    volatility_24h_pct: float | None
    status: str
    note: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class MarketDataProvider:
    def __init__(
        self,
        config: dict | None = None,
        now_provider: Callable[[], datetime] | None = None,
        http_get_json: Callable[[str], Any] | None = None,
    ):
        self.config = config or {}
        self.now_provider = now_provider or (lambda: datetime.now(timezone.utc))
        self.http_get_json = http_get_json or self._http_get_json
        self.base_url = self.config.get("exchange_base_url", "https://api.exchange.coinbase.com")
        self.max_symbols = int(self.config.get("max_symbols", 6))
        self.reference_symbols = tuple(self.config.get("reference_symbols", DEFAULT_REFERENCE_SYMBOLS))

    def build_snapshots(
        self,
        wallet_states: dict[str, Any],
        recent_trades: list[dict],
        active_agents: list[str],
        supported_symbols: set[str] | None = None,
    ) -> list[dict]:
        symbols = self._collect_symbols(wallet_states, recent_trades, active_agents, supported_symbols=supported_symbols)
        snapshots = [self.get_snapshot(symbol).to_dict() for symbol in symbols]
        return snapshots

    def get_snapshot(self, symbol: str) -> MarketSnapshot:
        product_id = self._resolve_product_id(symbol)
        if not product_id:
            return MarketSnapshot(symbol=symbol, product_id="", price_usdc=None, return_1h_pct=None, return_4h_pct=None, return_24h_pct=None, volume_24h_usd=None, volatility_24h_pct=None, status="unavailable", note="No Coinbase USD or USDC market")

        try:
            stats = self.http_get_json(f"{self.base_url}/products/{product_id}/stats")
            candles = self._fetch_hourly_candles(product_id)
        except Exception as exc:  # noqa: BLE001
            return MarketSnapshot(symbol=symbol, product_id=product_id, price_usdc=None, return_1h_pct=None, return_4h_pct=None, return_24h_pct=None, volume_24h_usd=None, volatility_24h_pct=None, status="unavailable", note=str(exc))

        closes = [float(candle[4]) for candle in candles]
        price = closes[-1] if closes else _safe_float(stats.get("last"))
        volume_base = _safe_float(stats.get("volume"))
        volume_24h_usd = (volume_base * price) if volume_base is not None and price is not None else None
        return MarketSnapshot(
            symbol=symbol,
            product_id=product_id,
            price_usdc=price,
            return_1h_pct=_period_return(closes, 1),
            return_4h_pct=_period_return(closes, 4),
            return_24h_pct=_period_return(closes, 24),
            volume_24h_usd=volume_24h_usd,
            volatility_24h_pct=_volatility_pct(closes[-24:] if len(closes) >= 24 else closes),
            status="ok",
        )

    def _collect_symbols(
        self,
        wallet_states: dict[str, Any],
        recent_trades: list[dict],
        active_agents: list[str],
        supported_symbols: set[str] | None = None,
    ) -> list[str]:
        ordered: list[str] = []
        seen: set[str] = set()
        supported = {str(symbol).upper() for symbol in (supported_symbols or set())}

        def add(symbol: str | None):
            normalized = str(symbol or "").upper()
            if not normalized or normalized in {"USDC", "USD"} or normalized in seen:
                return
            if supported and normalized not in supported:
                return
            seen.add(normalized)
            ordered.append(normalized)

        for symbol in self.reference_symbols:
            add(symbol)
        for agent_name in active_agents:
            wallet_state = wallet_states.get(agent_name)
            positions = getattr(wallet_state, "positions", {}) if wallet_state is not None else {}
            for symbol in positions.keys():
                add(symbol)
        for trade in recent_trades:
            add(trade.get("symbol"))

        return ordered[: self.max_symbols]

    def _resolve_product_id(self, symbol: str) -> str | None:
        for quote in ("USDC", "USD"):
            product_id = f"{symbol}-{quote}"
            try:
                payload = self.http_get_json(f"{self.base_url}/products/{product_id}")
            except Exception:  # noqa: BLE001
                continue
            if isinstance(payload, dict) and payload.get("id") == product_id:
                return product_id
        return None

    def _fetch_hourly_candles(self, product_id: str) -> list[list[float]]:
        end = self.now_provider().astimezone(timezone.utc)
        start = end - timedelta(hours=30)
        query = urlencode(
            {
                "granularity": 3600,
                "start": start.isoformat().replace("+00:00", "Z"),
                "end": end.isoformat().replace("+00:00", "Z"),
            }
        )
        payload = self.http_get_json(f"{self.base_url}/products/{product_id}/candles?{query}")
        candles = sorted(payload or [], key=lambda row: row[0])
        return candles

    @staticmethod
    def _http_get_json(url: str) -> Any:
        request = Request(url, headers={"User-Agent": "ai-trading-arena-market-data/1.0"})
        try:
            with urlopen(request, timeout=10) as response:
                return json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Market data request failed for {url}") from exc


def _safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _period_return(closes: list[float], hours: int) -> float | None:
    if len(closes) <= hours or closes[-hours - 1] == 0:
        return None
    previous = closes[-hours - 1]
    current = closes[-1]
    return ((current - previous) / previous) * 100


def _volatility_pct(closes: list[float]) -> float | None:
    if len(closes) < 2:
        return None
    returns = []
    for previous, current in zip(closes, closes[1:]):
        if previous == 0:
            continue
        returns.append(((current - previous) / previous) * 100)
    if not returns:
        return None
    mean = sum(returns) / len(returns)
    variance = sum((value - mean) ** 2 for value in returns) / len(returns)
    return variance ** 0.5
