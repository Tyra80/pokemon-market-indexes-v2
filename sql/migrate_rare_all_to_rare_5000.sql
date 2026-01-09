-- ============================================================
-- Migration: RARE_ALL → RARE_5000
-- ============================================================
-- This script removes all RARE_ALL data from the database.
-- RARE_5000 will be populated by the next rebalancing run.
--
-- Run this in Supabase SQL Editor after deploying the code changes.
-- ============================================================

-- Step 1: Delete RARE_ALL from index_values_daily
DELETE FROM index_values_daily WHERE index_code = 'RARE_ALL';

-- Step 2: Delete RARE_ALL from constituents_monthly
DELETE FROM constituents_monthly WHERE index_code = 'RARE_ALL';

-- Verify deletion
SELECT 'index_values_daily' as table_name, COUNT(*) as rare_all_count
FROM index_values_daily WHERE index_code = 'RARE_ALL'
UNION ALL
SELECT 'constituents_monthly' as table_name, COUNT(*) as rare_all_count
FROM constituents_monthly WHERE index_code = 'RARE_ALL';

-- Show current index codes in the database
SELECT DISTINCT index_code, COUNT(*) as records
FROM index_values_daily
GROUP BY index_code
ORDER BY index_code;
