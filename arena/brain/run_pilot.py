from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PILOT_CONFIG = Path(__file__).resolve().with_name("arena_config_pilot.yaml")
WALLET_ADDRESSES_PATH = PROJECT_ROOT / "arena" / "setup" / "wallet_addresses.json"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from arena.brain.main import ArenaLoop, load_config


DEFAULT_PILOT_WALLETS = {
    "grok": "0xFb173EEE2532BD7Ecb35dB37CDe928366C22e88f",
    "deepseek": "0x837F0C48609A5c2d5b9224957D2E33C4E91ee5f4",
}


def main() -> None:
    load_dotenv(PROJECT_ROOT / ".env")
    config = load_config(PILOT_CONFIG)
    config["wallet"]["wallets"].update(_load_pilot_wallets())
    arena_loop = ArenaLoop(config=config)
    max_loops = int(os.getenv("PILOT_MAX_LOOPS", arena_loop.config.get("loop", {}).get("max_loops", 96)))

    arena_loop.startup_checks()
    arena_loop.telegram.send_high("🧪 PILOT STARTED: Grok + DeepSeek, $10 each, 48-hour test")

    executed_loops = 0
    try:
        while executed_loops < max_loops and not arena_loop.shutdown_requested:
            arena_loop._execute_loop()
            executed_loops += 1
            if executed_loops < max_loops and not arena_loop.shutdown_requested:
                arena_loop._sleep_until_next_loop()
    finally:
        try:
            arena_loop.telegram.send_high(f"🧪 PILOT COMPLETE: {executed_loops} loops executed")
        finally:
            arena_loop.close()


def _load_pilot_wallets() -> dict[str, str]:
    wallets = dict(DEFAULT_PILOT_WALLETS)
    if not WALLET_ADDRESSES_PATH.exists():
        return wallets

    payload = json.loads(WALLET_ADDRESSES_PATH.read_text(encoding="utf-8"))
    if "arena-grok" in payload:
        wallets["grok"] = payload["arena-grok"]
    if "arena-deepseek" in payload:
        wallets["deepseek"] = payload["arena-deepseek"]
    return wallets


if __name__ == "__main__":
    main()
