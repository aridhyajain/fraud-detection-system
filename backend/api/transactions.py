"""
Transaction API  (/api/v1/transactions)

Future endpoints:
─────────────────
POST /submit          – ingest a new UPI / bank-transfer transaction
GET  /                – list transactions with pagination & filters
GET  /{id}            – get a single transaction with its risk score
POST /{id}/review     – admin marks a flagged transaction as fraud or false-positive
GET  /stats           – aggregate statistics for the dashboard
"""

import random
import string
from typing import List, Optional
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel

from models.db_models import Transaction, Admin, OTPCode, get_db
from api.auth import require_role
from services.fraud_detection import detect
from services.actions import freeze_account, alert_customer
from models.db_models import FraudLabel
from config import get_settings

router = APIRouter(prefix="/api/v1/transactions", tags=["Transactions"])
settings = get_settings()


# ── Pydantic schemas ────────────────────────────────────────────

class TransactionCreate(BaseModel):
    step: int = 1
    type: str
    amount: float
    nameOrig: str
    oldbalanceOrg: float
    newbalanceOrig: float
    nameDest: str
    oldbalanceDest: float
    newbalanceDest: float
    isFraud: int = 0
    isFlaggedFraud: int = 0


class TransactionResponse(TransactionCreate):
    id: int
    risk_score: Optional[int]
    risk_tier: Optional[str]
    status: Optional[str]
    timestamp: datetime

    class Config:
        from_attributes = True


class UserTransactionResponse(BaseModel):
    """Response schema for user-facing /my endpoint — excludes risk_score and risk_tier."""
    id: int
    step: int
    type: str
    amount: float
    nameOrig: str
    oldbalanceOrg: float
    newbalanceOrig: float
    nameDest: str
    oldbalanceDest: float
    newbalanceDest: float
    isFraud: int
    isFlaggedFraud: int
    status: Optional[str]
    timestamp: datetime

    class Config:
        from_attributes = True


class SubmitResponse(BaseModel):
    status: str
    message: Optional[str] = None
    transaction_id: Optional[int] = None


class OTPVerifyRequest(BaseModel):
    transaction_id: int
    otp: str


class OTPVerifyResponse(BaseModel):
    status: str
    message: str


# ── Helpers ─────────────────────────────────────────────────────

def _generate_txn_otp(length: int = 6) -> str:
    """Return a random numeric OTP for transaction verification."""
    return "".join(random.choices(string.digits, k=length))


def _send_transaction_email(to_email: str, subject: str, body: str) -> None:
    """Send a transaction notification email via Gmail SMTP."""
    if not settings.GMAIL_ADDRESS or not settings.GMAIL_APP_PASSWORD:
        print(f"[Mock Txn Email to {to_email}]: {body}")
        return

    import smtplib
    from email.mime.text import MIMEText

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = settings.GMAIL_ADDRESS
    msg["To"] = to_email

    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.starttls()
    server.login(settings.GMAIL_ADDRESS, settings.GMAIL_APP_PASSWORD)
    server.send_message(msg)
    server.quit()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ═══════════════════════════════════════════════════════════════
# Admin-only endpoints (existing)
# ═══════════════════════════════════════════════════════════════

@router.get("/", response_model=List[TransactionResponse])
def get_all_transactions(
    db: Session = Depends(get_db),
    current_admin=Depends(require_role("admin"))
):
    """Return all transactions with risk scores."""
    txns = db.query(Transaction).all()
    for txn in txns:
        # Normalize badge to HIGH
        if txn.risk_tier in ("High", "CRITICAL") or (txn.risk_score is not None and txn.risk_score > 70):
            txn.risk_tier = "HIGH"
    return txns


@router.get("/my", response_model=List[UserTransactionResponse])
def get_my_transactions(
    db: Session = Depends(get_db),
    current_user: Admin = Depends(require_role("user"))
):
    """Return only transactions submitted by the calling user (excludes risk_score/risk_tier)."""
    return (
        db.query(Transaction)
        .filter(Transaction.submitted_by == current_user.id)
        .order_by(Transaction.timestamp.desc())
        .all()
    )


@router.get("/{id}", response_model=TransactionResponse)
def get_transaction(
    id: int,
    db: Session = Depends(get_db),
    current_admin=Depends(require_role("admin"))
):
    """Return single transaction details."""
    txn = db.query(Transaction).filter(Transaction.id == id).first()
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return txn


@router.post("/analyze", response_model=TransactionResponse)
def analyze_transaction(
    txn: TransactionCreate,
    db: Session = Depends(get_db),
    current_admin=Depends(require_role("admin"))
):
    """Run fraud detection on a given transaction and return risk score + tier."""
    txn_dict = txn.model_dump()
    
    # Run pipeline
    risk_result = detect(txn_dict)
    
    # Store to DB
    db_txn = Transaction(
        **txn_dict,
        risk_score=risk_result["score"],
        risk_tier=risk_result["tier"]
    )
    db.add(db_txn)
    db.commit()
    db.refresh(db_txn)
    
    return db_txn


# ═══════════════════════════════════════════════════════════════
# User-facing endpoints (Phase 6B)
# ═══════════════════════════════════════════════════════════════

@router.post("/submit", response_model=SubmitResponse)
def submit_transaction(
    txn: TransactionCreate,
    db: Session = Depends(get_db),
    current_user: Admin = Depends(require_role("user"))
):
    """
    User submits a transaction through the fraud pipeline.

    Flow:
    1. Check if account is frozen → reject immediately.
    2. Run full fraud detection pipeline.
    3. Branch on risk tier:
       - Low    → approved, email confirmation.
       - Medium → pending_otp, generate OTP, email OTP.
       - High   → blocked, email notification.
    """
    # ── Frozen account check ────────────────────────────────
    if current_user.account_frozen:
        return SubmitResponse(
            status="frozen",
            message="Your account has been suspended. Please contact support.",
        )

    # ── Run fraud pipeline ──────────────────────────────────
    txn_dict = txn.model_dump()
    age_td = _utcnow() - current_user.created_at
    txn_dict["account_age_days"] = age_td.total_seconds() / 86400.0
    risk_result = detect(txn_dict)

    tier = risk_result["tier"]    # "Low" / "Medium" / "High"
    score = risk_result["score"]

    # ── Determine status from tier ──────────────────────────
    if tier == "Low":
        txn_status = "approved"
    elif tier == "Medium":
        txn_status = "pending_otp"
    else:
        txn_status = "blocked"

    # Remove non-DB fields before persisting
    txn_dict.pop("account_age_days", None)

    # ── Persist the transaction ─────────────────────────────
    db_txn = Transaction(
        **txn_dict,
        risk_score=score,
        risk_tier=tier,
        status=txn_status,
        submitted_by=current_user.id,
    )
    db.add(db_txn)
    db.commit()
    db.refresh(db_txn)

    amount_str = f"₹{db_txn.amount:,.2f}"
    receiver = db_txn.nameDest

    # ── Low risk → approved ─────────────────────────────────
    if tier == "Low":
        try:
            _send_transaction_email(
                current_user.email,
                "Transaction Approved",
                f"Your transaction of {amount_str} to {receiver} has been approved.",
            )
        except Exception as e:
            print(f"Email send failed (approved): {e}")

        return SubmitResponse(
            status="approved",
            message="Transaction approved.",
            transaction_id=db_txn.id,
        )

    # ── Medium risk → pending_otp ───────────────────────────
    if tier == "Medium":
        otp = _generate_txn_otp()
        otp_record = OTPCode(
            admin_id=current_user.id,
            code=otp,
            expires_at=_utcnow() + timedelta(seconds=settings.OTP_EXPIRY_SECONDS),
        )
        db.add(otp_record)

        # Store the transaction_id on the OTP for later lookup — we stash it
        # by flushing so the OTP row exists, then we'll look it up via user +
        # unused OTP during verify-otp.
        db.commit()

        try:
            _send_transaction_email(
                current_user.email,
                "Transaction Verification Required",
                f"Your transaction of {amount_str} to {receiver} requires verification. "
                f"Your OTP is {otp}.",
            )
        except Exception as e:
            print(f"Email send failed (OTP): {e}")

        return SubmitResponse(
            status="pending_otp",
            message="An OTP has been sent to your email.",
            transaction_id=db_txn.id,
        )

    # ── High risk → blocked ─────────────────────────────────
    try:
        _send_transaction_email(
            current_user.email,
            "Transaction Blocked",
            f"Your transaction of {amount_str} to {receiver} has been blocked "
            f"and flagged for review.",
        )
    except Exception as e:
        print(f"Email send failed (blocked): {e}")

    return SubmitResponse(
        status="blocked",
        transaction_id=db_txn.id,
    )


@router.post("/verify-otp", response_model=OTPVerifyResponse)
def verify_transaction_otp(
    body: OTPVerifyRequest,
    db: Session = Depends(get_db),
    current_user: Admin = Depends(require_role("user"))
):
    """
    Verify the OTP sent for a medium-risk transaction.

    Accepts transaction_id and otp.
    If OTP matches → set status to 'cleared'.
    If OTP wrong  → return 400 error.
    """
    # ── Find the transaction ────────────────────────────────
    txn = (
        db.query(Transaction)
        .filter(
            Transaction.id == body.transaction_id,
            Transaction.submitted_by == current_user.id,
            Transaction.status == "pending_otp",
        )
        .first()
    )
    if not txn:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found or not awaiting OTP verification.",
        )

    # ── Find the matching unused OTP for this user ──────────
    otp_record = (
        db.query(OTPCode)
        .filter(
            OTPCode.admin_id == current_user.id,
            OTPCode.code == body.otp,
            OTPCode.used == False,  # noqa: E712
        )
        .order_by(OTPCode.created_at.desc())
        .first()
    )

    if otp_record is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OTP.",
        )

    if otp_record.expires_at < _utcnow():
        otp_record.used = True
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OTP has expired. Please submit the transaction again.",
        )

    # ── OTP valid → clear transaction ───────────────────────
    otp_record.used = True
    txn.status = "cleared"
    db.commit()

    return OTPVerifyResponse(
        status="cleared",
        message="Transaction verified and cleared.",
    )


@router.post("/{id}/confirm-fraud", response_model=TransactionResponse)
def confirm_fraud(
    id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_admin=Depends(require_role("admin"))
):
    """Admin confirms a transaction is fraud: freeze sender, send alert."""
    txn = db.query(Transaction).filter(Transaction.id == id).first()
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")
        
    txn.isFraud = 1
    txn.isFlaggedFraud = 1
    
    # Log label
    label = FraudLabel(transaction_id=txn.id, is_fraud=True, labeled_by=current_admin.id)
    db.add(label)
    
    # Freeze account (sender)
    freeze_account(db, txn.nameOrig)
    
    # Alert customer and freeze user account
    submitter = db.query(Admin).filter(Admin.id == txn.submitted_by).first()
    if submitter:
        customer_email = submitter.email
        submitter.account_frozen = True
    else:
        customer_email = f"customer_{txn.nameOrig}@example.com"
        
    message = "Your account has been frozen due to suspicious activity. Please contact support."
    alert_customer(customer_email, message)
    
    db.commit()
    db.refresh(txn)
    
    from services.retraining import trigger_retraining_if_needed
    trigger_retraining_if_needed(background_tasks)
    
    return txn


@router.post("/{id}/false-positive", response_model=TransactionResponse)
def clear_false_positive(
    id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_admin=Depends(require_role("admin"))
):
    """Admin marks transaction as false positive: clear flags."""
    txn = db.query(Transaction).filter(Transaction.id == id).first()
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")
        
    txn.isFraud = 0
    txn.isFlaggedFraud = 0
    txn.risk_tier = "Low"  # reset risk
    txn.risk_score = 0
    
    # Log label
    label = FraudLabel(transaction_id=txn.id, is_fraud=False, labeled_by=current_admin.id)
    db.add(label)
    
    db.commit()
    db.refresh(txn)
    
    from services.retraining import trigger_retraining_if_needed
    trigger_retraining_if_needed(background_tasks)
    
    return txn


@router.post("/{id}/clear-pending", response_model=TransactionResponse)
def clear_pending_transaction(
    id: int,
    db: Session = Depends(get_db),
    current_admin=Depends(require_role("admin"))
):
    """Admin manually clears a pending_otp transaction."""
    txn = db.query(Transaction).filter(Transaction.id == id).first()
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")
        
    if txn.status != "pending_otp":
        raise HTTPException(status_code=400, detail="Transaction is not in pending_otp status")

    txn.status = "cleared"
    db.commit()
    db.refresh(txn)
    
    return txn
