from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, Float, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from datetime import datetime
from database import Base
from embeddings import EMBEDDING_DIM

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    websites = relationship("Website", back_populates="owner", passive_deletes=True)
    refresh_tokens = relationship("RefreshToken", passive_deletes=True)

class Website(Base):
    __tablename__ = "websites"
    # Different users may monitor the same URL; one user can't add it twice.
    __table_args__ = (UniqueConstraint("owner_id", "url", name="uq_websites_owner_url"),)
    id = Column(Integer, primary_key=True, index=True)
    url = Column(String(255), nullable=False)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    owner = relationship("User", back_populates="websites")
    checks = relationship("Check", back_populates="website", passive_deletes=True)

class Check(Base):
    __tablename__ = "checks"
    id = Column(Integer, primary_key=True, index=True)
    website_id = Column(Integer, ForeignKey("websites.id", ondelete="CASCADE"), nullable=False, index=True)
    status_code = Column(Integer, nullable=True)
    response_time_ms = Column(Float, nullable=True)
    is_up = Column(Boolean, nullable=False)
    error = Column(String, nullable=True)
    checked_at = Column(DateTime, default=datetime.utcnow, index=True)
    ai_summary = Column(Text, nullable=True)
    embedding = Column(Vector(EMBEDDING_DIM), nullable=True)
    website = relationship("Website", back_populates="checks")

class RefreshToken(Base):
    """Opaque refresh tokens, stored hashed so a DB leak doesn't hand out sessions.
    Rotated on every use; presenting a revoked token revokes the whole family (reuse detection)."""
    __tablename__ = "refresh_tokens"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(64), unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    revoked_at = Column(DateTime, nullable=True)
