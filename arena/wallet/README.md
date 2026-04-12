# Arena Wallet Manager

Files:

- [wallet_manager.py](/C:/Users/gaber/projects/ai_trading_arena/arena/wallet/wallet_manager.py)
- [test_wallet_manager.py](/C:/Users/gaber/projects/ai_trading_arena/arena/wallet/test_wallet_manager.py)

## Purpose

This module isolates Coinbase wallet reads and trade execution from the Arena brain loop. The loop calls `WalletManager`, not AgentKit directly.

## Network

- `base-mainnet`

## SDK note

The spec names `CdpWalletProvider`, but Coinbase's current Python documentation shows `CdpEvmServerWalletProvider` and `CdpEvmServerWalletProviderConfig` for EVM wallets. This implementation uses the documented Python class path and keeps the provider factory injectable for tests and future SDK shifts.

Official source used:
- [Coinbase Wallet Management docs](https://docs.cdp.coinbase.com/agent-kit/core-concepts/wallet-management)

## Config

Expected wallet config keys:

```yaml
wallet:
  cdp_api_key_id: "${CDP_API_KEY_ID}"
  cdp_api_key_secret: "${CDP_API_KEY_SECRET}"
  wallet_secret: "${CDP_WALLET_SECRET}"   # optional in code, but present in current Coinbase Python docs
  network_id: "base-mainnet"
  wallets:
    grok: "0x..."
    deepseek: "0x..."
    qwen: "0x..."
    llama: "0x..."
```

## Provider seam

At runtime, the module expects a provider capable of:

- returning wallet balances
- returning token prices in USDC
- executing a swap from one asset to another

Tests inject a fake provider. Production uses the default AgentKit-backed factory when `coinbase-agentkit` is installed.

## Running tests

From [arena/wallet](/C:/Users/gaber/projects/ai_trading_arena/arena/wallet):

```bash
python -m unittest test_wallet_manager.py
```
