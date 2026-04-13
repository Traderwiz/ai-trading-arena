BEGIN;

CREATE OR REPLACE VIEW current_standings AS
SELECT DISTINCT ON (agent_name)
    id,
    agent_name,
    total_equity_usdc,
    cash_usdc,
    invested_usdc,
    pnl_percent,
    num_positions,
    timestamp,
    loop_number
FROM standings
ORDER BY agent_name, loop_number DESC, timestamp DESC, id DESC;

CREATE OR REPLACE VIEW leaderboard AS
SELECT
    cs.agent_name,
    a.display_name,
    a.status,
    cs.total_equity_usdc,
    cs.pnl_percent,
    cs.num_positions,
    cs.timestamp AS last_updated,
    RANK() OVER (ORDER BY cs.pnl_percent DESC) AS rank
FROM current_standings cs
JOIN agents a ON cs.agent_name = a.agent_name
WHERE a.status IN ('active', 'eliminated')
ORDER BY rank;

COMMIT;
