from __future__ import annotations

import unittest
from datetime import datetime, timezone

from arena.wallet.wallet_manager import WalletManager


class FakeProvider:
    def __init__(self):
        self.swap_attempts = 0
        self.last_swap = None
        self.failures = []
        self.balances_payload = [
            {"symbol": "USDC", "quantity": 50},
            {"symbol": "ETH", "quantity": 0.5},
            {"symbol": "AERO", "quantity": 2},
        ]
        self.prices = {"ETH": 2000.0, "AERO": 100.0}

    def get_balances(self):
        return self.balances_payload

    def get_balance(self):
        for balance in self.balances_payload:
            if balance["symbol"] == "ETH":
                return int(float(balance["quantity"]) * (10**18))
        return 0

    def get_price_usdc(self, symbol):
        return self.prices[symbol]

    def swap(self, from_asset, to_asset, amount):
        self.swap_attempts += 1
        self.last_swap = {"from_asset": from_asset, "to_asset": to_asset, "amount": amount}
        if self.failures:
            error = self.failures.pop(0)
            if error is not None:
                raise RuntimeError(error)
        return {
            "success": True,
            "tx_hash": "0xabc",
            "price_usdc": 100.0 if to_asset != "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE" else 2000.0,
            "usdc_value": amount * (100.0 if to_asset != "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE" else 2000.0),
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
                "assets": {
                    "BTC": {
                        "address": "0xcbB7C0000aB88B473b1f5aFd9ef808440eed33Bf",
                        "decimals": 8,
                    }
                },
            },
            provider_factory=lambda agent_name, config: self.provider,  # noqa: ARG005
            sleep_fn=lambda seconds: None,
            now_provider=lambda: datetime(2026, 4, 9, 12, 0, tzinfo=timezone.utc),
        )

    def test_get_wallet_state(self):
        state = self.manager.get_wallet_state("grok")
        self.assertEqual(state.cash_usdc, 50.0)
        self.assertAlmostEqual(state.total_equity_usdc, 1250.0)
        self.assertEqual(set(state.positions.keys()), {"ETH", "AERO"})

    def test_get_portfolio_value(self):
        self.assertAlmostEqual(self.manager.get_portfolio_value("grok"), 1250.0)

    def test_execute_trade_buy(self):
        execution = self.manager.execute_trade("grok", {"symbol": "AERO", "side": "buy", "quantity": 1.5})
        self.assertTrue(execution.success)
        self.assertEqual(execution.tx_hash, "0xabc")
        self.assertEqual(execution.requested_quantity, 1.5)
        self.assertIsNone(execution.adjustment_note)
        self.assertEqual(self.provider.swap_attempts, 1)

    def test_execute_trade_retries_rpc_failures(self):
        self.provider.failures = ["rpc timeout", None]
        execution = self.manager.execute_trade("grok", {"symbol": "AERO", "side": "buy", "quantity": 1})
        self.assertTrue(execution.success)
        self.assertEqual(self.provider.swap_attempts, 2)

    def test_execute_trade_handles_slippage(self):
        self.provider.failures = ["High slippage on route"]
        execution = self.manager.execute_trade("grok", {"symbol": "AERO", "side": "buy", "quantity": 1})
        self.assertFalse(execution.success)
        self.assertEqual(execution.error, "High Slippage")

    def test_liquidate_all(self):
        executions = self.manager.liquidate_all("grok")
        self.assertEqual(len(executions), 2)
        self.assertTrue(all(execution.side == "sell" for execution in executions))

    def test_execute_trade_sell_eth_reserves_gas(self):
        execution = self.manager.execute_trade("grok", {"symbol": "ETH", "side": "sell", "quantity": 0.5})
        self.assertTrue(execution.success)
        self.assertEqual(execution.requested_quantity, 0.5)
        self.assertAlmostEqual(execution.quantity, 0.4999, places=4)
        self.assertIn("executed 0.49990000 ETH", execution.adjustment_note)
        self.assertEqual(self.provider.swap_attempts, 1)
        self.assertEqual(self.provider.last_swap["amount"], int(0.4999 * (10**18)))

    def test_execute_trade_sell_eth_fails_when_only_gas_reserve_left(self):
        self.provider.balances_payload = [
            {"symbol": "USDC", "quantity": 50},
            {"symbol": "ETH", "quantity": 0.00005},
        ]
        execution = self.manager.execute_trade("grok", {"symbol": "ETH", "side": "sell", "quantity": 0.00005})
        self.assertFalse(execution.success)
        self.assertEqual(execution.requested_quantity, 0.00005)
        self.assertEqual(execution.error, "Insufficient balance after reserving gas")
        self.assertIn("reserved for gas", execution.adjustment_note)

    def test_supported_symbols_include_configured_assets(self):
        supported = self.manager.supported_symbols()
        self.assertIn("BTC", supported)
        self.assertIn("ETH", supported)

    def test_configured_asset_alias_routes_to_custom_address(self):
        self.provider.prices["BTC"] = 50000.0
        execution = self.manager.execute_trade("grok", {"symbol": "BTC", "side": "buy", "quantity": 0.0001})
        self.assertTrue(execution.success)
        self.assertEqual(self.provider.last_swap["to_asset"], "0xcbB7C0000aB88B473b1f5aFd9ef808440eed33Bf")


if __name__ == "__main__":
    unittest.main()
