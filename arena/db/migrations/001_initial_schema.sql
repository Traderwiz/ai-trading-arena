BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'arena_writer') THEN
        CREATE ROLE arena_writer NOLOGIN;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'arena_reader') THEN
        CREATE ROLE arena_reader NOLOGIN;
    END IF;
END
$$;

CREATE TABLE IF NOT EXISTS agents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_name TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    provider TEXT NOT NULL,
    execution_type TEXT NOT NULL CHECK (execution_type IN ('api', 'local')),
    wallet_address TEXT,
    x_handle TEXT,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'active', 'eliminated', 'inactive')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    eliminated_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS standings (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    agent_name TEXT NOT NULL REFERENCES agents(agent_name),
    total_equity_usdc NUMERIC(12,4) NOT NULL,
    cash_usdc NUMERIC(12,4) NOT NULL,
    invested_usdc NUMERIC(12,4) NOT NULL,
    pnl_percent NUMERIC(8,4) NOT NULL,
    num_positions INTEGER NOT NULL DEFAULT 0,
    loop_number INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_standings_agent_time ON standings(agent_name, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_standings_loop ON standings(loop_number);

CREATE TABLE IF NOT EXISTS positions (
    id BIGSERIAL PRIMARY KEY,
    agent_name TEXT NOT NULL REFERENCES agents(agent_name),
    symbol TEXT NOT NULL,
    quantity NUMERIC(18,8) NOT NULL,
    avg_entry_price_usdc NUMERIC(18,8),
    current_price_usdc NUMERIC(18,8),
    current_value_usdc NUMERIC(12,4),
    unrealized_pnl_usdc NUMERIC(12,4),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(agent_name, symbol)
);

CREATE TABLE IF NOT EXISTS trades (
    id BIGSERIAL PRIMARY KEY,
    agent_name TEXT NOT NULL REFERENCES agents(agent_name),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    symbol TEXT NOT NULL,
    side TEXT NOT NULL CHECK (side IN ('buy', 'sell')),
    quantity NUMERIC(18,8) NOT NULL,
    price_usdc NUMERIC(18,8) NOT NULL,
    usdc_value NUMERIC(12,4) NOT NULL,
    fee_usdc NUMERIC(10,6) DEFAULT 0,
    tx_hash TEXT,
    loop_number INTEGER NOT NULL,
    pre_trade_equity_usdc NUMERIC(12,4),
    post_trade_equity_usdc NUMERIC(12,4),
    reasoning TEXT,
    confidence INTEGER CHECK (confidence BETWEEN 1 AND 10)
);

CREATE INDEX IF NOT EXISTS idx_trades_agent_time ON trades(agent_name, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol);

CREATE TABLE IF NOT EXISTS chat_logs (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sender TEXT NOT NULL,
    message TEXT NOT NULL,
    trigger_type TEXT,
    loop_number INTEGER,
    in_reply_to BIGINT REFERENCES chat_logs(id),
    metadata JSONB
);

CREATE INDEX IF NOT EXISTS idx_chat_time ON chat_logs(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_chat_sender ON chat_logs(sender);

CREATE TABLE IF NOT EXISTS social_posts (
    id BIGSERIAL PRIMARY KEY,
    agent_name TEXT NOT NULL,
    platform TEXT NOT NULL DEFAULT 'x',
    content TEXT NOT NULL,
    posted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    x_post_id TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    blocked_reason TEXT,
    loop_number INTEGER
);

CREATE INDEX IF NOT EXISTS idx_social_agent ON social_posts(agent_name, posted_at DESC);

CREATE TABLE IF NOT EXISTS eliminations (
    id BIGSERIAL PRIMARY KEY,
    agent_name TEXT NOT NULL REFERENCES agents(agent_name) UNIQUE,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    final_equity_usdc NUMERIC(12,4) NOT NULL,
    elimination_type TEXT NOT NULL,
    fatal_trade_id BIGINT REFERENCES trades(id),
    last_words TEXT,
    final_x_post TEXT,
    final_positions JSONB,
    loops_below_threshold INTEGER,
    finish_place INTEGER
);

CREATE TABLE IF NOT EXISTS activity_tracking (
    id BIGSERIAL PRIMARY KEY,
    agent_name TEXT NOT NULL REFERENCES agents(agent_name),
    week_start DATE NOT NULL,
    qualifying_trades INTEGER NOT NULL DEFAULT 0,
    daily_chats_completed INTEGER NOT NULL DEFAULT 0,
    flag_status TEXT DEFAULT 'clear',
    flag_issued_at TIMESTAMPTZ,
    UNIQUE(agent_name, week_start)
);

CREATE TABLE IF NOT EXISTS loop_log (
    id BIGSERIAL PRIMARY KEY,
    loop_number INTEGER NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    agents_processed TEXT[],
    errors JSONB,
    token_usage JSONB
);

CREATE INDEX IF NOT EXISTS idx_loop_number ON loop_log(loop_number);

CREATE TABLE IF NOT EXISTS memory_summaries (
    id BIGSERIAL PRIMARY KEY,
    agent_name TEXT NOT NULL REFERENCES agents(agent_name),
    summary_type TEXT NOT NULL CHECK (summary_type IN ('daily', 'weekly')),
    period_start TIMESTAMPTZ NOT NULL,
    period_end TIMESTAMPTZ NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_memory_agent_type ON memory_summaries(agent_name, summary_type, period_end DESC);

CREATE TABLE IF NOT EXISTS validation_log (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    agent_name TEXT NOT NULL,
    validation_type TEXT NOT NULL CHECK (validation_type IN ('trade', 'chat', 'social')),
    approved BOOLEAN NOT NULL,
    input_data JSONB NOT NULL,
    rejection_reason TEXT,
    warnings TEXT[]
);

CREATE OR REPLACE VIEW current_standings AS
SELECT DISTINCT ON (agent_name)
    agent_name,
    total_equity_usdc,
    cash_usdc,
    invested_usdc,
    pnl_percent,
    num_positions,
    timestamp,
    loop_number
FROM standings
ORDER BY agent_name, timestamp DESC;

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

ALTER TABLE agents ENABLE ROW LEVEL SECURITY;
ALTER TABLE standings ENABLE ROW LEVEL SECURITY;
ALTER TABLE positions ENABLE ROW LEVEL SECURITY;
ALTER TABLE trades ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE social_posts ENABLE ROW LEVEL SECURITY;
ALTER TABLE eliminations ENABLE ROW LEVEL SECURITY;
ALTER TABLE activity_tracking ENABLE ROW LEVEL SECURITY;
ALTER TABLE loop_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE memory_summaries ENABLE ROW LEVEL SECURITY;
ALTER TABLE validation_log ENABLE ROW LEVEL SECURITY;

CREATE POLICY writer_all_agents ON agents FOR ALL TO arena_writer USING (true) WITH CHECK (true);
CREATE POLICY writer_all_standings ON standings FOR ALL TO arena_writer USING (true) WITH CHECK (true);
CREATE POLICY writer_all_positions ON positions FOR ALL TO arena_writer USING (true) WITH CHECK (true);
CREATE POLICY writer_all_trades ON trades FOR ALL TO arena_writer USING (true) WITH CHECK (true);
CREATE POLICY writer_all_chat_logs ON chat_logs FOR ALL TO arena_writer USING (true) WITH CHECK (true);
CREATE POLICY writer_all_social_posts ON social_posts FOR ALL TO arena_writer USING (true) WITH CHECK (true);
CREATE POLICY writer_all_eliminations ON eliminations FOR ALL TO arena_writer USING (true) WITH CHECK (true);
CREATE POLICY writer_all_activity_tracking ON activity_tracking FOR ALL TO arena_writer USING (true) WITH CHECK (true);
CREATE POLICY writer_all_loop_log ON loop_log FOR ALL TO arena_writer USING (true) WITH CHECK (true);
CREATE POLICY writer_all_memory_summaries ON memory_summaries FOR ALL TO arena_writer USING (true) WITH CHECK (true);
CREATE POLICY writer_all_validation_log ON validation_log FOR ALL TO arena_writer USING (true) WITH CHECK (true);

CREATE POLICY reader_select_agents ON agents FOR SELECT TO arena_reader USING (true);
CREATE POLICY reader_select_standings ON standings FOR SELECT TO arena_reader USING (true);
CREATE POLICY reader_select_positions ON positions FOR SELECT TO arena_reader USING (true);
CREATE POLICY reader_select_trades ON trades FOR SELECT TO arena_reader USING (true);
CREATE POLICY reader_select_chat_logs ON chat_logs FOR SELECT TO arena_reader USING (true);
CREATE POLICY reader_select_social_posts ON social_posts FOR SELECT TO arena_reader USING (true);
CREATE POLICY reader_select_eliminations ON eliminations FOR SELECT TO arena_reader USING (true);
CREATE POLICY reader_select_activity_tracking ON activity_tracking FOR SELECT TO arena_reader USING (true);
CREATE POLICY reader_select_loop_log ON loop_log FOR SELECT TO arena_reader USING (true);
CREATE POLICY reader_select_memory_summaries ON memory_summaries FOR SELECT TO arena_reader USING (true);
CREATE POLICY reader_select_validation_log ON validation_log FOR SELECT TO arena_reader USING (true);

GRANT USAGE ON SCHEMA public TO arena_reader, arena_writer;
GRANT SELECT ON TABLE agents, standings, positions, trades, chat_logs, social_posts, eliminations, activity_tracking, loop_log, memory_summaries, validation_log TO arena_reader;
GRANT SELECT ON TABLE current_standings, leaderboard TO arena_reader;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE agents, standings, positions, trades, chat_logs, social_posts, eliminations, activity_tracking, loop_log, memory_summaries, validation_log TO arena_writer;
GRANT SELECT ON TABLE current_standings, leaderboard TO arena_writer;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO arena_reader, arena_writer;

COMMIT;
