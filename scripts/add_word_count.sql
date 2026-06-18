-- Add word_count column to documents for fast listing (avoids string_to_array on clean_content)
ALTER TABLE documents ADD COLUMN IF NOT EXISTS word_count INTEGER;

-- Backfill from sum of chunk word_counts (already computed at ingest time)
UPDATE documents d
SET word_count = (
    SELECT COALESCE(SUM(c.word_count), 0)
    FROM chunks c
    WHERE c.document_id = d.id
)
WHERE d.word_count IS NULL;

-- Composite index for the default document listing sort (status filter + ORDER BY collected_at DESC)
CREATE INDEX IF NOT EXISTS documents_status_collected_at_idx
    ON documents (status, collected_at DESC);
