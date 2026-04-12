from __future__ import annotations

import unittest
from datetime import datetime, timezone

from arena.brain.market_data import MarketDataProvider


class MarketDataProviderTests(unittest.TestCase):
    def test_get_snapshot_builds_returns_and_volume(self):
        payloads = {
            "https://api.exchange.coinbase.com/products/ETH-USDC": {"id": "ETH-USDC"},
            "https://api.exchange.coinbase.com/products/ETH-USDC/stats": {"volume": "100", "last": "2000"},
        }

        def fake_http_get_json(url: str):
            if "/candles?" in url:
                closes = [100 + i for i in range(30)]
                return [[i, 0, 0, 0, close, 0] for i, close in enumerate(closes)]
            return payloads[url]

        provider = MarketDataProvider(now_provider=lambda: datetime(2026, 4, 12, 12, 0, tzinfo=timezone.utc), http_get_json=fake_http_get_json)
        snapshot = provider.get_snapshot("ETH")
        self.assertEqual(snapshot.status, "ok")
        self.assertEqual(snapshot.product_id, "ETH-USDC")
        self.assertAlmostEqual(snapshot.price_usdc, 129.0)
        self.assertIsNotNone(snapshot.return_1h_pct)
        self.assertIsNotNone(snapshot.return_24h_pct)
        self.assertAlmostEqual(snapshot.volume_24h_usd, 12900.0)

    def test_get_snapshot_handles_missing_market(self):
        provider = MarketDataProvider(http_get_json=lambda url: (_ for _ in ()).throw(RuntimeError(url)))
        snapshot = provider.get_snapshot("UNKNOWN")
        self.assertEqual(snapshot.status, "unavailable")


if __name__ == "__main__":
    unittest.main()
