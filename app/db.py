from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./chat_app.db")


# SQLAlchemy async engine and sessionmaker will be used later; for simplicity we use sync for now
engine = create_engine(
    "sqlite:///./chat_app.db", connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
