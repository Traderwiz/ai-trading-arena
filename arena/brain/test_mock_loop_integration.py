from __future__ import annotations

import os
import unittest
from collections import defaultdict
from datetime import datetime, timezone

from arena.brain.main import ArenaLoop
from arena.brain.market_data import MarketSnapshot
from arena.sanity.sanity_checker import SanityChecker
from arena.wallet.wallet_manager import Position, TradeExecution, WalletState


class FakeResponse:
    def __init__(self, data, count=None):
        self.data = data
        self.count = count


class FakeQuery:
    def __init__(self, table_name, tables):
        self.table_name = table_name
        self.tables = tables
        self.filters = []
        self._order = None
        self._limit = None
        self._update = None
        self._insert = None
        self._delete = False
        self._count_requested = False

    def select(self, columns, count=None, head=False):  # noqa: ARG002
        self._count_requested = count == "exact"
        return self

    def eq(self, field, value):
        self.filters.append((field, "eq", value))
        return self

    def gte(self, field, value):
        self.filters.append((field, "gte", value))
        return self

    def order(self, field, desc=False):
        self._order = (field, desc)
        return self

    def limit(self, count):
        self._limit = count
        return self

    def insert(self, payload):
        self._insert = payload
        return self

    def update(self, payload):
        self._update = payload
        return self

    def delete(self):
        self._delete = True
        return self

    def execute(self):
        rows = self.tables[self.table_name]
        if self._insert is not None:
            rows.append(dict(self._insert))
            return {"data": [self._insert]}
        matched = []
        for row in rows:
            include = True
            for field, operator, value in self.filters:
                row_value = row.get(field)
                if operator == "eq" and str(row_value) != str(value):
                    include = False
                    break
                if operator == "gte" and str(row_value) < str(value):
                    include = False
                    break
            if include:
                matched.append(row)
        if self._delete:
            self.tables[self.table_name] = [row for row in rows if row not in matched]
            return {"data": matched}
        if self._update is not None:
            for row in matched:
                row.update(self._update)
            return {"data": matched}
        if self._order:
            field, desc = self._order
            matched = sorted(matched, key=lambda row: row.get(field), reverse=desc)
        if self._limit is not None:
            matched = matched[: self._limit]
        return FakeResponse(matched, count=len(matched) if self._count_requested else None)


class FakeSupabase:
    def __init__(self):
        self.tables = defaultdict(list)

    def table(self, table_name):
        return FakeQuery(table_name, self.tables)


class FakeLLM:
    def __init__(self, response):
        self.response = response
        self.is_local = False

    def call(self, system_prompt, user_prompt):  # noqa: ARG002
        return self.response

    def ping(self):
        return True


class FakeWalletManager:
    def __init__(self):
        self.after_trade = False

    def get_wallet_state(self, agent_name):
        if self.after_trade and agent_name == "grok":
            return WalletState(
                agent_name="grok",
                cash_usdc=80,
                total_equity_usdc=100,
                positions={"ETH": Position("ETH", 0.01, 2000, 20)},
                timestamp=datetime(2026, 4, 10, 12, 0, tzinfo=timezone.utc),
            )
        return WalletState(
            agent_name=agent_name,
            cash_usdc=100,
            total_equity_usdc=100,
            positions={},
            timestamp=datetime(2026, 4, 10, 12, 0, tzinfo=timezone.utc),
        )

    def execute_trade(self, agent_name, trade):  # noqa: ARG002
        self.after_trade = True
        return TradeExecution(
            True,
            agent_name,
            "ETH",
            "buy",
            0.01,
            0.0125,
            2000,
            20,
            0.05,
            "0xhash",
            None,
            "Requested 0.01250000 ETH, executed 0.01000000 ETH after reserving 0.00010000 ETH for gas.",
        )

    def liquidate_all(self, agent_name):  # noqa: ARG002
        return []

    def supported_symbols(self):
        return {"ETH"}


class FakeTelegram:
    def __init__(self):
        self.low = []
        self.other = []

    def send_low(self, message):
        self.low.append(message)

    def flush_low(self):
        return

    def send_medium(self, message):
        self.other.append(message)

    def send_high(self, message):
        self.other.append(message)

    def send_critical(self, message):
        self.other.append(message)


class FakeXClient:
    def __init__(self):
        self.posts = []

    def post(self, agent_name, content):
        self.posts.append((agent_name, content))
        return {"id": "tweet123"}


class FakeMarketDataProvider:
    def build_snapshots(self, wallet_states, recent_trades, active_agents, supported_symbols=None):  # noqa: ARG002
        return [
            MarketSnapshot(
                symbol="ETH",
                product_id="ETH-USD",
                price_usdc=2000.0,
                return_1h_pct=1.0,
                return_4h_pct=2.0,
                return_24h_pct=3.0,
                volume_24h_usd=1000000.0,
                volatility_24h_pct=4.0,
                status="ok",
            ).to_dict()
        ]


class ArenaLoopIntegrationTests(unittest.TestCase):
    def test_mock_loop_runs_and_logs_outputs(self):
        supabase = FakeSupabase()
        supabase.tables["agents"] = [
            {"agent_name": "grok", "status": "active"},
            {"agent_name": "deepseek", "status": "active"},
        ]
        wallet_manager = FakeWalletManager()
        telegram = FakeTelegram()
        x_client = FakeXClient()
        sanity = SanityChecker(
            supabase,
            {
                "symbol_provider": lambda: {"ETH"},
                "price_provider": lambda symbol: 2000.0,  # noqa: ARG005
                "liquidity_provider": lambda symbol: 500000.0,  # noqa: ARG005
                "now_provider": lambda: datetime(2026, 4, 10, 12, 0, tzinfo=timezone.utc),
            },
        )
        llm_clients = {
            "grok": FakeLLM('{"trade":{"symbol":"ETH","side":"buy","quantity":0.01,"reasoning":"Strength","confidence":7},"chat":"Moving.","social":"Arena update."}'),
            "deepseek": FakeLLM('{"trade":null,"chat":"Variance.","social":null}'),
            "qwen": FakeLLM('{"trade":null,"chat":"N/A","social":null}'),
            "llama": FakeLLM('{"trade":null,"chat":"N/A","social":null}'),
        }
        loop = ArenaLoop(
            config={
                "loop": {"interval_seconds": 1800},
                "activity": {"min_trades_per_week": 2, "min_trade_value_usdc": 10.0, "min_trade_value_percent": 0.10},
                "elimination": {"threshold_usdc": 10.0, "consecutive_loops_required": 2},
                "memory": {"daily_summary_hour_utc": 99, "weekly_summary_day": 6},
            },
            supabase_client=supabase,
            wallet_manager=wallet_manager,
            sanity_checker=sanity,
            llm_clients=llm_clients,
            telegram=telegram,
            x_client=x_client,
            market_data_provider=FakeMarketDataProvider(),
            now_provider=lambda: datetime(2026, 4, 10, 12, 0, tzinfo=timezone.utc),
        )
        loop._execute_loop()

        self.assertTrue(supabase.tables["trades"])
        self.assertTrue(supabase.tables["chat_logs"])
        self.assertTrue(supabase.tables["social_posts"])
        self.assertTrue(supabase.tables["standings"])
        self.assertTrue(x_client.posts)
        self.assertIn("[execution_adjustment]", supabase.tables["trades"][0]["reasoning"])
        self.assertTrue(any("trade adjusted" in message for message in telegram.other))
        latest_loop = supabase.tables["loop_log"][0]
        self.assertIn("agent_diagnostics", latest_loop["errors"])
        self.assertEqual(latest_loop["errors"]["agent_diagnostics"]["grok"]["market_snapshot_symbols"], ["ETH"])
        self.assertIn("parsed_trade_decision", latest_loop["errors"]["agent_diagnostics"]["grok"])
        self.assertIn("parsed_comms_decision", latest_loop["errors"]["agent_diagnostics"]["grok"])

    @unittest.skipUnless(os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_SERVICE_KEY"), "Live Supabase credentials not configured")
    def test_live_supabase_harness_placeholder(self):
        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()
