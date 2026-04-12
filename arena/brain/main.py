from __future__ import annotations

import os
import random
import signal
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

try:
    from supabase import create_client
except ImportError:  # pragma: no cover
    create_client = None

from arena.brain.activity_tracker import ActivityTracker
from arena.brain.chat_triggers import determine_chat_triggers
from arena.brain.elimination import EliminationManager
from arena.brain.llm_client import LLMClient, LLMError
from arena.brain.memory_manager import MemoryManager
from arena.brain.prompt_builder import build_system_prompt, build_user_prompt
from arena.brain.response_parser import AgentParseError, parse_agent_response
from arena.brain.telegram_notifier import TelegramNotifier
from arena.brain.x_client import XClient
from arena.sanity.sanity_checker import SanityChecker
from arena.wallet.wallet_manager import WalletManager


AGENT_NAMES = ["grok", "deepseek", "qwen", "llama"]


def load_config(config_path: str | Path) -> dict:
    config_file = Path(config_path)
    raw = yaml.safe_load(config_file.read_text(encoding="utf-8"))
    return _resolve_env(raw)


def init_supabase(config: dict):
    if create_client is None:
        raise RuntimeError("supabase package is not installed")
    supabase_config = config.get("supabase", {})
    return create_client(supabase_config["url"], supabase_config["service_key"])


class ArenaLoop:
    def __init__(
        self,
        config_path: str | Path | None = None,
        config: dict | None = None,
        supabase_client=None,
        wallet_manager: WalletManager | None = None,
        sanity_checker: SanityChecker | None = None,
        llm_clients: dict[str, Any] | None = None,
        telegram: TelegramNotifier | None = None,
        x_client: XClient | None = None,
        activity_tracker: ActivityTracker | None = None,
        memory_manager: MemoryManager | None = None,
        elimination_manager: EliminationManager | None = None,
        now_provider=None,
        sleep_fn=None,
        randomizer=None,
    ):
        config_path = config_path or Path(__file__).with_name("arena_config.yaml")
        self.config = config or load_config(config_path)
        self.now_provider = now_provider or (lambda: datetime.now(timezone.utc))
        self.sleep_fn = sleep_fn or time.sleep
        self.randomizer = randomizer or random
        self.supabase = supabase_client or init_supabase(self.config)
        self.wallet_manager = wallet_manager or WalletManager(self.config.get("wallet", {}))
        self.sanity_checker = sanity_checker or SanityChecker(self.supabase, self.config)
        self.llm_clients = llm_clients or {name: LLMClient(name, self.config) for name in AGENT_NAMES}
        self.telegram = telegram or TelegramNotifier(self.config.get("telegram"))
        self.x_client = x_client or XClient(self.config.get("x_api"))
        self.activity_tracker = activity_tracker or ActivityTracker(self.supabase, self.config, now_provider=self.now_provider)
        self.memory_manager = memory_manager or MemoryManager(self.supabase, self.config, now_provider=self.now_provider)
        self.elimination_manager = elimination_manager or EliminationManager(
            self.supabase,
            self.wallet_manager,
            llm_clients=self.llm_clients,
            x_client=self.x_client,
            telegram=self.telegram,
            sanity_checker=self.sanity_checker,
            config=self.config,
            now_provider=self.now_provider,
        )
        self.loop_interval_seconds = int(self.config.get("loop", {}).get("interval_seconds", 1800))
        self.loop_number = self._get_last_loop_number() + 1
        self.shutdown_requested = False
        self.current_loop_errors: dict[str, Any] = {}
        self.current_loop_fallback_agents: list[str] = []
        self.allowed_agents = list(self.config.get("loop", {}).get("active_agents", AGENT_NAMES))
        self._install_signal_handlers()

    def close(self) -> None:
        try:
            self.wallet_manager.close()
        except Exception:
            pass

    def startup_checks(self) -> None:
        active_agents = self._get_active_agents()
        self._fetch_rows("agents", limit=1)
        for agent_name in active_agents:
            self.wallet_manager.get_wallet_state(agent_name)
        for client in self.llm_clients.values():
            client.ping()
        self.elimination_manager.load_watch(active_agents)
        self.telegram.send_high(f"Arena Brain Loop started. Loop #{self.loop_number}. {len(active_agents)} agents active.")

    def run(self) -> None:
        try:
            while not self.shutdown_requested:
                try:
                    self._execute_loop()
                except Exception as exc:  # noqa: BLE001
                    self.telegram.send_critical(f"🔴 LOOP {self.loop_number} CRASHED: {exc}")
                if not self.shutdown_requested:
                    self._sleep_until_next_loop()
            self.telegram.send_high(f"Arena Brain Loop shutting down after loop #{self.loop_number}.")
        finally:
            self.close()

    def _execute_loop(self) -> None:
        loop_start = self.now_provider()
        active_agents = self._get_active_agents()
        self.current_loop_errors = {}
        self.current_loop_fallback_agents = []
        self._log_loop_start(loop_start, active_agents)

        if len(active_agents) <= 1:
            self._handle_competition_end(active_agents)
            return

        shared_context = self._gather_shared_context(loop_start, active_agents)
        self.randomizer.shuffle(active_agents)
        processed_agents: list[str] = []

        for agent_name in active_agents:
            try:
                self._process_agent(agent_name, shared_context)
                processed_agents.append(agent_name)
            except Exception as exc:  # noqa: BLE001
                self.current_loop_errors[agent_name] = str(exc)
                self.telegram.send_high(f"🔴 {agent_name} loop FAILED: {exc}")
            if self.shutdown_requested:
                break

        self._check_eliminations()
        self._check_activity_compliance(active_agents)
        self._check_memory_generation(active_agents)
        self.telegram.flush_low()
        self._log_loop_complete(processed_agents)
        self.loop_number += 1

    def _process_agent(self, agent_name: str, shared_context: dict) -> None:
        wallet_state = self.wallet_manager.get_wallet_state(agent_name)
        memory = self.memory_manager.get_latest_summaries(agent_name)
        activity = self.activity_tracker.get_status(agent_name)
        rejections = self._get_pending_rejections(agent_name)
        trigger_bundle = shared_context["trigger_bundle"]

        system_prompt = build_system_prompt(agent_name, trigger_bundle)
        user_prompt = build_user_prompt(agent_name, wallet_state, shared_context, memory, activity, rejections, trigger_bundle)
        decision = self._get_agent_decision(agent_name, system_prompt, user_prompt)

        trade_execution = None
        if decision and decision.trade:
            trade_result = self.sanity_checker.validate_trade(agent_name, decision.trade, asdict(wallet_state))
            if trade_result.approved:
                trade_execution = self.wallet_manager.execute_trade(agent_name, decision.trade)
                if trade_execution.success:
                    self._log_trade(agent_name, decision.trade, trade_execution)
                    shared_context["recent_trades"].insert(0, self._trade_row(agent_name, decision.trade, trade_execution))
                    shared_context["recent_trades"] = shared_context["recent_trades"][:10]
                    self.telegram.send_low(
                        f"🔄 {agent_name}: {trade_execution.side} {trade_execution.quantity} {trade_execution.symbol} @ ${trade_execution.price_usdc:.4f} (${trade_execution.usdc_value:.2f})"
                    )
                else:
                    self.current_loop_errors.setdefault(agent_name, {})["trade_execution"] = trade_execution.error
                    self.telegram.send_medium(f"⚠️ {agent_name} trade execution failed: {trade_execution.error}")
            else:
                self.telegram.send_medium(f"⚠️ {agent_name} trade rejected: {trade_result.rejection_reason}")

        chat_posted = False
        if decision:
            chat_result = self.sanity_checker.validate_chat(
                agent_name,
                decision.chat,
                {"trigger_type": trigger_bundle.primary_trigger_type},
            )
            if chat_result.approved:
                self._write_chat(agent_name, chat_result.message, trigger_bundle)
                shared_context["recent_chat"].append({"sender": agent_name, "message": chat_result.message})
                shared_context["recent_chat"] = shared_context["recent_chat"][-20:]
                chat_posted = True

            if decision.social:
                social_result = self.sanity_checker.validate_social(agent_name, decision.social)
                if social_result.approved:
                    post_result = self.x_client.post(agent_name, social_result.post)
                    publish_status = "pending" if post_result.get("status") == "disabled" else "posted"
                    self._log_social(agent_name, social_result.post, post_result.get("id"), status=publish_status)
                    self.telegram.send_low(f"📱 {agent_name}: {social_result.post[:50]}...")
                else:
                    self.telegram.send_medium(f"⚠️ {agent_name} post blocked: {social_result.rejection_reason}")

        updated_wallet = self.wallet_manager.get_wallet_state(agent_name)
        self._write_standings(agent_name, updated_wallet)
        self._replace_positions(agent_name, updated_wallet)
        self.activity_tracker.update_activity(
            agent_name,
            asdict(trade_execution) if trade_execution and trade_execution.success else None,
            updated_wallet.total_equity_usdc,
            chat_posted=chat_posted,
        )
        self.elimination_manager.record_equity(agent_name, updated_wallet.total_equity_usdc, updated_wallet.timestamp.isoformat())

    def _get_agent_decision(self, agent_name: str, system_prompt: str, user_prompt: str):
        raw_response = self._call_llm(agent_name, system_prompt, user_prompt)
        try:
            return parse_agent_response(raw_response)
        except AgentParseError:
            retry_prompt = user_prompt + "\nYour previous response was not valid JSON. Respond with ONLY a JSON object."
            try:
                return parse_agent_response(self._call_llm(agent_name, system_prompt, retry_prompt))
            except Exception:  # noqa: BLE001
                self._write_fallback_chat(agent_name)
                return None

    def _call_llm(self, agent_name: str, system_prompt: str, user_prompt: str) -> str:
        client = self.llm_clients[agent_name]
        try:
            return client.call(system_prompt, user_prompt)
        except LLMError as exc:
            if getattr(client, "is_local", False):
                self.current_loop_fallback_agents.append(agent_name)
                self.telegram.send_high(f"🔴 LM Studio down — {agent_name} on fallback")
                return self.llm_clients["deepseek"].call(system_prompt, user_prompt)
            raise exc

    def _gather_shared_context(self, now: datetime, active_agents: list[str]) -> dict:
        leaderboard = self._fetch_rows("leaderboard")
        recent_chat = list(reversed(self._fetch_rows("chat_logs", order=("timestamp", True), limit=20)))
        recent_trades = self._fetch_rows("trades", order=("timestamp", True), limit=10)
        current_standings = self._fetch_rows("current_standings")
        previous_standings = self._get_previous_standings(active_agents)
        alerts = self._get_system_alerts(active_agents)
        trigger_bundle = determine_chat_triggers(now, recent_trades, current_standings, previous_standings, active_agents)
        return {
            "loop_number": self.loop_number,
            "timestamp": now.isoformat().replace("+00:00", "Z"),
            "leaderboard": leaderboard,
            "recent_chat": recent_chat,
            "recent_trades": recent_trades,
            "current_standings": current_standings,
            "alerts": alerts,
            "trigger_bundle": trigger_bundle,
        }

    def _get_previous_standings(self, active_agents: list[str]) -> list[dict]:
        rows = []
        for agent_name in active_agents:
            history = self._fetch_rows("standings", {"agent_name": agent_name}, order=("timestamp", True), limit=2)
            if len(history) >= 2:
                rows.append(history[1])
        return rows

    def _get_system_alerts(self, active_agents: list[str]) -> list[str]:
        alerts = []
        for agent_name in active_agents:
            status = self.activity_tracker.get_status(agent_name)
            if status.warning:
                alerts.append(f"{agent_name}: {status.warning}")
            state = self.elimination_manager.watch.get(agent_name)
            if state and state.consecutive_loops_below:
                alerts.append(f"{agent_name}: {state.consecutive_loops_below} loop(s) at or below elimination threshold")
        return alerts

    def _get_active_agents(self) -> list[str]:
        rows = self._fetch_rows("agents", {"status": "active"})
        allowed = set(self.allowed_agents)
        return [row["agent_name"] for row in rows if row["agent_name"] in allowed]

    def _get_last_loop_number(self) -> int:
        rows = self._fetch_rows("loop_log", order=("loop_number", True), limit=1)
        return int(rows[0]["loop_number"]) if rows else 0

    def _get_pending_rejections(self, agent_name: str) -> list[dict]:
        return self._fetch_rows("validation_log", {"agent_name": agent_name, "approved": False}, order=("timestamp", True), limit=3)

    def _log_loop_start(self, loop_start: datetime, active_agents: list[str]) -> None:
        self.supabase.table("loop_log").insert(
            {
                "loop_number": self.loop_number,
                "started_at": loop_start.isoformat(),
                "agents_processed": active_agents,
                "errors": {},
                "token_usage": {},
            }
        ).execute()

    def _log_loop_complete(self, processed_agents: list[str]) -> None:
        payload = {
            "completed_at": self.now_provider().isoformat(),
            "agents_processed": processed_agents,
            "errors": {
                "agent_errors": self.current_loop_errors,
                "fallback_mode": self.current_loop_fallback_agents,
            },
        }
        self.supabase.table("loop_log").update(payload).eq("loop_number", self.loop_number).execute()

    def _log_trade(self, agent_name: str, trade: dict, execution) -> None:
        self.supabase.table("trades").insert(
            {
                "agent_name": agent_name,
                "symbol": execution.symbol,
                "side": execution.side,
                "quantity": execution.quantity,
                "price_usdc": execution.price_usdc,
                "usdc_value": execution.usdc_value,
                "fee_usdc": execution.fee_usdc,
                "tx_hash": execution.tx_hash,
                "loop_number": self.loop_number,
                "reasoning": trade.get("reasoning"),
                "confidence": trade.get("confidence"),
            }
        ).execute()

    def _write_chat(self, agent_name: str, message: str, trigger_bundle) -> None:
        self.supabase.table("chat_logs").insert(
            {
                "sender": agent_name,
                "message": message,
                "trigger_type": trigger_bundle.primary_trigger_type,
                "loop_number": self.loop_number,
                "metadata": {"triggers": [trigger.name for trigger in trigger_bundle.triggers]},
            }
        ).execute()

    def _write_fallback_chat(self, agent_name: str) -> None:
        self.supabase.table("chat_logs").insert(
            {
                "sender": agent_name,
                "message": f"[{agent_name} experienced a technical difficulty this loop]",
                "trigger_type": "freeform",
                "loop_number": self.loop_number,
            }
        ).execute()

    def _log_social(self, agent_name: str, content: str, x_post_id: str | None, status: str = "posted") -> None:
        self.supabase.table("social_posts").insert(
            {
                "agent_name": agent_name,
                "platform": "x",
                "content": content,
                "x_post_id": x_post_id,
                "status": status,
                "loop_number": self.loop_number,
            }
        ).execute()

    def _write_standings(self, agent_name: str, wallet_state) -> None:
        pnl_percent = ((wallet_state.total_equity_usdc - 100.0) / 100.0) * 100
        invested = sum(position.value_usdc for position in wallet_state.positions.values())
        self.supabase.table("standings").insert(
            {
                "agent_name": agent_name,
                "timestamp": wallet_state.timestamp.isoformat(),
                "total_equity_usdc": wallet_state.total_equity_usdc,
                "cash_usdc": wallet_state.cash_usdc,
                "invested_usdc": invested,
                "pnl_percent": pnl_percent,
                "num_positions": len(wallet_state.positions),
                "loop_number": self.loop_number,
            }
        ).execute()

    def _replace_positions(self, agent_name: str, wallet_state) -> None:
        try:
            self.supabase.table("positions").delete().eq("agent_name", agent_name).execute()
        except Exception:  # noqa: BLE001
            pass
        for position in wallet_state.positions.values():
            self.supabase.table("positions").insert(
                {
                    "agent_name": agent_name,
                    "symbol": position.symbol,
                    "quantity": position.quantity,
                    "current_price_usdc": position.current_price_usdc,
                    "current_value_usdc": position.value_usdc,
                }
            ).execute()

    def _check_eliminations(self) -> None:
        for agent_name in self.elimination_manager.get_ready_agents():
            self.elimination_manager.trigger_elimination(agent_name, self.loop_number, elimination_type="financial")

    def _check_activity_compliance(self, active_agents: list[str]) -> None:
        events = self.activity_tracker.evaluate_weekly_compliance(active_agents)
        for event in events:
            self.telegram.send_medium(f"🟡 {event.agent_name} {event.flag_status.upper()} FLAG: {event.details}")
            if event.elimination_required:
                self.elimination_manager.trigger_elimination(event.agent_name, self.loop_number, elimination_type="inactivity")

    def _check_memory_generation(self, active_agents: list[str]) -> None:
        self.memory_manager.generate_due_summaries(active_agents)

    def _handle_competition_end(self, active_agents: list[str]) -> None:
        if len(active_agents) == 1:
            self.telegram.send_critical(f"🏆 WINNER: {active_agents[0]} - competition complete")
        else:
            self.telegram.send_critical("🏆 Competition ended with no active agents remaining.")

    def _trade_row(self, agent_name: str, trade: dict, execution) -> dict:
        return {
            "agent_name": agent_name,
            "symbol": execution.symbol,
            "side": execution.side,
            "quantity": execution.quantity,
            "price_usdc": execution.price_usdc,
            "usdc_value": execution.usdc_value,
            "loop_number": self.loop_number,
            "reasoning": trade.get("reasoning"),
            "confidence": trade.get("confidence"),
        }

    def _fetch_rows(self, table_name: str, filters: dict | None = None, order: tuple[str, bool] | None = None, limit: int | None = None) -> list[dict]:
        query = self.supabase.table(table_name).select("*")
        for field, value in (filters or {}).items():
            query = query.eq(field, value)
        if order:
            query = query.order(order[0], desc=order[1])
        if limit:
            query = query.limit(limit)
        response = query.execute()
        if isinstance(response, dict):
            return response.get("data", [])
        return getattr(response, "data", [])

    def _sleep_until_next_loop(self) -> None:
        self.sleep_fn(self.loop_interval_seconds)

    def _install_signal_handlers(self) -> None:
        def handle_signal(signum, frame):  # noqa: ARG001
            self.shutdown_requested = True

        for sig in (getattr(signal, "SIGINT", None), getattr(signal, "SIGTERM", None)):
            if sig is None:
                continue
            try:
                signal.signal(sig, handle_signal)
            except ValueError:
                continue


def _resolve_env(value):
    if isinstance(value, dict):
        return {key: _resolve_env(val) for key, val in value.items()}
    if isinstance(value, list):
        return [_resolve_env(item) for item in value]
    if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
        return os.getenv(value[2:-1], value)
    return value


if __name__ == "__main__":  # pragma: no cover
    loop = ArenaLoop()
    loop.startup_checks()
    loop.run()
