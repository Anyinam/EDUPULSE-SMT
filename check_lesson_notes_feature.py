#!/usr/bin/env python
"""Check if lesson_notes feature is enabled for the school"""

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
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    print("=== Checking School Subscription Features ===\n")
    
    # Get school info
    cursor.execute("SELECT id, name, subscription_plan FROM schools LIMIT 1")
    school = cursor.fetchone()
    
    if school:
        school_id, school_name, plan = school
        print(f"School: {school_name} (ID: {school_id})")
        print(f"Subscription Plan: {plan}")
        
        # Check subscription features table if it exists
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_name = 'subscription_features'
        """)
        
        if cursor.fetchone():
            cursor.execute("""
                SELECT feature_name, enabled 
                FROM subscription_features 
                WHERE school_id = %s
                ORDER BY feature_name
            """, (school_id,))
            
            features = cursor.fetchall()
            if features:
                print("\nSubscription Features:")
                for feature, enabled in features:
                    status = "✓ Enabled" if enabled else "✗ Disabled"
                    print(f"  {feature}: {status}")
                    
                # Check specifically for lesson_notes
                lesson_notes_enabled = any(f[0] == 'lesson_notes' and f[1] for f in features)
                if lesson_notes_enabled:
                    print("\n✅ lesson_notes feature is ENABLED")
                else:
                    print("\n⚠️  lesson_notes feature is NOT enabled or doesn't exist")
                    print("   This could be why submission is failing!")
            else:
                print("\n⚠️  No subscription features found for this school")
        else:
            print("\n⚠️  subscription_features table does not exist")
            print("   Feature checking may not be implemented")
    else:
        print("✗ No school found in database")
    
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f"✗ Error: {e}")
