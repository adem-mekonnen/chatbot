#!/usr/bin/env python3
import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.database import get_async_db_session, AccountEntity
from sqlalchemy import select

async def list_accounts():
    async with get_async_db_session() as db:
        result = await db.execute(select(AccountEntity))
        accounts = result.scalars().all()
        
        print('Available accounts:')
        for acc in accounts:
            print(f'  - ID: {acc.account_id}, Name: {acc.name}, Balance: {acc.balance} {acc.currency}')

if __name__ == "__main__":
    asyncio.run(list_accounts())