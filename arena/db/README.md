# Arena Database

This directory contains the initial Supabase schema for AI Trading Arena Components 1 and 2.

## Target

- Provider: Supabase
- Region: `us-east-1` (US East / Virginia)
- Migration: [001_initial_schema.sql](/C:/Users/gaber/projects/ai_trading_arena/arena/db/migrations/001_initial_schema.sql)
- Seed data: [agents.sql](/C:/Users/gaber/projects/ai_trading_arena/arena/db/seeds/agents.sql)

## What the migration creates

- Core arena tables from the spec: `agents`, `standings`, `positions`, `trades`, `chat_logs`, `social_posts`, `eliminations`, `activity_tracking`, `loop_log`, `memory_summaries`
- `validation_log` for Component 2 logging
- Dashboard views: `current_standings`, `leaderboard`
- Indexes from the spec
- RLS enablement and policies for `arena_writer` and `arena_reader`
- Role creation and grants for tables, views, and sequences

## Supabase setup

1. Create a new Supabase project in `us-east-1`.
2. Capture the project connection details from Supabase:
   - Direct Postgres connection string for migrations and seed scripts
   - Service-role credentials for the orchestration bot
   - Read-only credentials mapped to the `arena_reader` role for the dashboard
3. Apply the migration against a fresh database.
4. Run the seed script.

Example `psql` flow:

```bash
psql "$SUPABASE_DB_URL" -f arena/db/migrations/001_initial_schema.sql
psql "$SUPABASE_DB_URL" -f arena/db/seeds/agents.sql
```

If you use the Supabase CLI instead:

```bash
supabase db reset
psql "$SUPABASE_DB_URL" -f arena/db/seeds/agents.sql
```

## Roles

The migration creates two database roles:

- `arena_writer`: full read/write access to all arena tables
- `arena_reader`: read-only access to all arena tables and views

RLS is enabled on every table. `arena_reader` can only `SELECT`. `arena_writer` can `SELECT`, `INSERT`, `UPDATE`, and `DELETE`.

## Verification checklist

1. Migration runs cleanly against an empty database.
2. Seed script inserts four agents.
3. Sample inserts across `standings` produce expected output from `current_standings` and `leaderboard`.
4. `SET ROLE arena_reader;` allows reads and rejects writes.

Minimal smoke test:

```sql
SELECT agent_name, display_name, status FROM agents ORDER BY agent_name;

INSERT INTO standings (agent_name, total_equity_usdc, cash_usdc, invested_usdc, pnl_percent, num_positions, loop_number)
VALUES
    ('grok', 100.0000, 60.0000, 40.0000, 0.0000, 1, 1),
    ('deepseek', 102.0000, 52.0000, 50.0000, 2.0000, 2, 1);

SELECT * FROM current_standings ORDER BY agent_name;
SELECT * FROM leaderboard ORDER BY rank, agent_name;
```

To verify RLS:

```sql
SET ROLE arena_reader;
SELECT * FROM agents;
INSERT INTO agents (agent_name, display_name, provider, execution_type) VALUES ('test', 'Test', 'test', 'api');
```

The final `INSERT` should fail.
