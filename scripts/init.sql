CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS documents (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source      VARCHAR(255) NOT NULL,
    url         TEXT,
    category    VARCHAR(100),
    subcategory VARCHAR(100),
    title       TEXT,
    raw_content TEXT NOT NULL,
    clean_content TEXT,
    language    VARCHAR(10) DEFAULT 'fr',
    published_at DATE,
    collected_at TIMESTAMP DEFAULT NOW(),
    updated_at  TIMESTAMP,
    embedding   vector(384),
    metadata    JSONB,
    status      VARCHAR(20) DEFAULT 'active'
);

CREATE INDEX IF NOT EXISTS documents_embedding_idx
    ON documents USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

CREATE UNIQUE INDEX IF NOT EXISTS documents_url_idx ON documents (url);
CREATE INDEX IF NOT EXISTS documents_source_idx ON documents (source);
CREATE INDEX IF NOT EXISTS documents_category_idx ON documents (category);
CREATE INDEX IF NOT EXISTS documents_language_idx ON documents (language);

CREATE TABLE IF NOT EXISTS chunks (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id  UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index  INT  NOT NULL,
    content      TEXT NOT NULL,
    word_count   INT,
    embedding    vector(384),
    UNIQUE (document_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS chunks_embedding_idx
    ON chunks USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

CREATE INDEX IF NOT EXISTS chunks_document_id_idx ON chunks (document_id);

-- API keys table (hashed — plain-text key is never stored)
CREATE TABLE IF NOT EXISTS api_keys (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    key_hash    VARCHAR(64) NOT NULL UNIQUE,   -- SHA-256 hex digest
    owner_name  VARCHAR(255),
    owner_email VARCHAR(255),
    plan        VARCHAR(20) DEFAULT 'dev'      -- free | dev | institution
                CHECK (plan IN ('free', 'dev', 'institution')),
    is_active   BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMP DEFAULT NOW(),
    last_used   TIMESTAMP
);

CREATE INDEX IF NOT EXISTS api_keys_hash_idx    ON api_keys (key_hash);
CREATE INDEX IF NOT EXISTS api_keys_active_idx  ON api_keys (is_active);

-- Seed one document so stats/list/get-by-id tests pass in CI with an empty corpus
INSERT INTO documents (id, source, url, category, title, raw_content, clean_content, language, status)
VALUES (
    '00000000-0000-0000-0000-000000000001',
    'jo.gouv.tg',
    'https://jo.gouv.tg/test-loi-finances-2025',
    'legal',
    'Loi de finances 2025',
    'Le budget de l''État togolais pour 2025 s''élève à 2 400 milliards de FCFA.',
    'Le budget de l''État togolais pour 2025 s''élève à 2 400 milliards de FCFA.',
    'fr',
    'active'
) ON CONFLICT DO NOTHING;

INSERT INTO chunks (document_id, chunk_index, content, word_count)
VALUES (
    '00000000-0000-0000-0000-000000000001',
    0,
    'Le budget de l''État togolais pour 2025 s''élève à 2 400 milliards de FCFA.',
    13
) ON CONFLICT DO NOTHING;
