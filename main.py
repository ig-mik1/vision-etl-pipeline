import os
from fastapi import FastAPI
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from sqlalchemy.pool import NullPool

# Load environment variables securely
load_dotenv()
DATABASE_URL = os.getenv("SUPABASE_DB_URL")

# Force SQLAlchemy to use the asyncpg driver
if DATABASE_URL and DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
    
# The Master Connection String Trick for Supabase Pooler (Port 6543)
engine = create_async_engine(
    DATABASE_URL,
    poolclass=NullPool, # Let Supabase handle the pooling
    connect_args={
        "statement_cache_size": 0,          # Critical fix for asyncpg
        "prepared_statement_cache_size": 0  # Critical fix for asyncpg
    }
)

# Lifecycle manager to test DB connection on startup
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("⏳ Booting up Live-Event SQL Assistant...")
    try:
        # Attempt to connect to the database and run a simple query
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
            print("✅ SUCCESS: Connected to Supabase PostgreSQL Database!")
    except Exception as e:
        print(f"❌ ERROR: Database connection failed: {e}")
    
    yield # App is running
    
    # Cleanup on shutdown
    print("🛑 Shutting down Database connections...")
    await engine.dispose()

# Initialize the FastAPI application
app = FastAPI(lifespan=lifespan, title="Live-Event SQL Assistant API")

@app.get("/")
async def root():
    return {"status": "online", "message": "Agent API is live and listening."}