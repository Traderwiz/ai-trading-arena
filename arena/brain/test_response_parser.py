from __future__ import annotations

import unittest

from arena.brain.response_parser import AgentParseError, parse_agent_response, parse_comms_response, parse_trade_response


class ResponseParserTests(unittest.TestCase):
    def test_parses_plain_json(self):
        decision = parse_agent_response('{"trade": null, "chat": "Hello", "social": null}')
        self.assertEqual(decision.chat, "Hello")
        self.assertIsNone(decision.trade)

    def test_parses_markdown_fences(self):
        raw = '```json\n{"trade": {"symbol": "eth", "side": "buy", "quantity": "1", "confidence": "7"}, "chat": "Hi", "social": ""}\n```'
        decision = parse_agent_response(raw)
        self.assertEqual(decision.trade["symbol"], "ETH")
        self.assertEqual(decision.trade["confidence"], 7)
        self.assertIsNone(decision.social)

    def test_parses_leading_and_trailing_text(self):
        raw = 'Here you go:\n{"trade": null, "chat": "Ready", "social": null}\nThanks'
        decision = parse_agent_response(raw)
        self.assertEqual(decision.chat, "Ready")

    def test_defaults_missing_fields(self):
        decision = parse_agent_response('{"chat": ""}')
        self.assertEqual(decision.chat, "...")
        self.assertIsNone(decision.trade)
        self.assertIsNone(decision.social)

    def test_removes_trailing_commas(self):
        raw = '{"trade": null, "chat": "Hello", "social": null,}'
        decision = parse_agent_response(raw)
        self.assertEqual(decision.chat, "Hello")

    def test_raises_on_unparseable_input(self):
        with self.assertRaises(AgentParseError):
            parse_agent_response("not json at all")

    def test_parse_trade_response_accepts_trade_only_shape(self):
        decision = parse_trade_response('{"symbol":"eth","side":"buy","quantity":"1","confidence":"7"}')
        self.assertEqual(decision.trade["symbol"], "ETH")
        self.assertEqual(decision.trade["confidence"], 7)

    def test_parse_comms_response_accepts_comms_shape(self):
        decision = parse_comms_response('{"chat":"Hello","social":null}')
        self.assertEqual(decision.chat, "Hello")
        self.assertIsNone(decision.social)


if __name__ == "__main__":
    unittest.main()
