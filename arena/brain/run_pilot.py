from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import IO

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PILOT_CONFIG = Path(__file__).resolve().with_name("arena_config_pilot.yaml")
WALLET_ADDRESSES_PATH = PROJECT_ROOT / "arena" / "setup" / "wallet_addresses.json"
PILOT_LOCK_PATH = PROJECT_ROOT / "arena" / "brain" / ".pilot.lock"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from arena.brain.main import ArenaLoop, load_config


DEFAULT_PILOT_WALLETS = {
    "grok": "0xFb173EEE2532BD7Ecb35dB37CDe928366C22e88f",
    "deepseek": "0x837F0C48609A5c2d5b9224957D2E33C4E91ee5f4",
}


def main() -> None:
    load_dotenv(PROJECT_ROOT / ".env")
    lock_handle = _acquire_single_instance_lock()
    config = load_config(PILOT_CONFIG)
    config["wallet"]["wallets"].update(_load_pilot_wallets())
    arena_loop = ArenaLoop(config=config)
    max_loops = int(os.getenv("PILOT_MAX_LOOPS", arena_loop.config.get("loop", {}).get("max_loops", 96)))
    retry_delay_seconds = int(os.getenv("PILOT_RETRY_DELAY_SECONDS", "60"))

    arena_loop.startup_checks()
    _safe_telegram_notify(
        arena_loop,
        "high",
        "🧪 PILOT STARTED: Grok + DeepSeek, $10 each, 48-hour test",
    )

    executed_loops = 0
    try:
        while executed_loops < max_loops and not arena_loop.shutdown_requested:
            try:
                arena_loop._execute_loop()
                executed_loops += 1
            except Exception as exc:  # noqa: BLE001
                _safe_telegram_notify(arena_loop, "critical", f"🔴 PILOT LOOP {arena_loop.loop_number} CRASHED: {exc}")
                if arena_loop.shutdown_requested:
                    break
                arena_loop.sleep_fn(retry_delay_seconds)
                continue
            if executed_loops < max_loops and not arena_loop.shutdown_requested:
                arena_loop._sleep_until_next_loop()
    finally:
        try:
            _safe_telegram_notify(arena_loop, "high", f"🧪 PILOT COMPLETE: {executed_loops} loops executed")
        finally:
            try:
                arena_loop.close()
            finally:
                _release_single_instance_lock(lock_handle)


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


def _safe_telegram_notify(arena_loop: ArenaLoop, level: str, message: str) -> None:
    sender = getattr(arena_loop.telegram, f"send_{level}", None)
    if sender is None:
        return
    try:
        sender(message)
    except Exception:
        return


def _acquire_single_instance_lock() -> IO[str]:
    PILOT_LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    handle = PILOT_LOCK_PATH.open("a+", encoding="utf-8")
    try:
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        handle.close()
        raise RuntimeError("Another pilot runner is already active") from exc

    handle.seek(0)
    handle.truncate()
    handle.write(str(os.getpid()))
    handle.flush()
    return handle


def _release_single_instance_lock(handle: IO[str] | None) -> None:
    if handle is None:
        return
    try:
        if os.name == "nt":
            import msvcrt

            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    finally:
        handle.close()
        try:
            PILOT_LOCK_PATH.unlink(missing_ok=True)
        except Exception:
            pass


if __name__ == "__main__":
    main()
