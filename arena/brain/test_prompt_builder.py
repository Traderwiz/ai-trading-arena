from __future__ import annotations

import unittest
from datetime import datetime, timezone

from arena.brain.chat_triggers import TriggerBundle
from arena.brain.prompt_builder import build_system_prompt, build_user_prompt, estimate_tokens
from arena.wallet.wallet_manager import Position, WalletState


class PromptBuilderTests(unittest.TestCase):
    def test_system_prompt_contains_personality_and_rules(self):
        prompt = build_system_prompt("grok", TriggerBundle([]))
        self.assertIn("you are grok", prompt.lower())
        self.assertIn("respond with only the json object", prompt.lower())

    def test_user_prompt_contains_required_sections(self):
        wallet_state = WalletState(
            agent_name="grok",
            cash_usdc=50,
            total_equity_usdc=120,
            positions={"ETH": Position(symbol="ETH", quantity=0.01, current_price_usdc=3000, value_usdc=30)},
            timestamp=datetime(2026, 4, 10, 12, 0, tzinfo=timezone.utc),
        )
        shared_context = {
            "loop_number": 10,
            "timestamp": "2026-04-10T12:00:00Z",
            "leaderboard": [{"rank": 1, "display_name": "Grok", "total_equity_usdc": 120, "pnl_percent": 20, "status": "active"}],
            "recent_trades": [{"agent_name": "grok", "side": "buy", "quantity": 0.01, "symbol": "ETH", "price_usdc": 3000, "usdc_value": 30}],
            "recent_chat": [{"sender": "deepseek", "message": "Variance."}],
            "alerts": ["Stay alive."],
        }
        prompt = build_user_prompt(
            "grok",
            wallet_state,
            shared_context,
            {"daily_summary": "Day summary", "weekly_summary": "Week summary"},
            {"qualifying_trades": 1, "flag_status": "clear", "warning": ""},
            [{"validation_type": "trade", "rejection_reason": "Too large"}],
            TriggerBundle([]),
        )
        self.assertIn("YOUR PORTFOLIO", prompt)
        self.assertIn("LEADERBOARD", prompt)
        self.assertIn("GROUP CHAT", prompt)
        self.assertIn("Too large", prompt)

    def test_prompt_truncates_chat_for_token_budget(self):
        wallet_state = WalletState(agent_name="grok", cash_usdc=100, total_equity_usdc=100, positions={}, timestamp=datetime.now(timezone.utc))
        shared_context = {
            "loop_number": 1,
            "timestamp": "2026-04-10T12:00:00Z",
            "leaderboard": [],
            "recent_trades": [],
            "recent_chat": [{"sender": "x", "message": "A" * 1000} for _ in range(20)],
            "alerts": [],
        }
        prompt = build_user_prompt(
            "grok",
            wallet_state,
            shared_context,
            {"daily_summary": "B" * 1500, "weekly_summary": "C" * 1500},
            {"qualifying_trades": 0, "flag_status": "clear"},
            [],
            TriggerBundle([]),
        )
        self.assertLessEqual(estimate_tokens(prompt), 4000)


if __name__ == "__main__":
    unittest.main()
