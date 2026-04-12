from __future__ import annotations

import unittest
from collections import defaultdict
from datetime import datetime, timezone

from arena.brain.activity_tracker import ActivityTracker, current_week_start


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

    def insert(self, payload):
        self._insert = payload
        return self

    def update(self, payload):
        self._update = payload
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


class ActivityTrackerTests(unittest.TestCase):
    def setUp(self):
        self.supabase = FakeSupabase()
        self.now = datetime(2026, 4, 12, 23, 0, tzinfo=timezone.utc)
        self.tracker = ActivityTracker(self.supabase, now_provider=lambda: self.now)

    def test_current_week_start_monday(self):
        self.assertEqual(current_week_start(datetime(2026, 4, 12, 12, 0, tzinfo=timezone.utc)).isoformat(), "2026-04-06")

    def test_update_activity_counts_qualifying_trade(self):
        status = self.tracker.update_activity(
            "grok",
            {"symbol": "ETH", "usdc_value": 15, "success": True},
            total_equity_usdc=100,
            chat_posted=True,
            now=self.now,
        )
        self.assertEqual(status.qualifying_trades, 1)
        self.assertEqual(status.daily_chats_completed, 1)

    def test_trade_below_threshold_does_not_count(self):
        status = self.tracker.update_activity(
            "grok",
            {"symbol": "ETH", "usdc_value": 5, "success": True},
            total_equity_usdc=100,
            now=self.now,
        )
        self.assertEqual(status.qualifying_trades, 0)

    def test_weekly_escalation_reaches_elimination(self):
        self.supabase.tables["activity_tracking"] = [
            {"agent_name": "grok", "week_start": "2026-04-06", "qualifying_trades": 0, "daily_chats_completed": 0, "flag_status": "clear"},
            {"agent_name": "grok", "week_start": "2026-03-30", "qualifying_trades": 0, "daily_chats_completed": 0, "flag_status": "red"},
            {"agent_name": "grok", "week_start": "2026-03-23", "qualifying_trades": 0, "daily_chats_completed": 0, "flag_status": "yellow"},
        ]
        events = self.tracker.evaluate_weekly_compliance(["grok"], now=self.now)
        self.assertEqual(events[0].flag_status, "eliminated")
        self.assertTrue(events[0].elimination_required)


if __name__ == "__main__":
    unittest.main()
