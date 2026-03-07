#!/usr/bin/env python
"""Add submit_to column to lesson_notes table"""

import sqlite3

db_path = "/home/anyinam/Documents/EduPulse/backend/instance/edupulse.db"

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    print("Adding submit_to column to lesson_notes table...")
    cursor.execute("""
        ALTER TABLE lesson_notes 
        ADD COLUMN submit_to VARCHAR(20) DEFAULT 'headmaster'
    """)
    conn.commit()
    print("✓ Column added successfully!")
    
    # Verify
    cursor.execute("PRAGMA table_info(lesson_notes)")
    columns = cursor.fetchall()
    submit_to_found = any(col[1] == 'submit_to' for col in columns)
    
    if submit_to_found:
        print("✓ Verification passed: submit_to column exists")
    else:
        print("✗ Verification failed: submit_to column not found")
        
except sqlite3.OperationalError as e:
    if "duplicate column name" in str(e):
        print("✓ Column already exists")
    else:
        print(f"✗ Error: {e}")
except Exception as e:
    print(f"✗ Error: {e}")
finally:
    conn.close()
