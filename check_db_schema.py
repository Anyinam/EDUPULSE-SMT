#!/usr/bin/env python
"""Check database schema for lesson_notes table"""

import sqlite3

db_path = "/home/anyinam/Documents/EduPulse/backend/instance/edupulse.db"

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Check alembic version
print("=== Alembic Version ===")
try:
    cursor.execute("SELECT * FROM alembic_version")
    version = cursor.fetchone()
    print(f"Current version: {version[0] if version else 'None'}")
except Exception as e:
    print(f"Error: {e}")

print("\n=== Lesson Notes Table Structure ===")
cursor.execute("PRAGMA table_info(lesson_notes)")
columns = cursor.fetchall()
for col in columns:
    print(f"{col[1]}: {col[2]}")

conn.close()
