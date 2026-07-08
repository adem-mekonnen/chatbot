#!/usr/bin/env python3
import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.database import get_async_db_session, UserEntity
from app.security import pwd_context, verify_password
from sqlalchemy import select

async def check_admin():
    async with get_async_db_session() as db:
        result = await db.execute(select(UserEntity).where(UserEntity.user_id == 'admin'))
        admin_user = result.scalars().first()
        
        if admin_user:
            print(f'Admin user found: {admin_user.user_id}, role: {admin_user.role}')
            test_result = verify_password('admin123', admin_user.password_hash)
            print(f'Password verification for "admin123": {test_result}')
            
            # Test other passwords
            print(f'Password hash: {admin_user.password_hash[:50]}...')
        else:
            print('Admin user not found!')
            
            # List all users
            result = await db.execute(select(UserEntity))
            all_users = result.scalars().all()
            print(f"Available users:")
            for user in all_users:
                print(f"  - {user.user_id} ({user.role})")

if __name__ == "__main__":
    asyncio.run(check_admin())