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
from arena.brain.market_data import MarketDataProvider
from arena.brain.memory_manager import MemoryManager
from arena.brain.prompt_builder import (
    build_comms_system_prompt,
    build_comms_user_prompt,
    build_trade_system_prompt,
    build_trade_user_prompt,
)
from arena.brain.response_parser import AgentParseError, parse_comms_response, parse_trade_response
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
        market_data_provider: MarketDataProvider | None = None,
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
        if sanity_checker is not None:
            self.sanity_checker = sanity_checker
        else:
            sanity_config = dict(self.config)
            sanity_config["executable_symbol_provider"] = self.wallet_manager.supported_symbols
            self.sanity_checker = SanityChecker(self.supabase, sanity_config)
        self.llm_clients = llm_clients or {name: LLMClient(name, self.config) for name in AGENT_NAMES}
        self.telegram = telegram or TelegramNotifier(self.config.get("telegram"))
        self.x_client = x_client or XClient(self.config.get("x_api"))
        self.activity_tracker = activity_tracker or ActivityTracker(self.supabase, self.config, now_provider=self.now_provider)
        self.memory_manager = memory_manager or MemoryManager(self.supabase, self.config, now_provider=self.now_provider)
        self.market_data_provider = market_data_provider or MarketDataProvider(
            self.config.get("market_data"),
            now_provider=self.now_provider,
        )
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
        self.starting_capital_usdc = float(self.config.get("competition", {}).get("starting_capital_usdc", 10.0))
        self.loop_number = self._get_last_loop_number() + 1
        self.shutdown_requested = False
        self.current_loop_errors: dict[str, Any] = {}
        self.current_loop_fallback_agents: list[str] = []
        self.current_loop_diagnostics: dict[str, Any] = {}
        self.current_loop_token_usage: dict[str, Any] = {}
        self.current_loop_chat_posts: list[dict[str, Any]] = []
        self.current_loop_trade_posts: list[dict[str, Any]] = []
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
        self.current_loop_diagnostics = {}
        self.current_loop_token_usage = {}
        self.current_loop_chat_posts = []
        self.current_loop_trade_posts = []
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
        self._write_loop_commentary_if_needed(processed_agents)
        self.telegram.flush_low()
        self._log_loop_complete(processed_agents)
        self.loop_number += 1

    def _process_agent(self, agent_name: str, shared_context: dict) -> None:
        wallet_state = self.wallet_manager.get_wallet_state(agent_name)
        diagnostics = {
            "pre_wallet": self._wallet_summary(wallet_state),
            "market_snapshot_symbols": [row.get("symbol") for row in shared_context.get("market_snapshots", [])],
        }
        memory = self.memory_manager.get_latest_summaries(agent_name)
        activity = self.activity_tracker.get_status(agent_name)
        rejections = self._get_pending_rejections(agent_name)
        trigger_bundle = shared_context["trigger_bundle"]
        agent_shared_context = dict(shared_context)
        agent_shared_context["trade_limits"] = self._trade_limits_for_agent(agent_name, wallet_state, shared_context)

        trade_system_prompt = build_trade_system_prompt(agent_name)
        trade_user_prompt = build_trade_user_prompt(agent_name, wallet_state, agent_shared_context, memory, activity, rejections)
        trade_decision, trade_raw_response = self._get_trade_decision(agent_name, trade_system_prompt, trade_user_prompt)
        diagnostics["trade_raw_response"] = self._truncate_text(trade_raw_response)
        diagnostics["parsed_trade_decision"] = trade_decision.trade if trade_decision else None
        diagnostics["parsed_no_trade_explanation"] = trade_decision.no_trade_explanation if trade_decision else None
        trade_usage = self._llm_usage(agent_name)

        trade_execution = None
        trade_result = None
        if trade_decision and trade_decision.trade:
            trade_result = self.sanity_checker.validate_trade(agent_name, trade_decision.trade, asdict(wallet_state))
            diagnostics["trade_validation"] = {
                "approved": trade_result.approved,
                "rejection_reason": trade_result.rejection_reason,
                "warnings": trade_result.warnings,
            }
            if trade_result.approved:
                trade_execution = self.wallet_manager.execute_trade(agent_name, trade_decision.trade)
                diagnostics["trade_execution"] = self._trade_execution_summary(trade_execution)
                if trade_execution.success:
                    self._log_trade(agent_name, trade_decision.trade, trade_execution)
                    self.current_loop_trade_posts.append(
                        {
                            "agent_name": agent_name,
                            "side": trade_execution.side,
                            "quantity": trade_execution.quantity,
                            "symbol": trade_execution.symbol,
                            "usdc_value": trade_execution.usdc_value,
                        }
                    )
                    shared_context["recent_trades"].insert(0, self._trade_row(agent_name, trade_decision.trade, trade_execution))
                    shared_context["recent_trades"] = shared_context["recent_trades"][:10]
                    if trade_execution.adjustment_note:
                        self.telegram.send_medium(f"ℹ️ {agent_name} trade adjusted: {trade_execution.adjustment_note}")
                    self.telegram.send_low(
                        f"🔄 {agent_name}: {trade_execution.side} {trade_execution.quantity} {trade_execution.symbol} @ ${trade_execution.price_usdc:.4f} (${trade_execution.usdc_value:.2f})"
                    )
                else:
                    self.current_loop_errors.setdefault(agent_name, {})["trade_execution"] = trade_execution.error
                    if trade_execution.adjustment_note:
                        self.telegram.send_medium(f"ℹ️ {agent_name} trade adjusted: {trade_execution.adjustment_note}")
                    self.telegram.send_medium(f"⚠️ {agent_name} trade execution failed: {trade_execution.error}")
            else:
                self.telegram.send_medium(f"⚠️ {agent_name} trade rejected: {trade_result.rejection_reason}")
        else:
            diagnostics["trade_validation"] = {
                "approved": False,
                "rejection_reason": "No trade submitted",
                "warnings": [],
                "no_trade_explanation": trade_decision.no_trade_explanation if trade_decision else None,
            }

        trade_context = {
            "decision": trade_decision.trade if trade_decision else None,
            "validation": diagnostics.get("trade_validation"),
            "execution": diagnostics.get("trade_execution"),
        }
        comms_system_prompt = build_comms_system_prompt(agent_name, trigger_bundle)
        comms_user_prompt = build_comms_user_prompt(
            agent_name,
            wallet_state,
            agent_shared_context,
            memory,
            activity,
            rejections,
            trigger_bundle,
            trade_context=trade_context,
        )
        comms_decision, comms_raw_response = self._get_comms_decision(agent_name, comms_system_prompt, comms_user_prompt)
        diagnostics["comms_raw_response"] = self._truncate_text(comms_raw_response)
        diagnostics["parsed_comms_decision"] = {
            "chat": self._truncate_text(comms_decision.chat) if comms_decision else None,
            "social": self._truncate_text(comms_decision.social) if comms_decision and comms_decision.social else None,
        }
        comms_usage = self._llm_usage(agent_name)
        self.current_loop_token_usage[agent_name] = {
            "trade_decision": trade_usage,
            "communications": comms_usage,
        }

        chat_posted = False
        if comms_decision:
            chat_result = self.sanity_checker.validate_chat(
                agent_name,
                comms_decision.chat,
                {
                    "loop_number": self.loop_number,
                    "trigger_type": trigger_bundle.primary_trigger_type,
                    "recent_chat": shared_context.get("recent_chat", []),
                    "market_snapshot_symbols": diagnostics.get("market_snapshot_symbols", []),
                    "trade_context": trade_context,
                },
            )
            diagnostics["chat_validation"] = {
                "approved": chat_result.approved,
                "rejection_reason": chat_result.rejection_reason,
                "message": self._truncate_text(chat_result.message),
            }
            if chat_result.approved:
                self._write_chat(agent_name, chat_result.message, trigger_bundle)
                self.current_loop_chat_posts.append({"sender": agent_name, "message": chat_result.message})
                shared_context["recent_chat"].append({"sender": agent_name, "message": chat_result.message})
                shared_context["recent_chat"] = shared_context["recent_chat"][-20:]
                chat_posted = True

            if comms_decision.social:
                social_result = self.sanity_checker.validate_social(agent_name, comms_decision.social)
                diagnostics["social_validation"] = {
                    "approved": social_result.approved,
                    "rejection_reason": social_result.rejection_reason,
                    "post": self._truncate_text(social_result.post),
                }
                if social_result.approved:
                    post_result = self.x_client.post(agent_name, social_result.post)
                    publish_status = "pending" if post_result.get("status") == "disabled" else "posted"
                    self._log_social(agent_name, social_result.post, post_result.get("id"), status=publish_status)
                    self.telegram.send_low(f"📱 {agent_name}: {social_result.post[:50]}...")
                else:
                    self.telegram.send_medium(f"⚠️ {agent_name} post blocked: {social_result.rejection_reason}")
            else:
                diagnostics["social_validation"] = {"approved": False, "rejection_reason": "No social post submitted", "post": None}

        updated_wallet = self.wallet_manager.get_wallet_state(agent_name)
        diagnostics["post_wallet"] = self._wallet_summary(updated_wallet)
        self._write_standings(agent_name, updated_wallet)
        self._replace_positions(agent_name, updated_wallet)
        self.activity_tracker.update_activity(
            agent_name,
            asdict(trade_execution) if trade_execution and trade_execution.success else None,
            updated_wallet.total_equity_usdc,
            chat_posted=chat_posted,
        )
        diagnostics["activity_status"] = self._activity_summary(self.activity_tracker.get_status(agent_name))
        if trade_execution:
            diagnostics["trade_qualification"] = {
                "qualified": self.activity_tracker.trade_qualifies(asdict(trade_execution), updated_wallet.total_equity_usdc),
                "trade_usdc_value": trade_execution.usdc_value,
                "threshold_usdc": min(
                    self.activity_tracker.min_trade_value_usdc,
                    updated_wallet.total_equity_usdc * self.activity_tracker.min_trade_value_percent,
                ),
            }
        self.current_loop_diagnostics[agent_name] = diagnostics
        self.elimination_manager.record_equity(agent_name, updated_wallet.total_equity_usdc, updated_wallet.timestamp.isoformat())

    def _get_trade_decision(self, agent_name: str, system_prompt: str, user_prompt: str):
        raw_response = self._call_llm(agent_name, system_prompt, user_prompt)
        try:
            return parse_trade_response(raw_response), raw_response
        except AgentParseError:
            retry_prompt = user_prompt + "\nYour previous response was not valid JSON. Respond with ONLY a JSON object."
            try:
                retry_response = self._call_llm(agent_name, system_prompt, retry_prompt)
                return parse_trade_response(retry_response), retry_response
            except Exception:  # noqa: BLE001
                return None, raw_response

    def _get_comms_decision(self, agent_name: str, system_prompt: str, user_prompt: str):
        raw_response = self._call_llm(agent_name, system_prompt, user_prompt)
        try:
            return parse_comms_response(raw_response), raw_response
        except AgentParseError:
            retry_prompt = user_prompt + "\nYour previous response was not valid JSON. Respond with ONLY a JSON object."
            try:
                retry_response = self._call_llm(agent_name, system_prompt, retry_prompt)
                return parse_comms_response(retry_response), retry_response
            except Exception:  # noqa: BLE001
                self._write_fallback_chat(agent_name)
                return None, raw_response

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
        wallet_states = {agent_name: self.wallet_manager.get_wallet_state(agent_name) for agent_name in active_agents}
        market_snapshots = self.market_data_provider.build_snapshots(
            wallet_states,
            recent_trades,
            active_agents,
            supported_symbols=self.wallet_manager.supported_symbols(),
        )
        trigger_bundle = determine_chat_triggers(now, recent_trades, current_standings, previous_standings, active_agents)
        return {
            "loop_number": self.loop_number,
            "timestamp": now.isoformat().replace("+00:00", "Z"),
            "starting_capital_usdc": self.starting_capital_usdc,
            "leaderboard": leaderboard,
            "recent_chat": recent_chat,
            "recent_trades": recent_trades,
            "market_snapshots": market_snapshots,
            "wallet_states": wallet_states,
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
                "agent_diagnostics": self.current_loop_diagnostics,
            },
            "token_usage": self.current_loop_token_usage,
        }
        self.supabase.table("loop_log").update(payload).eq("loop_number", self.loop_number).execute()

    def _log_trade(self, agent_name: str, trade: dict, execution) -> None:
        reasoning = trade.get("reasoning")
        if execution.adjustment_note:
            reasoning = f"{reasoning}\n[execution_adjustment] {execution.adjustment_note}" if reasoning else f"[execution_adjustment] {execution.adjustment_note}"
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
                "reasoning": reasoning,
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

    def _write_loop_commentary_if_needed(self, processed_agents: list[str]) -> None:
        if self.current_loop_chat_posts:
            return

        message = self._build_loop_commentary(processed_agents)
        self.supabase.table("chat_logs").insert(
            {
                "sender": "arena",
                "message": message,
                "trigger_type": "system_update",
                "loop_number": self.loop_number,
                "metadata": {"source": "fallback_commentator"},
            }
        ).execute()
        self.current_loop_chat_posts.append({"sender": "arena", "message": message})

    def _build_loop_commentary(self, processed_agents: list[str]) -> str:
        equities: list[tuple[str, float]] = []
        for agent_name in processed_agents:
            diagnostics = self.current_loop_diagnostics.get(agent_name, {})
            post_wallet = diagnostics.get("post_wallet") or {}
            try:
                equities.append((agent_name, float(post_wallet.get("total_equity_usdc", 0))))
            except (TypeError, ValueError):
                continue

        rejection_summaries: list[str] = []
        for agent_name in processed_agents:
            diagnostics = self.current_loop_diagnostics.get(agent_name, {})
            chat_validation = diagnostics.get("chat_validation") or {}
            reason = chat_validation.get("rejection_reason")
            if reason:
                rejection_summaries.append(f"{agent_name} chat blocked ({reason.lower()})")
        if len(equities) >= 2:
            equities.sort(key=lambda item: item[1], reverse=True)
            leader_name, leader_equity = equities[0]
            trailer_name, trailer_equity = equities[-1]
        elif equities:
            leader_name, leader_equity = equities[0]
            trailer_name, trailer_equity = equities[0]
        else:
            leader_name, leader_equity = ("arena", 0.0)
            trailer_name, trailer_equity = ("arena", 0.0)

        gap = leader_equity - trailer_equity
        trade_summaries = [
            f"{row['agent_name']} {row['side']} {row['quantity']} {row['symbol']} (${row['usdc_value']:.2f})"
            for row in self.current_loop_trade_posts[:2]
        ]
        coverage_text = (
            "Feed coverage: " + "; ".join(rejection_summaries[:2]) + "."
            if rejection_summaries
            else "Feed coverage held, but the agents left the mic to Arena this loop."
        )
        mode = self.loop_number % 5

        if mode == 0:
            lead_line = (
                f"{leader_name} leads {trailer_name} ${leader_equity:.2f} to ${trailer_equity:.2f} (gap ${gap:.2f})."
                if leader_name != trailer_name
                else f"{leader_name} sits at ${leader_equity:.2f}."
            )
            trade_line = (
                "This loop's trades: " + "; ".join(trade_summaries) + "."
                if trade_summaries
                else "No trades executed this loop."
            )
            return f"Arena update: {lead_line} {trade_line} {coverage_text}"

        if mode == 1:
            if trade_summaries:
                trade_line = "Trade tape: " + "; ".join(trade_summaries) + "."
            else:
                trade_line = f"The tape stayed quiet while {leader_name} protected a ${gap:.2f} edge."
            return f"Arena tape: {trade_line} {coverage_text}"

        if mode == 2:
            if leader_name != trailer_name:
                tension_line = (
                    f"Endgame check: only ${gap:.2f} separates {leader_name} and {trailer_name}, "
                    f"with the board sitting at ${leader_equity:.2f} vs ${trailer_equity:.2f}."
                )
            else:
                tension_line = f"Endgame check: {leader_name} holds at ${leader_equity:.2f}."
            trade_line = "No one pulled the trigger this loop." if not trade_summaries else "Pressure release came through " + "; ".join(trade_summaries) + "."
            return f"{tension_line} {trade_line} {coverage_text}"

        if mode == 3:
            rivalry_line = (
                f"Rivalry desk: {leader_name} is up ${gap:.2f} on {trailer_name}."
                if leader_name != trailer_name
                else f"Rivalry desk: {leader_name} is shadowboxing at ${leader_equity:.2f}."
            )
            action_line = (
                "Latest move: " + "; ".join(trade_summaries) + "."
                if trade_summaries
                else "Latest move: all talk, no fills."
            )
            return f"{rivalry_line} {action_line} {coverage_text}"

        activity_line = (
            f"Standings pulse: {leader_name} remains in front at ${leader_equity:.2f}, with {trailer_name} at ${trailer_equity:.2f}."
            if leader_name != trailer_name
            else f"Standings pulse: {leader_name} remains at ${leader_equity:.2f}."
        )
        quiet_line = "No trades hit the book this round." if not trade_summaries else "Trades on the book: " + "; ".join(trade_summaries) + "."
        return f"{activity_line} {quiet_line} {coverage_text}"

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
        pnl_percent = ((wallet_state.total_equity_usdc - self.starting_capital_usdc) / self.starting_capital_usdc) * 100
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

    @staticmethod
    def _truncate_text(value: str | None, limit: int = 600) -> str | None:
        if value is None:
            return None
        text = str(value)
        return text if len(text) <= limit else text[:limit] + "...[truncated]"

    @staticmethod
    def _wallet_summary(wallet_state) -> dict[str, Any]:
        return {
            "cash_usdc": wallet_state.cash_usdc,
            "total_equity_usdc": wallet_state.total_equity_usdc,
            "positions": {
                symbol: {
                    "quantity": position.quantity,
                    "price_usdc": position.current_price_usdc,
                    "value_usdc": position.value_usdc,
                }
                for symbol, position in wallet_state.positions.items()
            },
            "timestamp": wallet_state.timestamp.isoformat(),
        }

    @staticmethod
    def _trade_execution_summary(trade_execution) -> dict[str, Any]:
        return {
            "success": trade_execution.success,
            "symbol": trade_execution.symbol,
            "side": trade_execution.side,
            "requested_quantity": trade_execution.requested_quantity,
            "executed_quantity": trade_execution.quantity,
            "price_usdc": trade_execution.price_usdc,
            "usdc_value": trade_execution.usdc_value,
            "fee_usdc": trade_execution.fee_usdc,
            "tx_hash": trade_execution.tx_hash,
            "error": trade_execution.error,
            "adjustment_note": trade_execution.adjustment_note,
        }

    @staticmethod
    def _activity_summary(activity_status) -> dict[str, Any]:
        return {
            "qualifying_trades": activity_status.qualifying_trades,
            "daily_chats_completed": activity_status.daily_chats_completed,
            "flag_status": activity_status.flag_status,
            "warning": activity_status.warning,
        }

    def _llm_usage(self, agent_name: str) -> dict[str, Any]:
        client = self.llm_clients.get(agent_name)
        if client is None:
            return {}
        return dict(getattr(client, "last_response_meta", {}) or {})

    def _trade_limits_for_agent(self, agent_name: str, wallet_state, shared_context: dict) -> dict[str, Any]:
        cap_percent = float(getattr(self.sanity_checker, "max_trade_percent", 0.29))
        raw_max_notional = min(wallet_state.cash_usdc, wallet_state.total_equity_usdc * cap_percent)
        max_notional = raw_max_notional * 0.985
        symbol_limits: list[dict[str, Any]] = []
        for snapshot in shared_context.get("market_snapshots", []):
            if snapshot.get("status") != "ok":
                continue
            price = snapshot.get("price_usdc")
            try:
                price_value = float(price)
            except (TypeError, ValueError):
                continue
            if price_value <= 0:
                continue
            symbol_limits.append(
                {
                    "symbol": snapshot.get("symbol"),
                    "price_usdc": price_value,
                    "max_buy_quantity": max_notional / price_value,
                    "max_buy_notional_usdc": max_notional,
                }
            )
        return {
            "agent_name": agent_name,
            "max_trade_percent": cap_percent,
            "raw_max_buy_notional_usdc": raw_max_notional,
            "max_buy_notional_usdc": max_notional,
            "cash_usdc": wallet_state.cash_usdc,
            "symbol_limits": symbol_limits,
        }


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
