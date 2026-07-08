#!/usr/bin/env python3
"""
Demo User Setup Script
Creates default demo users if they don't exist.
"""

import asyncio
import sys
import os

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.database import get_async_db_session, UserEntity, AccountEntity, init_db
from app.security import pwd_context
from sqlalchemy import select

async def setup_demo_users():
    """Create demo users if they don't exist"""
    
    # Initialize database first
    await init_db()
    
    demo_users = [
        {"user_id": "admin", "password": "admin123", "role": "admin"},
        {"user_id": "alice", "password": "alice123", "role": "customer"}, 
        {"user_id": "bob", "password": "bob123", "role": "customer"}
    ]
    
    async with get_async_db_session() as db:
        # Check existing users
        result = await db.execute(select(UserEntity))
        existing_users = {user.user_id for user in result.scalars().all()}
        
        # Check existing accounts
        result = await db.execute(select(AccountEntity))
        existing_accounts = {acc.account_id for acc in result.scalars().all()}
        
        print(f"Found {len(existing_users)} existing users: {existing_users}")
        print(f"Found {len(existing_accounts)} existing accounts: {existing_accounts}")
        
        # Create missing users
        for user_data in demo_users:
            user_id = user_data["user_id"]
            if user_id not in existing_users:
                print(f"Creating user: {user_id} ({user_data['role']})")
                
                # Create user
                hashed_password = pwd_context.hash(user_data["password"])
                user = UserEntity(
                    user_id=user_id,
                    password_hash=hashed_password,
                    role=user_data["role"]
                )
                db.add(user)
            else:
                print(f"User already exists: {user_id}")
            
            # Create account if it doesn't exist
            if user_id not in existing_accounts:
                print(f"Creating account for: {user_id}")
                account = AccountEntity(
                    account_id=user_id,
                    name=f"Account for {user_id}",
                    balance=1000.0 if user_data["role"] == "customer" else 0.0,
                    currency="ETB"
                )
                db.add(account)
            else:
                print(f"Account already exists for: {user_id}")
        
        await db.commit()
        print("✅ Demo users setup complete!")
        
        # Verify users
        result = await db.execute(select(UserEntity))
        all_users = result.scalars().all()
        print(f"\nFinal user list ({len(all_users)} users):")
        for user in all_users:
            print(f"  - {user.user_id} ({user.role})")

if __name__ == "__main__":
    asyncio.run(setup_demo_users())