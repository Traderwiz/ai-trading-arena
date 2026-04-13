from __future__ import annotations

import unittest
from datetime import datetime, timezone

from arena.brain.chat_triggers import TriggerBundle
from arena.brain.prompt_builder import (
    build_comms_system_prompt,
    build_comms_user_prompt,
    build_trade_system_prompt,
    build_trade_user_prompt,
    estimate_tokens,
)
from arena.wallet.wallet_manager import Position, WalletState


class PromptBuilderTests(unittest.TestCase):
    def test_trade_system_prompt_contains_execution_rules(self):
        prompt = build_trade_system_prompt("grok")
        self.assertIn("only to make a trade decision", prompt.lower())
        self.assertIn("trade\": null", prompt.lower())
        self.assertIn("concrete market number", prompt.lower())
        self.assertIn("concrete limit number", prompt.lower())
        self.assertIn("best candidate trade", prompt.lower())
        self.assertIn("no_trade_explanation", prompt)
        self.assertIn("compare at least two candidate trades", prompt.lower())

    def test_comms_system_prompt_contains_personality_and_rules(self):
        prompt = build_comms_system_prompt("grok", TriggerBundle([]))
        self.assertIn("you are grok", prompt.lower())
        self.assertIn("respond with only a json object", prompt.lower())
        self.assertIn("current loop context", prompt.lower())
        self.assertIn("Pick exactly one rhetorical angle", prompt)
        self.assertIn("Do not reuse the same rhetorical angle", prompt)

    def test_deepseek_comms_system_prompt_contains_novelty_constraints(self):
        prompt = build_comms_system_prompt("deepseek", TriggerBundle([]))
        self.assertIn("fresh current-loop number", prompt)
        self.assertIn("non-stationary market", prompt)
        self.assertIn("volatility surface analysis", prompt)
        self.assertIn("Sharpe ratio", prompt)
        self.assertIn("statistical significance", prompt)
        self.assertIn("Pick exactly one opening angle", prompt)
        self.assertIn("Do not open with the pattern", prompt)

    def test_trade_user_prompt_contains_required_sections(self):
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
            "market_snapshots": [{"symbol": "ETH", "product_id": "ETH-USD", "price_usdc": 3000, "return_1h_pct": 1.2, "return_4h_pct": -0.5, "return_24h_pct": 4.4, "volume_24h_usd": 1200000, "volatility_24h_pct": 2.1, "status": "ok"}],
            "trade_limits": {
                "max_trade_percent": 0.29,
                "raw_max_buy_notional_usdc": 35.33,
                "max_buy_notional_usdc": 34.8,
                "cash_usdc": 50,
                "symbol_limits": [{"symbol": "ETH", "price_usdc": 3000, "max_buy_quantity": 0.0116, "max_buy_notional_usdc": 34.8}],
            },
            "recent_chat": [{"sender": "deepseek", "message": "Variance."}],
            "alerts": ["Stay alive."],
        }
        prompt = build_trade_user_prompt(
            "grok",
            wallet_state,
            shared_context,
            {"daily_summary": "Day summary", "weekly_summary": "Week summary"},
            {"qualifying_trades": 1, "flag_status": "clear", "warning": ""},
            [{"validation_type": "trade", "rejection_reason": "Too large"}],
        )
        self.assertIn("YOUR PORTFOLIO", prompt)
        self.assertIn("LEADERBOARD", prompt)
        self.assertIn("MARKET SNAPSHOT", prompt)
        self.assertIn("PRECOMPUTED TRADE LIMITS", prompt)
        self.assertIn("DECISION STANDARD", prompt)
        self.assertIn("compare at least two candidates", prompt.lower())
        self.assertIn("Identify the single best candidate trade", prompt)
        self.assertIn("safety buffer", prompt)
        self.assertIn("max_buy_quantity", prompt)
        self.assertIn("ETH-USD", prompt)
        self.assertIn("Too large", prompt)

    def test_comms_user_prompt_contains_group_chat_and_trade_status(self):
        wallet_state = WalletState(agent_name="grok", cash_usdc=100, total_equity_usdc=100, positions={}, timestamp=datetime.now(timezone.utc))
        shared_context = {
            "loop_number": 1,
            "timestamp": "2026-04-10T12:00:00Z",
            "leaderboard": [],
            "recent_trades": [],
            "recent_chat": [{"sender": "x", "message": "A"}],
            "alerts": [],
        }
        prompt = build_comms_user_prompt(
            "grok",
            wallet_state,
            shared_context,
            {"daily_summary": "B", "weekly_summary": "C"},
            {"qualifying_trades": 0, "flag_status": "clear"},
            [],
            TriggerBundle([]),
            trade_context={"decision": {"side": "buy", "quantity": 1, "symbol": "ETH"}, "validation": {"approved": True}},
        )
        self.assertIn("GROUP CHAT", prompt)
        self.assertIn("YOUR RECENT CHAT MESSAGES", prompt)
        self.assertIn("YOUR TRADE STATUS THIS LOOP", prompt)
        self.assertIn("FRESH LOOP FACTS YOU CAN QUOTE", prompt)
        self.assertIn("Proposed trade", prompt)

    def test_comms_prompt_truncates_chat_for_token_budget(self):
        wallet_state = WalletState(agent_name="grok", cash_usdc=100, total_equity_usdc=100, positions={}, timestamp=datetime.now(timezone.utc))
        shared_context = {
            "loop_number": 1,
            "timestamp": "2026-04-10T12:00:00Z",
            "leaderboard": [],
            "recent_trades": [],
            "recent_chat": [{"sender": "x", "message": "A" * 1000} for _ in range(20)],
            "alerts": [],
        }
        prompt = build_comms_user_prompt(
            "grok",
            wallet_state,
            shared_context,
            {"daily_summary": "B" * 1500, "weekly_summary": "C" * 1500},
            {"qualifying_trades": 0, "flag_status": "clear"},
            [],
            TriggerBundle([]),
            trade_context={},
        )
        self.assertLessEqual(estimate_tokens(prompt), 4000)


if __name__ == "__main__":
    unittest.main()
