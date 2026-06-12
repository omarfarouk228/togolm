-- Migration: add key_prefix column to api_keys
-- Run once: psql $DATABASE_URL -f scripts/add_key_prefix.sql

ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS key_prefix VARCHAR(20);
ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS use_case TEXT;
