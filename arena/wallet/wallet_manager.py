from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from web3 import Web3


USDC_SYMBOL = "USDC"
ETH_SYMBOL = "ETH"
ETH_PSEUDO_ADDRESS = "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE"
RETRY_BACKOFF_SECONDS = (1, 3, 9)


class WalletManagerError(RuntimeError):
    pass


@dataclass
class Position:
    symbol: str
    quantity: float
    current_price_usdc: float
    value_usdc: float


@dataclass
class WalletState:
    agent_name: str
    cash_usdc: float
    total_equity_usdc: float
    positions: dict[str, Position]
    timestamp: datetime


@dataclass
class TradeExecution:
    success: bool
    agent_name: str
    symbol: str
    side: str
    quantity: float
    requested_quantity: float
    price_usdc: float
    usdc_value: float
    fee_usdc: float
    tx_hash: str | None
    error: str | None
    adjustment_note: str | None = None


class WalletManager:
    """Manages Coinbase Agentic Wallets on Base."""

    def __init__(
        self,
        config: dict,
        provider_factory: Callable[[str, dict], Any] | None = None,
        sleep_fn: Callable[[float], None] | None = None,
        now_provider: Callable[[], datetime] | None = None,
    ):
        self.config = config or {}
        self.network_id = self.config.get("network_id", "base-mainnet")
        self.wallets = self.config.get("wallets") or {}
        self.asset_registry = {
            str(symbol).upper(): dict(payload)
            for symbol, payload in (self.config.get("assets") or {}).items()
            if isinstance(payload, dict)
        }
        self.native_gas_reserve_eth = float(self.config.get("native_gas_reserve_eth", 0.0001))
        self.provider_factory = provider_factory or self._default_provider_factory
        self.sleep_fn = sleep_fn or time.sleep
        self.now_provider = now_provider or (lambda: datetime.now(timezone.utc))
        self._providers: dict[str, Any] = {}
        self._cdp_clients: dict[str, Any] = {}
        self._patch_cdp_swap_fee_parser()

    def close(self) -> None:
        for client in self._cdp_clients.values():
            if client is None or not hasattr(client, "close"):
                continue
            try:
                self._await(client.close())
            except Exception:
                continue

    def get_wallet_state(self, agent_name: str) -> WalletState:
        provider = self._get_provider(agent_name)
        raw_balances = self._fetch_balances(provider)

        cash_usdc = 0.0
        positions: dict[str, Position] = {}
        for balance in raw_balances:
            symbol = str(balance.get("symbol") or balance.get("asset") or balance.get("currency") or "").upper()
            quantity = float(balance.get("quantity") or balance.get("balance") or balance.get("amount") or 0.0)
            if not symbol or quantity <= 0:
                continue
            if symbol == USDC_SYMBOL:
                cash_usdc += quantity
                continue
            asset_identifier = balance.get("contract_address") or symbol
            decimals = int(balance.get("decimals", self._token_decimals(symbol)))
            try:
                price_usdc = self._get_price_usdc(provider, asset_identifier, decimals=decimals)
            except Exception:
                price_usdc = 0.0
            positions[symbol] = Position(
                symbol=symbol,
                quantity=quantity,
                current_price_usdc=price_usdc,
                value_usdc=quantity * price_usdc,
            )

        total_equity_usdc = cash_usdc + sum(position.value_usdc for position in positions.values())
        return WalletState(
            agent_name=agent_name,
            cash_usdc=cash_usdc,
            total_equity_usdc=total_equity_usdc,
            positions=positions,
            timestamp=self.now_provider(),
        )

    def execute_trade(self, agent_name: str, trade: dict) -> TradeExecution:
        provider = self._get_provider(agent_name)
        symbol = str(trade.get("symbol", "")).upper()
        side = str(trade.get("side", "")).lower()
        requested_quantity = float(trade.get("quantity", 0.0))
        quantity, adjustment_note = self._adjust_quantity_for_gas_reserve(provider, symbol, side, requested_quantity)
        if quantity <= 0:
            return self._failed_execution(
                agent_name,
                symbol,
                side,
                0.0,
                requested_quantity,
                "Insufficient balance after reserving gas",
                adjustment_note=adjustment_note,
            )
        from_symbol, to_symbol = self._determine_swap_assets(symbol, side)
        price_usdc = self._get_price_usdc(provider, symbol)
        usdc_value = quantity * price_usdc
        from_asset = self._token_address_for_symbol(from_symbol)
        to_asset = self._token_address_for_symbol(to_symbol)
        from_amount = self._trade_from_amount(quantity, side, symbol, price_usdc)

        last_error: Exception | None = None
        for attempt, delay in enumerate((0, *RETRY_BACKOFF_SECONDS), start=1):
            try:
                result = self._swap(provider, from_asset, to_asset, from_amount)
                return self._build_trade_execution(
                    agent_name,
                    symbol,
                    side,
                    quantity,
                    result,
                    requested_quantity=requested_quantity,
                    adjustment_note=adjustment_note,
                    price_usdc=price_usdc,
                    usdc_value=usdc_value,
                )
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                error_message = str(exc)
                if "slippage" in error_message.lower():
                    return self._failed_execution(
                        agent_name,
                        symbol,
                        side,
                        quantity,
                        requested_quantity,
                        "High Slippage",
                        adjustment_note=adjustment_note,
                    )
                if attempt > len(RETRY_BACKOFF_SECONDS):
                    break
                self.sleep_fn(delay or 0)

        return self._failed_execution(
            agent_name,
            symbol,
            side,
            quantity,
            requested_quantity,
            str(last_error) if last_error else "Unknown wallet error",
            adjustment_note=adjustment_note,
        )

    def get_portfolio_value(self, agent_name: str) -> float:
        return self.get_wallet_state(agent_name).total_equity_usdc

    def liquidate_all(self, agent_name: str) -> list[TradeExecution]:
        wallet_state = self.get_wallet_state(agent_name)
        executions: list[TradeExecution] = []
        for symbol, position in wallet_state.positions.items():
            executions.append(
                self.execute_trade(
                    agent_name,
                    {"symbol": symbol, "side": "sell", "quantity": position.quantity},
                )
            )
        return executions

    def _get_provider(self, agent_name: str):
        if agent_name not in self.wallets:
            raise WalletManagerError(f"No wallet configured for {agent_name}")
        if agent_name not in self._providers:
            self._providers[agent_name] = self.provider_factory(agent_name, self.wallet_config(agent_name))
        return self._providers[agent_name]

    def wallet_config(self, agent_name: str) -> dict:
        return {
            "cdp_api_key_id": self.config.get("cdp_api_key_id"),
            "cdp_api_key_secret": self.config.get("cdp_api_key_secret"),
            "wallet_secret": self.config.get("wallet_secret"),
            "network_id": self.network_id,
            "wallet_reference": self.wallets[agent_name],
        }

    def supported_symbols(self) -> set[str]:
        supported = {ETH_SYMBOL}
        supported.update(self.asset_registry.keys())
        try:
            from coinbase_agentkit.action_providers.erc20.constants import TOKEN_ADDRESSES_BY_SYMBOLS
        except ImportError:
            return supported
        supported.update(TOKEN_ADDRESSES_BY_SYMBOLS.get(self.network_id, {}).keys())
        return {str(symbol).upper() for symbol in supported}

    def _default_provider_factory(self, agent_name: str, wallet_config: dict):
        try:
            from coinbase_agentkit import CdpEvmWalletProvider, CdpEvmWalletProviderConfig
        except ImportError as exc:
            raise WalletManagerError(
                "coinbase-agentkit is not installed. Install it or inject a provider_factory."
            ) from exc

        config_kwargs = {
            "api_key_id": wallet_config.get("cdp_api_key_id"),
            "api_key_secret": wallet_config.get("cdp_api_key_secret"),
            "network_id": wallet_config.get("network_id"),
        }
        if wallet_config.get("wallet_secret"):
            config_kwargs["wallet_secret"] = wallet_config["wallet_secret"]
        if wallet_config.get("wallet_reference"):
            config_kwargs["address"] = wallet_config["wallet_reference"]
        provider_config = CdpEvmWalletProviderConfig(**config_kwargs)
        return CdpEvmWalletProvider(provider_config)

    def _fetch_balances(self, provider) -> list[dict]:
        if hasattr(provider, "get_balances"):
            balances = provider.get_balances()
            if isinstance(balances, dict):
                normalized = []
                for symbol, amount in balances.items():
                    normalized.append({"symbol": symbol, "quantity": amount})
                return normalized
            return list(balances)
        elif hasattr(provider, "balances"):
            balances = provider.balances()
            if isinstance(balances, dict):
                normalized = []
                for symbol, amount in balances.items():
                    normalized.append({"symbol": symbol, "quantity": amount})
                return normalized
            return list(balances)
        else:
            return self._fetch_balances_via_cdp(provider)

    def _fetch_balances_via_cdp(self, provider) -> list[dict]:
        account = self._get_cdp_account(provider)
        network = self._cdp_network_name()
        token_result = self._await(account.list_token_balances(network=network))
        payload = []
        for balance in getattr(token_result, "balances", []) or []:
            symbol = getattr(getattr(balance, "token", None), "symbol", None)
            amount = getattr(balance, "amount", None)
            raw_amount = getattr(amount, "amount", 0)
            decimals = getattr(amount, "decimals", 0)
            quantity = float(raw_amount) / (10 ** int(decimals)) if decimals is not None else float(raw_amount)
            payload.append(
                {
                    "symbol": symbol or getattr(getattr(balance, "token", None), "contract_address", ""),
                    "quantity": quantity,
                    "contract_address": getattr(getattr(balance, "token", None), "contract_address", None),
                    "decimals": int(decimals) if decimals is not None else None,
                }
            )

        if hasattr(provider, "get_balance"):
            native_balance = float(provider.get_balance()) / (10**18)
            if native_balance > 0:
                payload.append({"symbol": ETH_SYMBOL, "quantity": native_balance})
        return payload

    def _get_cdp_account(self, provider):
        client = self._get_cdp_client(provider)
        address = provider.get_address() if hasattr(provider, "get_address") else None
        if client is None or address is None:
            raise WalletManagerError("Wallet provider does not expose account balance APIs")
        return self._await(client.evm.get_account(address=address))

    def _get_cdp_client(self, provider):
        cache_key = provider.get_address() if hasattr(provider, "get_address") else None
        if not cache_key:
            return provider.get_client() if hasattr(provider, "get_client") else None
        if cache_key not in self._cdp_clients:
            self._cdp_clients[cache_key] = provider.get_client() if hasattr(provider, "get_client") else None
        return self._cdp_clients[cache_key]

    def _cdp_network_name(self) -> str:
        return "base" if self.network_id == "base-mainnet" else self.network_id

    def _get_price_usdc(self, provider, symbol_or_address: str, decimals: int | None = None) -> float:
        if hasattr(provider, "get_price_usdc"):
            return float(provider.get_price_usdc(symbol_or_address))
        if hasattr(provider, "get_price"):
            return float(provider.get_price(symbol_or_address, quote=USDC_SYMBOL))
        client = self._get_cdp_client(provider)
        taker = provider.get_address() if hasattr(provider, "get_address") else None
        if client is None or taker is None:
            raise WalletManagerError(f"Wallet provider does not expose a pricing method for {symbol_or_address}")
        from_decimals = decimals if decimals is not None else self._token_decimals(symbol_or_address)
        result = self._await(
            client.evm.get_swap_price(
                from_token=self._token_address_for_symbol(symbol_or_address),
                to_token=self._token_address_for_symbol(USDC_SYMBOL),
                from_amount=self._to_base_units(1.0, from_decimals),
                network=self._cdp_network_name(),
                taker=taker,
            )
        )
        to_amount = getattr(result, "to_amount", None)
        if to_amount is None:
            raise WalletManagerError(f"Unable to fetch swap price for {symbol_or_address}")
        return float(to_amount) / (10 ** self._token_decimals(USDC_SYMBOL))

    def _swap(self, provider, from_asset: str, to_asset: str, quantity: int):
        if hasattr(provider, "swap"):
            return provider.swap(from_asset=from_asset, to_asset=to_asset, amount=quantity)
        if hasattr(provider, "execute_trade"):
            return provider.execute_trade(from_asset=from_asset, to_asset=to_asset, amount=quantity)
        try:
            from cdp.actions.evm.send_transaction import send_transaction
            from cdp.evm_transaction_types import TransactionRequestEIP1559
            from cdp.openapi_client.models.create_evm_swap_quote_request import CreateEvmSwapQuoteRequest
            from cdp.openapi_client.models.eip712_domain import EIP712Domain
            from cdp.openapi_client.models.eip712_message import EIP712Message
            from cdp.openapi_client.models.evm_swaps_network import EvmSwapsNetwork
        except ImportError as exc:
            raise WalletManagerError("cdp-sdk swap dependencies are unavailable") from exc

        client = self._get_cdp_client(provider)
        address = provider.get_address() if hasattr(provider, "get_address") else None
        if client is None or address is None:
            raise WalletManagerError("Wallet provider does not expose swap APIs")

        async def execute_swap():
            request = CreateEvmSwapQuoteRequest(
                network=EvmSwapsNetwork(self._cdp_network_name()),
                from_token=from_asset,
                to_token=to_asset,
                from_amount=str(int(quantity)),
                taker=address,
                slippage_bps=100,
            )
            response = await client.api_clients.evm_swaps.create_evm_swap_quote_without_preload_content(request)
            payload = json.loads((await response.read()).decode("utf-8"))
            if not payload.get("liquidityAvailable", False):
                raise WalletManagerError("Swap unavailable: insufficient liquidity")

            permit2 = payload.get("permit2") or {}
            calldata = payload["transaction"]["data"]
            if permit2.get("eip712"):
                typed_data = permit2["eip712"]
                signature = await client.api_clients.evm_accounts.sign_evm_typed_data(
                    address=address,
                    eip712_message=EIP712Message(
                        domain=EIP712Domain(
                            name=typed_data["domain"].get("name"),
                            version=typed_data["domain"].get("version"),
                            chain_id=typed_data["domain"].get("chainId"),
                            verifying_contract=typed_data["domain"].get("verifyingContract"),
                            salt=typed_data["domain"].get("salt"),
                        ),
                        types=typed_data["types"],
                        primary_type=typed_data["primaryType"],
                        message=typed_data["message"],
                    ),
                )
                signature = signature.signature
                sig_hex = signature[2:] if signature.startswith("0x") else signature
                sig_length_hex = f"{len(sig_hex) // 2:064x}"
                calldata = calldata + sig_length_hex + sig_hex

            tx_payload = payload["transaction"]
            tx_request = TransactionRequestEIP1559(
                to=Web3.to_checksum_address(tx_payload["to"]),
                data=calldata,
                value=int(tx_payload.get("value") or 0),
                gas=int(tx_payload["gas"]) if tx_payload.get("gas") else None,
            )
            if tx_payload.get("maxFeePerGas"):
                tx_request.maxFeePerGas = int(tx_payload["maxFeePerGas"])
            if tx_payload.get("maxPriorityFeePerGas"):
                tx_request.maxPriorityFeePerGas = int(tx_payload["maxPriorityFeePerGas"])

            tx_hash = await send_transaction(
                client.api_clients.evm_accounts,
                address,
                tx_request,
                tx_payload.get("network") or self._cdp_network_name(),
            )
            return {"transaction_hash": tx_hash}

        return self._await(execute_swap())

    @staticmethod
    def _determine_swap_assets(symbol: str, side: str) -> tuple[str, str]:
        if side == "buy":
            return USDC_SYMBOL, symbol
        if side == "sell":
            return symbol, USDC_SYMBOL
        raise WalletManagerError(f"Unsupported trade side: {side}")

    def _build_trade_execution(
        self,
        agent_name: str,
        symbol: str,
        side: str,
        quantity: float,
        result: Any,
        requested_quantity: float,
        adjustment_note: str | None = None,
        price_usdc: float | None = None,
        usdc_value: float | None = None,
    ) -> TradeExecution:
        payload = result if isinstance(result, dict) else vars(result)
        tx_hash = payload.get("tx_hash") or payload.get("transaction_hash") or payload.get("hash")
        fee_usdc = float(payload.get("fee_usdc") or payload.get("fee") or 0.0)
        price_usdc = payload.get("price_usdc", price_usdc)
        usdc_value = payload.get("usdc_value", usdc_value)

        if price_usdc is None or usdc_value is None:
            provider = self._get_provider(agent_name)
            market_price = self._get_price_usdc(provider, symbol)
            price_usdc = market_price if price_usdc is None else float(price_usdc)
            usdc_value = quantity * float(price_usdc) if usdc_value is None else float(usdc_value)
        else:
            price_usdc = float(price_usdc)
            usdc_value = float(usdc_value)

        return TradeExecution(
            success=bool(payload.get("success", True)),
            agent_name=agent_name,
            symbol=symbol,
            side=side,
            quantity=quantity,
            requested_quantity=requested_quantity,
            price_usdc=float(price_usdc),
            usdc_value=float(usdc_value),
            fee_usdc=fee_usdc,
            tx_hash=tx_hash,
            error=payload.get("error"),
            adjustment_note=adjustment_note,
        )

    @staticmethod
    def _failed_execution(
        agent_name: str,
        symbol: str,
        side: str,
        quantity: float,
        requested_quantity: float,
        error: str,
        adjustment_note: str | None = None,
    ) -> TradeExecution:
        return TradeExecution(
            success=False,
            agent_name=agent_name,
            symbol=symbol,
            side=side,
            quantity=quantity,
            requested_quantity=requested_quantity,
            price_usdc=0.0,
            usdc_value=0.0,
            fee_usdc=0.0,
            tx_hash=None,
            error=error,
            adjustment_note=adjustment_note,
        )

    def _adjust_quantity_for_gas_reserve(self, provider, symbol: str, side: str, quantity: float) -> tuple[float, str | None]:
        if side != "sell" or symbol != ETH_SYMBOL:
            return quantity, None

        available = self._native_balance_eth(provider) - self.native_gas_reserve_eth
        if available <= 0:
            return 0.0, (
                f"Requested {quantity:.8f} {ETH_SYMBOL}, but {self.native_gas_reserve_eth:.8f} {ETH_SYMBOL} is reserved for gas."
            )
        adjusted = min(quantity, available)
        if adjusted < quantity:
            return adjusted, (
                f"Requested {quantity:.8f} {ETH_SYMBOL}, executed {adjusted:.8f} {ETH_SYMBOL} "
                f"after reserving {self.native_gas_reserve_eth:.8f} {ETH_SYMBOL} for gas."
            )
        return adjusted, None

    def _native_balance_eth(self, provider) -> float:
        if hasattr(provider, "get_balance"):
            return float(provider.get_balance()) / (10**18)
        for balance in self._fetch_balances(provider):
            symbol = str(balance.get("symbol") or "").upper()
            if symbol == ETH_SYMBOL:
                return float(balance.get("quantity") or 0.0)
        return 0.0

    def _trade_from_amount(self, quantity: float, side: str, symbol: str, price_usdc: float) -> int:
        if side == "buy":
            return self._to_base_units(quantity * price_usdc, self._token_decimals(USDC_SYMBOL))
        return self._to_base_units(quantity, self._token_decimals(symbol))

    def _token_address_for_symbol(self, symbol: str) -> str:
        raw_value = str(symbol)
        if raw_value.startswith("0x") and len(raw_value) == 42:
            return raw_value
        normalized = raw_value.upper()
        if normalized == ETH_SYMBOL:
            return ETH_PSEUDO_ADDRESS
        registry_entry = self.asset_registry.get(normalized)
        if registry_entry and registry_entry.get("address"):
            return str(registry_entry["address"])
        try:
            from coinbase_agentkit.action_providers.erc20.constants import TOKEN_ADDRESSES_BY_SYMBOLS
        except ImportError as exc:
            raise WalletManagerError("coinbase-agentkit ERC20 token constants are unavailable") from exc

        address = TOKEN_ADDRESSES_BY_SYMBOLS.get(self.network_id, {}).get(normalized)
        if address:
            return address
        raise WalletManagerError(f"No on-chain token address mapping for symbol {normalized} on {self.network_id}")

    def _token_decimals(self, symbol: str) -> int:
        normalized = str(symbol).upper()
        registry_entry = self.asset_registry.get(normalized)
        if registry_entry and registry_entry.get("decimals") is not None:
            return int(registry_entry["decimals"])
        if normalized in {USDC_SYMBOL, "USDT", "EURC"}:
            return 6
        if normalized in {"BTC", "WBTC", "CBBTC"}:
            return 8
        return 18

    @staticmethod
    def _to_base_units(quantity: float, decimals: int) -> int:
        return int(round(quantity * (10**decimals)))

    @staticmethod
    def _patch_cdp_swap_fee_parser() -> None:
        try:
            from cdp.openapi_client.models.common_swap_response_fees import CommonSwapResponseFees
            from cdp.openapi_client.models.common_swap_response_issues import CommonSwapResponseIssues
            from cdp.openapi_client.models.common_swap_response_issues_allowance import CommonSwapResponseIssuesAllowance
            from cdp.openapi_client.models.common_swap_response_issues_balance import CommonSwapResponseIssuesBalance
            from cdp.openapi_client.models.token_fee import TokenFee
        except ImportError:
            return

        if getattr(CommonSwapResponseFees, "_arena_patched", False):
            return

        @classmethod
        def from_dict(cls, obj):
            if obj is None:
                return None
            if not isinstance(obj, dict):
                return cls.model_validate(obj)

            zero_fee = {"amount": "0", "token": ETH_PSEUDO_ADDRESS}
            gas_fee = obj.get("gasFee") if obj.get("gasFee") is not None else zero_fee
            protocol_fee = obj.get("protocolFee") if obj.get("protocolFee") is not None else zero_fee
            return cls.model_validate(
                {
                    "gasFee": TokenFee.from_dict(gas_fee),
                    "protocolFee": TokenFee.from_dict(protocol_fee),
                }
            )

        CommonSwapResponseFees.from_dict = from_dict
        CommonSwapResponseFees._arena_patched = True

        @classmethod
        def issues_from_dict(cls, obj):
            if obj is None:
                return None
            if not isinstance(obj, dict):
                return cls.model_validate(obj)

            allowance = obj.get("allowance")
            balance = obj.get("balance")
            if allowance is None:
                allowance = {"currentAllowance": "0", "spender": "0x0000000000000000000000000000000000000000"}
            if balance is None:
                balance = {
                    "token": ETH_PSEUDO_ADDRESS,
                    "currentBalance": "0",
                    "requiredBalance": "0",
                }
            return cls.model_validate(
                {
                    "allowance": CommonSwapResponseIssuesAllowance.from_dict(allowance),
                    "balance": CommonSwapResponseIssuesBalance.from_dict(balance),
                    "simulationIncomplete": obj.get("simulationIncomplete", False),
                }
            )

        CommonSwapResponseIssues.from_dict = issues_from_dict
        CommonSwapResponseIssues._arena_patched = True

    @staticmethod
    def _await(coro):
        try:
            return asyncio.run(coro)
        except RuntimeError:
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(coro)
            finally:
                loop.close()
