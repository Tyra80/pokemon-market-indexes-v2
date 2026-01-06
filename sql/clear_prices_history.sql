-- ============================================================
-- Clear card_prices_daily table
-- ============================================================
-- WARNING: This will DELETE ALL price history data!
-- Run this in Supabase SQL Editor before re-running backfill_history_v2.py
-- ============================================================

-- Option 1: TRUNCATE (fastest, resets auto-increment)
TRUNCATE TABLE card_prices_daily;

-- Option 2: DELETE (slower but works with foreign keys)
-- DELETE FROM card_prices_daily;

-- Verify the table is empty
SELECT COUNT(*) as remaining_rows FROM card_prices_daily;
