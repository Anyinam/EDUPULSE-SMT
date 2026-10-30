#!/usr/bin/env python
"""Upgrade school subscription to enable lesson_notes feature"""

import os
import psycopg2

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
    conn.autocommit = True
    cursor = conn.cursor()
    
    print("=== Upgrading School Subscription ===\n")
    
    # Get current plan
    cursor.execute("SELECT id, name, subscription_plan FROM schools LIMIT 1")
    school = cursor.fetchone()
    
    if school:
        school_id, school_name, current_plan = school
        print(f"School: {school_name}")
        print(f"Current Plan: {current_plan}")
        
        # Upgrade to Basic plan
        new_plan = "Basic"
        cursor.execute("""
            UPDATE schools 
            SET subscription_plan = %s 
            WHERE id = %s
        """, (new_plan, school_id))
        
        print(f"\n✅ Successfully upgraded to: {new_plan}")
        print("\nFeatures now enabled:")
        print("  ✓ Lesson Notes (Full Access)")
        print("  ✓ Grade Entry")
        print("  ✓ Attendance (Full Access)")
        print("  ✓ AI Analysis (Basic)")
        print("  ✓ Multiple Report Templates")
        print("\nLimits:")
        print("  • Max Classes: 5")
        print("  • Max Students: 200")
        print("  • Max Staff: 15")
        
        # Verify
        cursor.execute("SELECT subscription_plan FROM schools WHERE id = %s", (school_id,))
        updated_plan = cursor.fetchone()[0]
        
        if updated_plan == new_plan:
            print(f"\n✓ Verification passed: School is now on {updated_plan} plan")
        else:
            print(f"\n✗ Verification failed: Expected {new_plan}, got {updated_plan}")
    else:
        print("✗ No school found in database")
    
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f"✗ Error: {e}")
