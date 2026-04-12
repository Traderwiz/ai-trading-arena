INSERT INTO agents (agent_name, display_name, provider, execution_type, status)
VALUES
    ('grok', 'Grok', 'xai', 'api', 'pending'),
    ('deepseek', 'DeepSeek', 'deepseek', 'api', 'pending'),
    ('qwen', 'Qwen', 'alibaba', 'local', 'pending'),
    ('llama', 'Llama', 'meta', 'local', 'pending')
ON CONFLICT (agent_name) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    provider = EXCLUDED.provider,
    execution_type = EXCLUDED.execution_type,
    status = EXCLUDED.status;
