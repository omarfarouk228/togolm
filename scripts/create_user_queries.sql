CREATE TABLE IF NOT EXISTS user_queries (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    question      TEXT NOT NULL,
    language      VARCHAR(10) DEFAULT 'fr',
    category      VARCHAR(100),
    is_off_topic  BOOLEAN DEFAULT FALSE,
    chunks_found  INTEGER DEFAULT 0,
    latency_ms    INTEGER,
    api_key_prefix VARCHAR(20),
    created_at    TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS user_queries_created_at_idx ON user_queries (created_at);
CREATE INDEX IF NOT EXISTS user_queries_api_key_prefix_idx ON user_queries (api_key_prefix);
