"""
SQLAlchemy ORM models for the fraud-detection database.

Currently defines:
  • Admin        – administrator / user accounts (username / hashed password / phone / role)
  • OTPCode      – one-time passwords linked to an admin
  • Transaction  – financial transactions with fraud-detection metadata
  • FrozenAccount– accounts that have been frozen
  • FraudLabel   – admin-applied fraud / false-positive labels
"""

from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, ForeignKey, create_engine, Float, text
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

from config import get_settings

settings = get_settings()

engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ── Helper ──────────────────────────────────────────────────────
def utcnow():
    return datetime.now(timezone.utc)


# ── Admin table ─────────────────────────────────────────────────
class Admin(Base):
    __tablename__ = "admins"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    phone = Column(String(20), nullable=False)
    role = Column(String(20), nullable=False, default="user")       # "admin" | "user"
    account_frozen = Column(Boolean, default=False)
    failed_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    otp_codes = relationship("OTPCode", back_populates="admin")
    submitted_transactions = relationship("Transaction", back_populates="submitter")


# ── OTP table ───────────────────────────────────────────────────
class OTPCode(Base):
    __tablename__ = "otp_codes"

    id = Column(Integer, primary_key=True, index=True)
    admin_id = Column(Integer, ForeignKey("admins.id"), nullable=False)
    code = Column(String(6), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    admin = relationship("Admin", back_populates="otp_codes")


# ── Valid transaction statuses ──────────────────────────────────
TRANSACTION_STATUSES = (
    "approved", "pending_otp", "cleared", "blocked",
    "confirmed_fraud", "false_positive", "frozen",
)


# ── Transaction table ───────────────────────────────────────────
class Transaction(Base):
    __tablename__ = "transactions"
    
    id = Column(Integer, primary_key=True, index=True)
    step = Column(Integer, default=1)
    type = Column(String(50), nullable=False)
    amount = Column(Float, nullable=False)
    nameOrig = Column(String(50), nullable=False)
    oldbalanceOrg = Column(Float, nullable=False)
    newbalanceOrig = Column(Float, nullable=False)
    nameDest = Column(String(50), nullable=False)
    oldbalanceDest = Column(Float, nullable=False)
    newbalanceDest = Column(Float, nullable=False)
    
    isFraud = Column(Integer, default=0)
    isFlaggedFraud = Column(Integer, default=0)
    
    risk_score = Column(Integer, nullable=True)
    risk_tier = Column(String(20), nullable=True)
    status = Column(String(30), nullable=False, default="approved")  # see TRANSACTION_STATUSES
    submitted_by = Column(Integer, ForeignKey("admins.id"), nullable=True)
    timestamp = Column(DateTime(timezone=True), default=utcnow)

    submitter = relationship("Admin", back_populates="submitted_transactions")

# ── FrozenAccount table ─────────────────────────────────────────
class FrozenAccount(Base):
    __tablename__ = "frozen_accounts"
    
    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(String(50), unique=True, nullable=False, index=True)
    frozen_at = Column(DateTime(timezone=True), default=utcnow)


# ── FraudLabel table ────────────────────────────────────────────
class FraudLabel(Base):
    __tablename__ = "fraud_labels"
    
    id = Column(Integer, primary_key=True, index=True)
    transaction_id = Column(Integer, ForeignKey("transactions.id"), nullable=False)
    is_fraud = Column(Boolean, nullable=False)
    labeled_by = Column(Integer, ForeignKey("admins.id"), nullable=False)
    processed = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    
    transaction = relationship("Transaction")
    admin = relationship("Admin")


# ── DB helpers ──────────────────────────────────────────────────
def _safe_alter(conn, sql: str) -> None:
    """Execute an ALTER / CREATE INDEX, silently ignoring if already exists."""
    try:
        conn.execute(text(sql))
    except Exception:
        pass


def init_db():
    """Create all tables (call once on startup)."""
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        # ── admins table migrations ─────────────────────────────
        _safe_alter(conn, "ALTER TABLE admins ADD COLUMN email VARCHAR(255)")
        _safe_alter(conn, "CREATE UNIQUE INDEX ix_admins_email ON admins (email)")
        _safe_alter(conn, "ALTER TABLE admins ADD COLUMN role VARCHAR(20) DEFAULT 'user'")
        _safe_alter(conn, "ALTER TABLE admins ADD COLUMN account_frozen BOOLEAN DEFAULT FALSE")
        # ── transactions table migrations ───────────────────────
        _safe_alter(conn, "ALTER TABLE transactions ADD COLUMN status VARCHAR(30) DEFAULT 'approved'")
        _safe_alter(conn, "ALTER TABLE transactions ADD COLUMN submitted_by INTEGER REFERENCES admins(id)")


def get_db():
    """FastAPI dependency — yields a DB session and auto-closes."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
