from __future__ import annotations

import unittest
from datetime import datetime, timezone

from arena.wallet.wallet_manager import WalletManager


class FakeProvider:
    def __init__(self):
        self.swap_attempts = 0
        self.failures = []
        self.balances_payload = [
            {"symbol": "USDC", "quantity": 50},
            {"symbol": "ETH", "quantity": 0.5},
            {"symbol": "SOL", "quantity": 2},
        ]
        self.prices = {"ETH": 2000.0, "SOL": 100.0}

    def get_balances(self):
        return self.balances_payload

    def get_price_usdc(self, symbol):
        return self.prices[symbol]

    def swap(self, from_asset, to_asset, amount):
        self.swap_attempts += 1
        if self.failures:
            error = self.failures.pop(0)
            if error is not None:
                raise RuntimeError(error)
        return {
            "success": True,
            "tx_hash": "0xabc",
            "price_usdc": 100.0 if to_asset == "SOL" else 2000.0,
            "usdc_value": amount * (100.0 if to_asset == "SOL" else 2000.0),
            "fee_usdc": 0.25,
        }


class WalletManagerTests(unittest.TestCase):
    def setUp(self):
        self.provider = FakeProvider()
        self.manager = WalletManager(
            {
                "cdp_api_key_id": "id",
                "cdp_api_key_secret": "secret",
                "wallets": {"grok": "0xwallet"},
                "network_id": "base-mainnet",
            },
            provider_factory=lambda agent_name, config: self.provider,  # noqa: ARG005
            sleep_fn=lambda seconds: None,
            now_provider=lambda: datetime(2026, 4, 9, 12, 0, tzinfo=timezone.utc),
        )

    def test_get_wallet_state(self):
        state = self.manager.get_wallet_state("grok")
        self.assertEqual(state.cash_usdc, 50.0)
        self.assertAlmostEqual(state.total_equity_usdc, 1250.0)
        self.assertEqual(set(state.positions.keys()), {"ETH", "SOL"})

    def test_get_portfolio_value(self):
        self.assertAlmostEqual(self.manager.get_portfolio_value("grok"), 1250.0)

    def test_execute_trade_buy(self):
        execution = self.manager.execute_trade("grok", {"symbol": "SOL", "side": "buy", "quantity": 1.5})
        self.assertTrue(execution.success)
        self.assertEqual(execution.tx_hash, "0xabc")
        self.assertEqual(self.provider.swap_attempts, 1)

    def test_execute_trade_retries_rpc_failures(self):
        self.provider.failures = ["rpc timeout", None]
        execution = self.manager.execute_trade("grok", {"symbol": "SOL", "side": "buy", "quantity": 1})
        self.assertTrue(execution.success)
        self.assertEqual(self.provider.swap_attempts, 2)

    def test_execute_trade_handles_slippage(self):
        self.provider.failures = ["High slippage on route"]
        execution = self.manager.execute_trade("grok", {"symbol": "SOL", "side": "buy", "quantity": 1})
        self.assertFalse(execution.success)
        self.assertEqual(execution.error, "High Slippage")

    def test_liquidate_all(self):
        executions = self.manager.liquidate_all("grok")
        self.assertEqual(len(executions), 2)
        self.assertTrue(all(execution.side == "sell" for execution in executions))


if __name__ == "__main__":
    unittest.main()
