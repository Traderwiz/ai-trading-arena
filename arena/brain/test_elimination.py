from __future__ import annotations

import unittest
from collections import defaultdict

from arena.brain.elimination import EliminationManager
from arena.wallet.wallet_manager import Position, WalletState


class FakeResponse:
    def __init__(self, data):
        self.data = data


class FakeQuery:
    def __init__(self, table_name, tables):
        self.table_name = table_name
        self.tables = tables
        self.filters = []
        self._order = None
        self._limit = None
        self._update = None
        self._insert = None

    def select(self, columns):  # noqa: ARG002
        return self

    def eq(self, field, value):
        self.filters.append((field, value))
        return self

    def order(self, field, desc=False):
        self._order = (field, desc)
        return self

    def limit(self, count):
        self._limit = count
        return self

    def update(self, payload):
        self._update = payload
        return self

    def insert(self, payload):
        self._insert = payload
        return self

    def execute(self):
        rows = self.tables[self.table_name]
        if self._insert is not None:
            rows.append(dict(self._insert))
            return {"data": [self._insert]}
        matched = [row for row in rows if all(str(row.get(field)) == str(value) for field, value in self.filters)]
        if self._update is not None:
            for row in matched:
                row.update(self._update)
            return {"data": matched}
        if self._order:
            field, desc = self._order
            matched = sorted(matched, key=lambda row: row.get(field), reverse=desc)
        if self._limit is not None:
            matched = matched[: self._limit]
        return FakeResponse(matched)


class FakeSupabase:
    def __init__(self):
        self.tables = defaultdict(list)

    def table(self, table_name):
        return FakeQuery(table_name, self.tables)


class FakeWalletManager:
    def get_wallet_state(self, agent_name):  # noqa: ARG002
        return WalletState(agent_name="grok", cash_usdc=5, total_equity_usdc=5, positions={"ETH": Position("ETH", 0.1, 50, 5)}, timestamp=None)

    def liquidate_all(self, agent_name):  # noqa: ARG002
        return []


class EliminationTests(unittest.TestCase):
    def setUp(self):
        self.supabase = FakeSupabase()
        self.manager = EliminationManager(self.supabase, FakeWalletManager())

    def test_record_equity_counts_consecutive_loops(self):
        state = self.manager.record_equity("grok", 9.5)
        self.assertEqual(state.consecutive_loops_below, 1)
        state = self.manager.record_equity("grok", 8.0)
        self.assertEqual(state.consecutive_loops_below, 2)
        self.assertTrue(self.manager.should_eliminate("grok"))

    def test_record_equity_resets_when_above_threshold(self):
        self.manager.record_equity("grok", 9.5)
        state = self.manager.record_equity("grok", 15.0)
        self.assertEqual(state.consecutive_loops_below, 0)
        self.assertFalse(self.manager.should_eliminate("grok"))

    def test_load_watch_reconstructs_from_standings(self):
        self.supabase.tables["standings"] = [
            {"agent_name": "grok", "total_equity_usdc": 9, "loop_number": 5, "timestamp": "2026-04-09T12:00:00Z"},
            {"agent_name": "grok", "total_equity_usdc": 8, "loop_number": 4, "timestamp": "2026-04-09T11:30:00Z"},
            {"agent_name": "grok", "total_equity_usdc": 20, "loop_number": 3, "timestamp": "2026-04-09T11:00:00Z"},
        ]
        watch = self.manager.load_watch(["grok"])
        self.assertEqual(watch["grok"].consecutive_loops_below, 2)


if __name__ == "__main__":
    unittest.main()
