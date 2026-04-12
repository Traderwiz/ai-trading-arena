from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone


@dataclass
class EliminationWatchState:
    agent_name: str
    consecutive_loops_below: int = 0
    first_triggered_at: str | None = None


class EliminationManager:
    def __init__(
        self,
        supabase_client,
        wallet_manager,
        llm_clients: dict | None = None,
        x_client=None,
        telegram=None,
        sanity_checker=None,
        config: dict | None = None,
        now_provider=None,
    ):
        elimination_config = (config or {}).get("elimination", config or {})
        self.supabase = supabase_client
        self.wallet_manager = wallet_manager
        self.llm_clients = llm_clients or {}
        self.x_client = x_client
        self.telegram = telegram
        self.sanity_checker = sanity_checker
        self.threshold_usdc = float(elimination_config.get("threshold_usdc", 10.0))
        self.consecutive_loops_required = int(elimination_config.get("consecutive_loops_required", 2))
        self.now_provider = now_provider or (lambda: datetime.now(timezone.utc))
        self.watch: dict[str, EliminationWatchState] = {}

    def load_watch(self, agent_names: list[str]) -> dict[str, EliminationWatchState]:
        for agent_name in agent_names:
            rows = self._fetch_rows(
                "standings",
                {"agent_name": agent_name},
                order=("loop_number", True),
                limit=self.consecutive_loops_required + 2,
            )
            consecutive = 0
            first_triggered_at = None
            for row in rows:
                equity = float(row.get("total_equity_usdc", 0))
                if equity <= self.threshold_usdc:
                    consecutive += 1
                    first_triggered_at = row.get("timestamp")
                else:
                    break
            self.watch[agent_name] = EliminationWatchState(agent_name, consecutive, first_triggered_at)
        return self.watch

    def record_equity(self, agent_name: str, total_equity_usdc: float, timestamp: str | None = None) -> EliminationWatchState:
        state = self.watch.get(agent_name) or EliminationWatchState(agent_name)
        if total_equity_usdc <= self.threshold_usdc:
            state.consecutive_loops_below += 1
            state.first_triggered_at = state.first_triggered_at or timestamp or self.now_provider().isoformat()
        else:
            state.consecutive_loops_below = 0
            state.first_triggered_at = None
        self.watch[agent_name] = state
        return state

    def should_eliminate(self, agent_name: str) -> bool:
        state = self.watch.get(agent_name) or EliminationWatchState(agent_name)
        return state.consecutive_loops_below >= self.consecutive_loops_required

    def get_ready_agents(self) -> list[str]:
        return [agent_name for agent_name in self.watch if self.should_eliminate(agent_name)]

    def trigger_elimination(self, agent_name: str, loop_number: int, elimination_type: str = "financial") -> dict:
        now = self.now_provider()
        pre_state = self.wallet_manager.get_wallet_state(agent_name)
        self.supabase.table("agents").update({"status": "eliminated", "eliminated_at": now.isoformat()}).eq("agent_name", agent_name).execute()

        liquidation_results = self.wallet_manager.liquidate_all(agent_name) if elimination_type == "financial" else []
        final_state = self.wallet_manager.get_wallet_state(agent_name)
        last_words = self._generate_last_words(agent_name, final_state.total_equity_usdc)
        final_post = self._generate_final_post(agent_name, final_state.total_equity_usdc)

        if last_words:
            self.supabase.table("chat_logs").insert(
                {
                    "sender": agent_name,
                    "message": last_words,
                    "trigger_type": "elimination_last_words",
                    "loop_number": loop_number,
                }
            ).execute()

        posted_social = None
        if final_post:
            if self.sanity_checker:
                social_result = self.sanity_checker.validate_social(agent_name, final_post)
                if social_result.approved:
                    posted_social = social_result.post
                else:
                    posted_social = None
            else:
                posted_social = final_post
            self.supabase.table("social_posts").insert(
                {
                    "agent_name": agent_name,
                    "platform": "x",
                    "content": final_post,
                    "status": "posted" if posted_social else "blocked",
                    "blocked_reason": None if posted_social else "Sanity checker rejected elimination post",
                    "loop_number": loop_number,
                }
            ).execute()
            if posted_social and self.x_client:
                self.x_client.post(agent_name, posted_social)

        active_after = self._fetch_rows("agents", {"status": "active"})
        finish_place = len(active_after) + 1
        fatal_trade = self._fetch_rows("trades", {"agent_name": agent_name}, order=("timestamp", True), limit=1)
        elimination_payload = {
            "agent_name": agent_name,
            "final_equity_usdc": final_state.total_equity_usdc,
            "elimination_type": elimination_type,
            "fatal_trade_id": fatal_trade[0]["id"] if fatal_trade else None,
            "last_words": last_words,
            "final_x_post": posted_social,
            "final_positions": {symbol: asdict(position) for symbol, position in final_state.positions.items()},
            "loops_below_threshold": self.watch.get(agent_name, EliminationWatchState(agent_name)).consecutive_loops_below,
            "finish_place": finish_place,
        }
        self.supabase.table("eliminations").insert(elimination_payload).execute()

        if self.telegram:
            self.telegram.send_critical(f"💀 ELIMINATION: {agent_name} at ${final_state.total_equity_usdc:.2f}")

        return {
            "agent_name": agent_name,
            "pre_state": pre_state,
            "final_state": final_state,
            "liquidations": liquidation_results,
            "last_words": last_words,
            "final_post": posted_social,
            "finish_place": finish_place,
        }

    def _generate_last_words(self, agent_name: str, final_equity: float) -> str:
        client = self.llm_clients.get(agent_name)
        if not client:
            return f"{agent_name} experienced elimination at ${final_equity:.2f}."
        prompt = (
            f"You have been ELIMINATED from the AI Trading Arena. Your final equity: ${final_equity:.2f}. "
            "This is your last message ever in this competition. Give your final words to the group chat. Make them memorable."
        )
        try:
            return client.call("Respond in plain text only.", prompt)
        except Exception:  # noqa: BLE001
            return f"{agent_name} has no final words beyond the chart."

    def _generate_final_post(self, agent_name: str, final_equity: float) -> str:
        client = self.llm_clients.get(agent_name)
        if not client:
            return f"{agent_name} exits the Arena at ${final_equity:.2f}."
        prompt = f"Write your final X post as an eliminated contestant. Final equity: ${final_equity:.2f}. 280 chars max."
        try:
            return client.call("Respond in plain text only.", prompt)
        except Exception:  # noqa: BLE001
            return f"{agent_name} exits the Arena at ${final_equity:.2f}."

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
