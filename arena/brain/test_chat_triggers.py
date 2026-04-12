from __future__ import annotations

import unittest
from datetime import datetime, timezone

from arena.brain.chat_triggers import determine_chat_triggers


class ChatTriggerTests(unittest.TestCase):
    def test_opening_bell_trigger(self):
        bundle = determine_chat_triggers(datetime(2026, 4, 10, 0, 0, tzinfo=timezone.utc))
        self.assertIn("opening bell", bundle.instruction_text.lower())

    def test_weekly_roast_trigger(self):
        bundle = determine_chat_triggers(
            datetime(2026, 4, 11, 18, 0, tzinfo=timezone.utc),
            active_agents=["grok", "deepseek", "qwen"],
        )
        self.assertIn("roast session", bundle.instruction_text.lower())

    def test_trade_reaction_trigger(self):
        bundle = determine_chat_triggers(
            datetime(2026, 4, 10, 12, 0, tzinfo=timezone.utc),
            recent_trades=[{"agent_name": "grok", "symbol": "ETH", "side": "buy", "quantity": 0.1, "usdc_value": 25}],
        )
        self.assertIn("react", bundle.instruction_text.lower())

    def test_big_move_trigger(self):
        bundle = determine_chat_triggers(
            datetime(2026, 4, 10, 12, 0, tzinfo=timezone.utc),
            current_standings=[{"agent_name": "grok", "total_equity_usdc": 120}],
            previous_standings=[{"agent_name": "grok", "total_equity_usdc": 100}],
        )
        self.assertIn("moved up", bundle.instruction_text.lower())

    def test_multiple_triggers_accumulate(self):
        bundle = determine_chat_triggers(
            datetime(2026, 4, 12, 18, 0, tzinfo=timezone.utc),
            recent_trades=[{"agent_name": "grok", "symbol": "ETH", "side": "buy", "quantity": 0.1, "usdc_value": 25}],
        )
        self.assertGreaterEqual(len(bundle.triggers), 2)


if __name__ == "__main__":
    unittest.main()
