from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
import os
from dotenv import load_dotenv

load_dotenv()

database_url=os.getenv("sql_url")

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

engine = create_async_engine (database_url)
AsyncSessionLocal = sessionmaker (engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()