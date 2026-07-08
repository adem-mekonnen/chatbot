#!/usr/bin/env python3
import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.database import get_async_db_session, UserEntity
from app.security import pwd_context
from sqlalchemy import select, update

async def reset_admin_password():
    new_password = "admin123"
    hashed_password = pwd_context.hash(new_password)
    
    async with get_async_db_session() as db:
        # Update admin password
        result = await db.execute(
            update(UserEntity)
            .where(UserEntity.user_id == 'admin')
            .values(password_hash=hashed_password)
        )
        
        if result.rowcount > 0:
            await db.commit()
            print(f"✅ Admin password reset successfully")
            
            # Verify the update
            result = await db.execute(select(UserEntity).where(UserEntity.user_id == 'admin'))
            admin_user = result.scalars().first()
            
            if admin_user:
                # Test verification
                from app.security import verify_password
                is_valid = verify_password(new_password, admin_user.password_hash)
                print(f"✅ Password verification test: {is_valid}")
            
        else:
            print("❌ Admin user not found or not updated")

if __name__ == "__main__":
    asyncio.run(reset_admin_password())