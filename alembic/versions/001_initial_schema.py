"""Initial schema: documents, chunks, api_keys, user_queries

Revision ID: 001
Revises:
Create Date: 2025-01-01 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    op.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            source      VARCHAR(255) NOT NULL,
            url         TEXT,
            category    VARCHAR(100),
            subcategory VARCHAR(100),
            title       TEXT,
            raw_content TEXT NOT NULL,
            clean_content TEXT,
            word_count  INTEGER,
            language    VARCHAR(10) DEFAULT 'fr',
            published_at DATE,
            collected_at TIMESTAMP DEFAULT NOW(),
            updated_at  TIMESTAMP,
            embedding   vector(384),
            metadata    JSONB,
            status      VARCHAR(20) DEFAULT 'active',
            fts_vector  tsvector GENERATED ALWAYS AS (
                to_tsvector('french', coalesce(clean_content, '') || ' ' || coalesce(title, ''))
            ) STORED
        )
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS documents_embedding_idx
            ON documents USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100)
    """)
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS documents_url_idx ON documents (url)")
    op.execute("CREATE INDEX IF NOT EXISTS documents_source_idx ON documents (source)")
    op.execute("CREATE INDEX IF NOT EXISTS documents_category_idx ON documents (category)")
    op.execute("CREATE INDEX IF NOT EXISTS documents_language_idx ON documents (language)")
    op.execute("CREATE INDEX IF NOT EXISTS documents_fts_idx ON documents USING gin (fts_vector)")
    op.execute("""
        CREATE INDEX IF NOT EXISTS documents_status_collected_at_idx
            ON documents (status, collected_at DESC)
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS chunks (
            id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            document_id  UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
            chunk_index  INT  NOT NULL,
            content      TEXT NOT NULL,
            word_count   INT,
            embedding    vector(384),
            UNIQUE (document_id, chunk_index)
        )
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS chunks_embedding_idx
            ON chunks USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100)
    """)
    op.execute("CREATE INDEX IF NOT EXISTS chunks_document_id_idx ON chunks (document_id)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS api_keys (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            key_hash    VARCHAR(64) NOT NULL UNIQUE,
            key_prefix  VARCHAR(20),
            owner_name  VARCHAR(255),
            owner_email VARCHAR(255),
            use_case    TEXT,
            plan        VARCHAR(20) DEFAULT 'free'
                        CHECK (plan IN ('free', 'dev', 'institution')),
            is_active   BOOLEAN DEFAULT TRUE,
            created_at  TIMESTAMP DEFAULT NOW(),
            last_used   TIMESTAMP
        )
    """)

    op.execute("CREATE INDEX IF NOT EXISTS api_keys_hash_idx ON api_keys (key_hash)")
    op.execute("CREATE INDEX IF NOT EXISTS api_keys_active_idx ON api_keys (is_active)")

    op.execute("""
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
        )
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS user_queries_created_at_idx ON user_queries (created_at)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS user_queries_api_key_prefix_idx
            ON user_queries (api_key_prefix)
    """)

    # Seed document for CI tests
    op.execute("""
        INSERT INTO documents
            (id, source, url, category, title,
             raw_content, clean_content, word_count, language, status)
        VALUES (
            '00000000-0000-0000-0000-000000000001',
            'jo.gouv.tg',
            'https://jo.gouv.tg/test-loi-finances-2025',
            'legal',
            'Loi de finances 2025',
            'Le budget de l''État togolais pour 2025 s''élève à 2 400 milliards de FCFA.',
            'Le budget de l''État togolais pour 2025 s''élève à 2 400 milliards de FCFA.',
            13,
            'fr',
            'active'
        ) ON CONFLICT DO NOTHING
    """)

    op.execute("""
        INSERT INTO chunks (document_id, chunk_index, content, word_count)
        VALUES (
            '00000000-0000-0000-0000-000000000001',
            0,
            'Le budget de l''État togolais pour 2025 s''élève à 2 400 milliards de FCFA.',
            13
        ) ON CONFLICT DO NOTHING
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS user_queries CASCADE")
    op.execute("DROP TABLE IF EXISTS api_keys CASCADE")
    op.execute("DROP TABLE IF EXISTS chunks CASCADE")
    op.execute("DROP TABLE IF EXISTS documents CASCADE")
