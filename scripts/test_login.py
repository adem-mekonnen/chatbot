#!/usr/bin/env python3
"""
Quick login test script
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.security import authenticate_user_credentials

async def test_login():
    """Test login for all demo users"""
    
    test_users = [
        ("admin", "admin123"),
        ("alice", "alice123"),
        ("bob", "bob123"),
        ("1001", "dev_password_ahmed"),
        ("1002", "dev_password_sara"),
    ]
    
    print("Testing login credentials...")
    print("=" * 60)
    
    for username, password in test_users:
        try:
            user = await authenticate_user_credentials(username, password)
            if user:
                print(f"✅ {username:15} : SUCCESS (role: {user.get('role')})")
            else:
                print(f"❌ {username:15} : FAILED (invalid credentials)")
        except Exception as e:
            print(f"❌ {username:15} : ERROR - {e}")
    
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_login())
