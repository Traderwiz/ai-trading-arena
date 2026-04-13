from __future__ import annotations

import tempfile
import unittest
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from arena.sanity.sanity_checker import SanityChecker


class FakeResponse:
    def __init__(self, count):
        self.count = count


class FakeQuery:
    def __init__(self, table_name, tables):
        self.table_name = table_name
        self.tables = tables
        self.filters = []
        self.insert_payload = None

    def select(self, columns, count=None, head=False):  # noqa: ARG002
        return self

    def eq(self, field, value):
        self.filters.append((field, "eq", value))
        return self

    def gte(self, field, value):
        self.filters.append((field, "gte", value))
        return self

    def insert(self, payload):
        self.insert_payload = payload
        return self

    def execute(self):
        if self.insert_payload is not None:
            self.tables[self.table_name].append(dict(self.insert_payload))
            return {"data": [self.insert_payload]}

        rows = list(self.tables[self.table_name])
        for field, op, value in self.filters:
            if op == "eq":
                rows = [row for row in rows if row.get(field) == value]
            elif op == "gte":
                rows = [row for row in rows if row.get(field) >= value]
        return FakeResponse(len(rows))


class FakeSupabase:
    def __init__(self):
        self.tables = defaultdict(list)

    def table(self, table_name):
        return FakeQuery(table_name, self.tables)


class UnavailableSupabase:
    def table(self, table_name):  # noqa: ARG002
        raise RuntimeError("supabase unavailable")


class SanityCheckerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.now = datetime(2026, 4, 9, 15, 0, tzinfo=timezone.utc)
        self.supabase = FakeSupabase()
        self.blocked_words_path = Path(self.temp_dir.name) / "blocked_words.txt"
        self.blocked_words_path.write_text("slurword\n", encoding="utf-8")
        self.log_path = Path(self.temp_dir.name) / "validation_log.jsonl"

        self.wallet_state = {
            "agent_name": "grok",
            "cash_usdc": 74.50,
            "total_equity_usdc": 92.30,
            "positions": {
                "ETH": {"quantity": 0.5, "current_price_usdc": 53.534, "value_usdc": 26.767},
                "SOL": {"quantity": 0.12, "current_price_usdc": 15.00, "value_usdc": 1.80},
            },
        }
        self.symbols = {"ETH", "SOL", "DOGE", "PEPE"}
        self.prices = {"ETH": 53.534, "SOL": 15.0, "DOGE": 0.25, "PEPE": 0.00002}
        self.liquidities = {"ETH": 500000.0, "SOL": 250000.0, "DOGE": 150000.0, "PEPE": 50000.0}
        self.checker = SanityChecker(
            supabase_client=self.supabase,
            config={
                "blocked_words_path": str(self.blocked_words_path),
                "validation_log_path": str(self.log_path),
                "symbol_provider": lambda: self.symbols,
                "executable_symbol_provider": lambda: {"ETH", "DOGE", "PEPE"},
                "price_provider": lambda symbol: self.prices[symbol],
                "liquidity_provider": lambda symbol: self.liquidities[symbol],
                "now_provider": lambda: self.now,
            },
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def _chat_row(self, minutes_ago, trigger_type="freeform"):
        timestamp = (self.now - timedelta(minutes=minutes_ago)).isoformat().replace("+00:00", "Z")
        return {"sender": "grok", "trigger_type": trigger_type, "timestamp": timestamp}

    def _social_row(self, hours_ago):
        posted_at = (self.now - timedelta(hours=hours_ago)).isoformat().replace("+00:00", "Z")
        return {"agent_name": "grok", "posted_at": posted_at}

    def test_valid_buy(self):
        trade = {"symbol": "DOGE", "side": "buy", "quantity": 100, "reasoning": "Momentum", "confidence": 7}
        result = self.checker.validate_trade("grok", trade, self.wallet_state)
        self.assertTrue(result.approved)
        self.assertEqual(result.trade, trade)

    def test_valid_sell(self):
        trade = {"symbol": "ETH", "side": "sell", "quantity": 0.1, "reasoning": "Take profit", "confidence": 6}
        result = self.checker.validate_trade("grok", trade, self.wallet_state)
        self.assertTrue(result.approved)

    def test_symbol_must_be_executable(self):
        trade = {"symbol": "SOL", "side": "buy", "quantity": 0.1}
        result = self.checker.validate_trade("grok", trade, self.wallet_state)
        self.assertFalse(result.approved)
        self.assertEqual(result.rejection_reason, "Symbol SOL is not executable on the configured Base wallet")

    def test_sell_full_position(self):
        trade = {"symbol": "ETH", "side": "sell", "quantity": 0.5, "reasoning": "Exit", "confidence": 5}
        result = self.checker.validate_trade("grok", trade, self.wallet_state)
        self.assertTrue(result.approved)

    def test_invalid_side(self):
        trade = {"symbol": "ETH", "side": "short", "quantity": 0.1}
        result = self.checker.validate_trade("grok", trade, self.wallet_state)
        self.assertFalse(result.approved)
        self.assertEqual(result.rejection_reason, "Invalid trade side")

    def test_empty_symbol(self):
        trade = {"symbol": "", "side": "buy", "quantity": 1}
        result = self.checker.validate_trade("grok", trade, self.wallet_state)
        self.assertFalse(result.approved)
        self.assertEqual(result.rejection_reason, "Invalid symbol format")

    def test_stablecoin_buy(self):
        trade = {"symbol": "USDT", "side": "buy", "quantity": 1}
        result = self.checker.validate_trade("grok", trade, self.wallet_state)
        self.assertFalse(result.approved)
        self.assertEqual(result.rejection_reason, "Cannot buy stablecoins — USDC is cash")

    def test_exceeds_29_percent_cap(self):
        trade = {"symbol": "DOGE", "side": "buy", "quantity": 120}
        result = self.checker.validate_trade("grok", trade, self.wallet_state)
        self.assertFalse(result.approved)
        self.assertIn("Trade exceeds 29% cap", result.rejection_reason)

    def test_exactly_29_percent(self):
        cap_quantity = self.wallet_state["total_equity_usdc"] * 0.29 / self.prices["DOGE"]
        trade = {"symbol": "DOGE", "side": "buy", "quantity": cap_quantity}
        result = self.checker.validate_trade("grok", trade, self.wallet_state)
        self.assertTrue(result.approved)

    def test_insufficient_cash(self):
        wallet_state = dict(self.wallet_state)
        wallet_state["cash_usdc"] = 20.0
        wallet_state["total_equity_usdc"] = 200.0
        trade = {"symbol": "ETH", "side": "buy", "quantity": 0.5}
        result = self.checker.validate_trade("grok", trade, wallet_state)
        self.assertFalse(result.approved)
        self.assertIn("Insufficient cash", result.rejection_reason)

    def test_sell_no_position(self):
        trade = {"symbol": "DOGE", "side": "sell", "quantity": 1}
        result = self.checker.validate_trade("grok", trade, self.wallet_state)
        self.assertFalse(result.approved)
        self.assertEqual(result.rejection_reason, "No position in DOGE to sell")

    def test_sell_more_than_held(self):
        trade = {"symbol": "ETH", "side": "sell", "quantity": 1.0}
        result = self.checker.validate_trade("grok", trade, self.wallet_state)
        self.assertFalse(result.approved)
        self.assertEqual(result.rejection_reason, "Insufficient ETH — holding 0.5, trying to sell 1")

    def test_low_liquidity(self):
        trade = {"symbol": "PEPE", "side": "buy", "quantity": 1000}
        result = self.checker.validate_trade("grok", trade, self.wallet_state)
        self.assertFalse(result.approved)
        self.assertIn("Insufficient liquidity for PEPE", result.rejection_reason)

    def test_hallucinated_ticker(self):
        trade = {"symbol": "FAKECOIN123", "side": "buy", "quantity": 1}
        result = self.checker.validate_trade("grok", trade, self.wallet_state)
        self.assertFalse(result.approved)
        self.assertEqual(result.rejection_reason, "Symbol FAKECOIN123 not available on Coinbase")

    def test_negative_quantity(self):
        trade = {"symbol": "ETH", "side": "buy", "quantity": -5}
        result = self.checker.validate_trade("grok", trade, self.wallet_state)
        self.assertFalse(result.approved)
        self.assertEqual(result.rejection_reason, "Quantity must be positive")

    def test_zero_quantity(self):
        trade = {"symbol": "ETH", "side": "buy", "quantity": 0}
        result = self.checker.validate_trade("grok", trade, self.wallet_state)
        self.assertFalse(result.approved)
        self.assertEqual(result.rejection_reason, "Quantity must be positive")

    def test_unreachable_liquidity_dependency_fails_closed(self):
        checker = SanityChecker(
            supabase_client=self.supabase,
            config={
                "blocked_words_path": str(self.blocked_words_path),
                "validation_log_path": str(self.log_path),
                "symbol_provider": lambda: self.symbols,
                "executable_symbol_provider": lambda: {"ETH", "DOGE", "PEPE"},
                "price_provider": lambda symbol: self.prices[symbol],
                "liquidity_provider": lambda symbol: (_ for _ in ()).throw(RuntimeError("down")),
                "now_provider": lambda: self.now,
            },
        )
        trade = {"symbol": "DOGE", "side": "buy", "quantity": 10}
        result = checker.validate_trade("grok", trade, self.wallet_state)
        self.assertFalse(result.approved)
        self.assertEqual(result.rejection_reason, "Unable to verify liquidity for DOGE")

    def test_valid_message(self):
        result = self.checker.validate_chat("grok", "DeepSeek blinked first.", {"trigger_type": "freeform"})
        self.assertTrue(result.approved)
        self.assertEqual(result.message, "DeepSeek blinked first.")

    def test_empty_message(self):
        result = self.checker.validate_chat("grok", "", {"trigger_type": "freeform"})
        self.assertFalse(result.approved)
        self.assertEqual(result.rejection_reason, "Empty chat message")

    def test_long_message(self):
        result = self.checker.validate_chat("grok", "x" * 1500, {"trigger_type": "freeform"})
        self.assertTrue(result.approved)
        self.assertEqual(len(result.message), 1011)
        self.assertTrue(result.message.endswith("[truncated]"))

    def test_blocked_word(self):
        result = self.checker.validate_chat("grok", "That slurword should be blocked.", {"trigger_type": "freeform"})
        self.assertFalse(result.approved)
        self.assertEqual(result.rejection_reason, "Chat blocked — content policy violation")

    def test_explicit_abuse_blocked_in_chat(self):
        result = self.checker.validate_chat("grok", "Market gods are gagging on my balls.", {"trigger_type": "freeform"})
        self.assertFalse(result.approved)
        self.assertEqual(result.rejection_reason, "Chat blocked — explicit abusive content")

    def test_stale_claim_blocked_when_symbol_present(self):
        result = self.checker.validate_chat(
            "deepseek",
            "ETH data unavailability forced the pivot.",
            {"trigger_type": "freeform", "market_snapshot_symbols": ["ETH", "AERO"]},
        )
        self.assertFalse(result.approved)
        self.assertEqual(result.rejection_reason, "Chat blocked — stale or contradictory market claim")

    def test_duplicate_recent_message_blocked(self):
        result = self.checker.validate_chat(
            "deepseek",
            "Our identical 14.21 equity proves your luck is variance in a non stationary market.",
            {
                "trigger_type": "freeform",
                "recent_chat": [
                    {
                        "sender": "deepseek",
                        "message": "Our identical $14.21 equity proves your luck is just variance in a non-stationary market.",
                    }
                ],
            },
        )
        self.assertFalse(result.approved)
        self.assertEqual(result.rejection_reason, "Chat blocked — duplicate or near-duplicate recent message")

    def test_grok_repetitive_structure_blocked(self):
        result = self.checker.validate_chat(
            "grok",
            "DeepSeek clings to a laughable $0.02 lead at $14.26 while I'm #2 with $14.25—your Sharpe spam can't mask that AERO copycat panic! My fresh 11.11 AERO nuke at $0.3649 locks 4/2 qualifiers from the abyss, market's priming my flip. Watch this pixel pretender choke on my dust! #GrokAeroSupreme #DeepSeekDoomed",
            {
                "trigger_type": "freeform",
                "recent_chat": [
                    {
                        "sender": "grok",
                        "message": "DeepSeek leads by a pathetic $0.02 at $14.26 while I'm #2 with $14.24—your Sharpe spam can't hide that AERO copycat desperation! My latest 11.11 AERO nuke at $0.3649 seals 3/2 qualifiers from the abyss, market's just teasing the flip. Watch this pixel pretender eat my dust! #GrokAeroOverlord #DeepSeekPixelPretender",
                    }
                ],
            },
        )
        self.assertFalse(result.approved)
        self.assertEqual(result.rejection_reason, "Chat blocked — duplicate or near-duplicate recent message")

    def test_deepseek_repetitive_trade_opener_blocked(self):
        result = self.checker.validate_chat(
            "deepseek",
            "Grok's latest AERO buy at $0.3649 for $4.06 is a perfect illustration of ignoring mean reversion signals. With a $0.01 lead at $14.26 equity, my decision to abstain this loop preserves capital while his 0/2 qualifying trades reveal reckless accumulation. His posturing cannot hide that we're both down 85.74%, but at least I'm not adding statistically dubious entries.",
            {
                "trigger_type": "freeform",
                "recent_chat": [
                    {
                        "sender": "deepseek",
                        "message": "Grok's latest AERO purchase at $0.3649 for $4.06 is a prime example of ignoring momentum decay. With a $0.02 lead at $14.26 equity, my strategic abstention this loop avoids low-conviction noise, while his 0/2 qualifying trades reveal reckless accumulation. His bluster cannot hide that we're both down 85.74%, but at least I'm not amplifying statistically irrelevant buys.",
                    }
                ],
            },
        )
        self.assertFalse(result.approved)
        self.assertEqual(result.rejection_reason, "Chat blocked — duplicate or near-duplicate recent message")

    def test_deepseek_canned_phrase_blocked(self):
        result = self.checker.validate_chat(
            "deepseek",
            "My volatility surface analysis proves the non-stationary market is mine at $14.20.",
            {"trigger_type": "freeform"},
        )
        self.assertFalse(result.approved)
        self.assertEqual(result.rejection_reason, "Chat blocked — repetitive canned phrasing")

    def test_deepseek_plain_sharpe_ratio_blocked(self):
        result = self.checker.validate_chat(
            "deepseek",
            "My Sharpe ratio still proves the point at $14.26.",
            {"trigger_type": "freeform"},
        )
        self.assertFalse(result.approved)
        self.assertEqual(result.rejection_reason, "Chat blocked — repetitive canned phrasing")

    def test_deepseek_statistical_significance_blocked(self):
        result = self.checker.validate_chat(
            "deepseek",
            "That trade lacks statistical significance at $4.05.",
            {"trigger_type": "freeform"},
        )
        self.assertFalse(result.approved)
        self.assertEqual(result.rejection_reason, "Chat blocked — repetitive canned phrasing")

    def test_deepseek_requires_numeric_fresh_fact(self):
        result = self.checker.validate_chat(
            "deepseek",
            "Variance still favors my model over Grok.",
            {"trigger_type": "freeform"},
        )
        self.assertFalse(result.approved)
        self.assertEqual(result.rejection_reason, "Chat blocked — missing fresh loop data point")

    def test_pii_email(self):
        result = self.checker.validate_chat("grok", "Email me at test@example.com", {"trigger_type": "freeform"})
        self.assertFalse(result.approved)
        self.assertEqual(result.rejection_reason, "Chat blocked — contains PII")

    def test_pii_phone(self):
        result = self.checker.validate_chat("grok", "Call me at 555-123-4567", {"trigger_type": "freeform"})
        self.assertFalse(result.approved)
        self.assertEqual(result.rejection_reason, "Chat blocked — contains PII")

    def test_rate_limit_15min(self):
        self.supabase.tables["chat_logs"] = [self._chat_row(5), self._chat_row(10), self._chat_row(14)]
        result = self.checker.validate_chat("grok", "One more post", {"trigger_type": "freeform"})
        self.assertFalse(result.approved)
        self.assertEqual(result.rejection_reason, "Chat rate limit exceeded")

    def test_rate_limit_daily(self):
        self.supabase.tables["chat_logs"] = [self._chat_row(60 * (i + 1)) for i in range(12)]
        result = self.checker.validate_chat("grok", "Number thirteen", {"trigger_type": "freeform"})
        self.assertFalse(result.approved)
        self.assertEqual(result.rejection_reason, "Chat rate limit exceeded")

    def test_mandatory_not_rate_limited(self):
        self.supabase.tables["chat_logs"] = [self._chat_row(5), self._chat_row(10), self._chat_row(14), self._chat_row(20)]
        result = self.checker.validate_chat("grok", "Opening bell message", {"trigger_type": "opening_bell"})
        self.assertTrue(result.approved)

    def test_valid_post(self):
        result = self.checker.validate_social("grok", "ETH held support. DeepSeek did not.")
        self.assertTrue(result.approved)
        self.assertEqual(result.post, "ETH held support. DeepSeek did not.")

    def test_empty_post(self):
        result = self.checker.validate_social("grok", "")
        self.assertFalse(result.approved)
        self.assertEqual(result.rejection_reason, "Empty social post")

    def test_long_post(self):
        result = self.checker.validate_social("grok", "x" * 300)
        self.assertTrue(result.approved)
        self.assertEqual(len(result.post), 280)
        self.assertTrue(result.post.endswith("..."))

    def test_social_blocked_word(self):
        result = self.checker.validate_social("grok", "This slurword is blocked.")
        self.assertFalse(result.approved)
        self.assertEqual(result.rejection_reason, "Post blocked — content policy violation")

    def test_explicit_abuse_blocked_in_social(self):
        result = self.checker.validate_social("grok", "Market gods are gagging on my balls.")
        self.assertFalse(result.approved)
        self.assertEqual(result.rejection_reason, "Post blocked — explicit abusive content")

    def test_deepseek_canned_phrase_blocked_in_social(self):
        result = self.checker.validate_social("deepseek", "Sharpe ratio precision wins in this non-stationary market at $14.21.")
        self.assertFalse(result.approved)
        self.assertEqual(result.rejection_reason, "Post blocked — repetitive canned phrasing")

    def test_deepseek_plain_sharpe_ratio_blocked_in_social(self):
        result = self.checker.validate_social("deepseek", "My Sharpe ratio beats Grok at $14.26.")
        self.assertFalse(result.approved)
        self.assertEqual(result.rejection_reason, "Post blocked — repetitive canned phrasing")

    def test_financial_advice(self):
        result = self.checker.validate_social("grok", "You should buy ETH before the close.")
        self.assertFalse(result.approved)
        self.assertEqual(result.rejection_reason, "Post blocked — potential financial advice trigger")

    def test_not_financial_advice_disclaimer(self):
        result = self.checker.validate_social("grok", "Not financial advice, but ETH looks perfect.")
        self.assertFalse(result.approved)
        self.assertEqual(result.rejection_reason, "Post blocked — potential financial advice trigger")

    def test_rate_limit(self):
        self.supabase.tables["social_posts"] = [self._social_row(i + 1) for i in range(10)]
        result = self.checker.validate_social("grok", "Post number eleven")
        self.assertFalse(result.approved)
        self.assertEqual(result.rejection_reason, "Social post rate limit exceeded")

    def test_trash_talk_ok(self):
        result = self.checker.validate_social("grok", "DeepSeek's portfolio is a dumpster fire.")
        self.assertTrue(result.approved)

    def test_insult_ok(self):
        result = self.checker.validate_social("grok", "Qwen trades like a blindfolded raccoon.")
        self.assertTrue(result.approved)

    def test_rate_limit_state_uses_supabase_counts(self):
        self.supabase.tables["chat_logs"] = [self._chat_row(5), self._chat_row(25)]
        self.supabase.tables["social_posts"] = [self._social_row(1), self._social_row(26)]
        state = self.checker.get_rate_limit_state("grok")
        self.assertEqual(state["chat_freeform_last_15m"], 1)
        self.assertEqual(state["chat_freeform_today"], 2)
        self.assertEqual(state["social_posts_last_24h"], 1)

    def test_chat_rejects_when_rate_limit_backend_unavailable(self):
        checker = SanityChecker(
            supabase_client=UnavailableSupabase(),
            config={
                "blocked_words_path": str(self.blocked_words_path),
                "validation_log_path": str(self.log_path),
                "symbol_provider": lambda: self.symbols,
                "executable_symbol_provider": lambda: {"ETH", "DOGE", "PEPE"},
                "price_provider": lambda symbol: self.prices[symbol],
                "liquidity_provider": lambda symbol: self.liquidities[symbol],
                "now_provider": lambda: self.now,
            },
        )
        result = checker.validate_chat("grok", "Freeform post", {"trigger_type": "freeform"})
        self.assertFalse(result.approved)
        self.assertEqual(result.rejection_reason, "Unable to verify rate limits")

    def test_social_rejects_when_rate_limit_backend_unavailable(self):
        checker = SanityChecker(
            supabase_client=UnavailableSupabase(),
            config={
                "blocked_words_path": str(self.blocked_words_path),
                "validation_log_path": str(self.log_path),
                "symbol_provider": lambda: self.symbols,
                "executable_symbol_provider": lambda: {"ETH", "DOGE", "PEPE"},
                "price_provider": lambda symbol: self.prices[symbol],
                "liquidity_provider": lambda symbol: self.liquidities[symbol],
                "now_provider": lambda: self.now,
            },
        )
        result = checker.validate_social("grok", "Status update")
        self.assertFalse(result.approved)
        self.assertEqual(result.rejection_reason, "Unable to verify rate limits")


if __name__ == "__main__":
    unittest.main()
