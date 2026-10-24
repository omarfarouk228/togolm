-- Test-only corpus row, loaded by CI after `alembic upgrade head`.
-- It used to be inserted by migration 001, which put this made-up figure into
-- the production corpus too (removed by migration 007). Never load it in prod.
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
) ON CONFLICT DO NOTHING;

INSERT INTO chunks (document_id, chunk_index, content, word_count)
VALUES (
    '00000000-0000-0000-0000-000000000001',
    0,
    'Le budget de l''État togolais pour 2025 s''élève à 2 400 milliards de FCFA.',
    13
) ON CONFLICT DO NOTHING;
