#!/usr/bin/env python3
"""
Create a platform admin user for the Platform Owner Console.
"""
import sys
import os
from datetime import datetime, timezone

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from backend.api.models import db, PlatformUser
from backend.config import app

def create_platform_user(username, email, password):
    """Create a platform admin user."""
    with app.app_context():
        # Check if user exists
        existing = PlatformUser.query.filter(
            (PlatformUser.username == username) | (PlatformUser.email == email)
        ).first()
        
        if existing:
            print(f"❌ User with username '{username}' or email '{email}' already exists!")
            return False
        
        # Create new user
        user = PlatformUser(
            username=username,
            email=email,
            is_active=True,
            created_at=datetime.now(timezone.utc)
        )
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        
        print(f"✅ Platform user created successfully!")
        print(f"   Username: {username}")
        print(f"   Email: {email}")
        print(f"\nYou can now log in at: http://localhost:3000/platform-console")
        return True

if __name__ == '__main__':
    print("=" * 60)
    print("Create Platform Admin User")
    print("=" * 60)
    
    if len(sys.argv) == 4:
        username = sys.argv[1]
        email = sys.argv[2]
        password = sys.argv[3]
    else:
        username = input("Username: ").strip()
        email = input("Email: ").strip()
        password = input("Password: ").strip()
    
    if not username or not email or not password:
        print("❌ All fields are required!")
        sys.exit(1)
    
    create_platform_user(username, email, password)
