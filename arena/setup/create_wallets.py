from __future__ import annotations

import asyncio
import json
from pathlib import Path

from dotenv import load_dotenv

try:
    from cdp import CdpClient
except ImportError as exc:  # pragma: no cover
    raise RuntimeError("cdp-sdk is not installed. Run `pip install cdp-sdk python-dotenv`.") from exc


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_PATH = Path(__file__).resolve().parent / "wallet_addresses.json"
WALLET_NAMES = [
    "arena-grok",
    "arena-deepseek",
    "arena-qwen",
    "arena-llama",
]


async def create_wallets() -> dict[str, str]:
    load_dotenv(PROJECT_ROOT / ".env")
    cdp = CdpClient()
    addresses: dict[str, str] = {}
    try:
        for wallet_name in WALLET_NAMES:
            account = await _get_or_create_named_account(cdp, wallet_name)
            addresses[wallet_name] = account.address
            print(f"{wallet_name}: {account.address}")

        OUTPUT_PATH.write_text(json.dumps(addresses, indent=2) + "\n", encoding="utf-8")
        return addresses
    finally:
        await cdp.close()


async def _get_or_create_named_account(cdp: CdpClient, wallet_name: str):
    evm = cdp.evm
    for method_name in ("get_or_create_account", "getOrCreateAccount"):
        method = getattr(evm, method_name, None)
        if method is not None:
            return await method(wallet_name)

    for method_name in ("create_account", "createAccount"):
        method = getattr(evm, method_name, None)
        if method is not None:
            return await method(wallet_name)

    raise RuntimeError("Unable to find a compatible EVM account creation method in cdp-sdk")


if __name__ == "__main__":
    asyncio.run(create_wallets())
