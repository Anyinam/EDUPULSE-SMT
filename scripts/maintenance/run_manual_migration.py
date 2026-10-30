#!/usr/bin/env python3
"""
Manual migration script to add submit_to columns to SQLite database.
WARNING: Use Alembic migrations in normal workflows.
"""

import os
import sqlite3

# Path to the dev SQLite database (keep aligned with alembic.ini)
DB_PATH = os.path.join(os.path.dirname(__file__), "edupulse.db")


def run_migration():
    """Add submit_to columns to lesson_notes and report_cards tables"""

    print("⚠️  WARNING: This script bypasses Alembic. Prefer Alembic migrations.")

    if not os.path.exists(DB_PATH):
        print(f"❌ Database not found at: {DB_PATH}")
        print("Please ensure the database exists first.")
        return False

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        print("🔄 Starting manual migration...")

        # Add submit_to to lesson_notes
        try:
            cursor.execute("""
                ALTER TABLE lesson_notes 
                ADD COLUMN submit_to VARCHAR(20) DEFAULT 'headmaster'
            """)
            print("✅ Added submit_to column to lesson_notes table")
        except sqlite3.OperationalError as e:
            if "duplicate column" in str(e).lower():
                print("ℹ️  submit_to column already exists in lesson_notes table")
            else:
                raise

        # Add submit_to to report_cards
        try:
            cursor.execute("""
                ALTER TABLE report_cards 
                ADD COLUMN submit_to VARCHAR(20) DEFAULT 'headmaster'
            """)
            print("✅ Added submit_to column to report_cards table")
        except sqlite3.OperationalError as e:
            if "duplicate column" in str(e).lower():
                print("ℹ️  submit_to column already exists in report_cards table")
            else:
                raise

        conn.commit()

        # Verify the columns
        print("\n📊 Verifying lesson_notes table schema:")
        cursor.execute("PRAGMA table_info(lesson_notes)")
        columns = cursor.fetchall()
        for col in columns:
            if col[1] == "submit_to":
                print(f"   ✓ submit_to: {col[2]} (default: {col[4]})")

        print("\n📊 Verifying report_cards table schema:")
        cursor.execute("PRAGMA table_info(report_cards)")
        columns = cursor.fetchall()
        for col in columns:
            if col[1] == "submit_to":
                print(f"   ✓ submit_to: {col[2]} (default: {col[4]})")

        conn.close()

        print("\n✅ Migration completed successfully!")
        return True

    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        return False


if __name__ == "__main__":
    success = run_migration()
    exit(0 if success else 1)
