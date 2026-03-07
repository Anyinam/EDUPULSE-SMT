-- Manual Database Migration Script for SQLite
-- Run this if alembic migrations fail
-- This adds the submit_to fields to lesson_notes and report_cards tables

-- SQLite doesn't support ADD COLUMN IF NOT EXISTS in older versions
-- So we use a safer approach with error handling

-- Add submit_to column to lesson_notes table
-- Run each ALTER TABLE separately, ignore errors if column exists
ALTER TABLE lesson_notes ADD COLUMN submit_to VARCHAR(20) DEFAULT 'headmaster';

-- Add submit_to column to report_cards table
ALTER TABLE report_cards ADD COLUMN submit_to VARCHAR(20) DEFAULT 'headmaster';

-- Verify the columns were added
PRAGMA table_info(lesson_notes);
PRAGMA table_info(report_cards);
