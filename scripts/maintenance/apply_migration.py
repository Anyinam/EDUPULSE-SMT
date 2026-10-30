#!/usr/bin/env python
"""
Direct migration script that applies the lesson notes expansion without Alembic connection issues
"""

import os
import sqlite3

# Create database directory if needed
db_dir = "/home/anyinam/Documents/EduPulse/backend/instance"
os.makedirs(db_dir, exist_ok=True)

db_path = os.path.join(db_dir, "edupulse.db")

# Create/connect to database
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Create lesson_notes table if it doesn't exist (fallback)
cursor.execute("""
    CREATE TABLE IF NOT EXISTS lesson_notes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        staff_id INTEGER,
        subject VARCHAR(100),
        content TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
""")

# Add all required columns to lesson_notes
# Complete list of all columns that should exist
all_columns = [
    ("school_id", "VARCHAR(20)"),
    ("teacher_id", "INTEGER"),
    ("week_number", "INTEGER"),
    ("class_name", "VARCHAR(50)"),
    ("indicator_code", "VARCHAR(50)"),
    ("content_standard_code", "VARCHAR(50)"),
    ("performance_indicator", "TEXT"),
    ("core_competencies", "TEXT"),
    ("key_words", "TEXT"),
    ("teaching_learning_resources", "TEXT"),
    ("references", "TEXT"),
    ("ai_score", "INTEGER"),
    ("ai_feedback", "TEXT"),
    ("status", "VARCHAR(20)"),
    ("submitted_at", "DATETIME"),
]

# Get existing columns
cursor.execute("PRAGMA table_info(lesson_notes)")
existing_columns = {row[1] for row in cursor.fetchall()}

for col_name, col_type in all_columns:
    if col_name not in existing_columns:
        try:
            cursor.execute(f"ALTER TABLE lesson_notes ADD COLUMN {col_name} {col_type}")
            print(f"✓ Added column {col_name}")
        except Exception as e:
            print(f"✗ Failed to add column {col_name}: {e}")
    else:
        print(f"✓ Column {col_name} already exists")

# Create daily_lesson_phases table
cursor.execute("""
    CREATE TABLE IF NOT EXISTS daily_lesson_phases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        lesson_note_id INTEGER NOT NULL,
        day VARCHAR(20),
        phase_1_starter TEXT,
        phase_2_main TEXT,
        phase_3_plenary TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(lesson_note_id) REFERENCES lesson_notes(id)
    )
""")
print("✓ Created table daily_lesson_phases")

# Create index on lesson_note_id
cursor.execute(
    "CREATE INDEX IF NOT EXISTS idx_daily_lesson_phases_lesson_note_id ON daily_lesson_phases(lesson_note_id)"
)
print("✓ Created index on lesson_note_id")

# Commit changes
conn.commit()

# Verify tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = [row[0] for row in cursor.fetchall()]
print(f"\n✓ Database tables: {tables}")

# Verify columns in lesson_notes
cursor.execute("PRAGMA table_info(lesson_notes)")
columns = [row[1] for row in cursor.fetchall()]
print(f"✓ lesson_notes columns: {columns}")

# Verify columns in daily_lesson_phases
cursor.execute("PRAGMA table_info(daily_lesson_phases)")
columns = [row[1] for row in cursor.fetchall()]
print(f"✓ daily_lesson_phases columns: {columns}")

conn.close()
print("\n✅ Migration completed successfully!")
