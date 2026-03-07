#!/usr/bin/env python
"""Add submit_to column to PostgreSQL lesson_notes table"""

import os
import psycopg2
from psycopg2 import sql

# Database configuration
DB_HOST = os.getenv("DATABASE_HOST", "localhost")
DB_PORT = os.getenv("DATABASE_PORT", "5432")
DB_NAME = os.getenv("POSTGRES_DB", "edupulse_db")
DB_USER = os.getenv("POSTGRES_USER", "edupulse_user")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "try123")

try:
    # Connect to PostgreSQL
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    conn.autocommit = True
    cursor = conn.cursor()
    
    print("Connected to PostgreSQL database")
    print(f"Database: {DB_NAME} at {DB_HOST}:{DB_PORT}")
    
    # Check if column exists
    cursor.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'lesson_notes' 
        AND column_name = 'submit_to'
    """)
    
    if cursor.fetchone():
        print("✓ Column 'submit_to' already exists in lesson_notes table")
    else:
        print("Adding 'submit_to' column to lesson_notes table...")
        cursor.execute("""
            ALTER TABLE lesson_notes 
            ADD COLUMN submit_to VARCHAR(20) DEFAULT 'headmaster'
        """)
        print("✓ Column added successfully!")
    
    # Verify
    cursor.execute("""
        SELECT column_name, data_type, column_default
        FROM information_schema.columns 
        WHERE table_name = 'lesson_notes' 
        AND column_name = 'submit_to'
    """)
    
    result = cursor.fetchone()
    if result:
        print(f"✓ Verification passed: {result[0]} ({result[1]}) with default: {result[2]}")
    else:
        print("✗ Verification failed: submit_to column not found")
    
    cursor.close()
    conn.close()
    print("\n✅ Database update complete!")
    
except psycopg2.OperationalError as e:
    print(f"✗ Connection error: {e}")
    print("\nTIP: Make sure PostgreSQL is running and credentials are correct")
except Exception as e:
    print(f"✗ Error: {e}")
