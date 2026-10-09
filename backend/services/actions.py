"""
Actions Service

Will contain:
─────────────
• approve_transaction(txn_id)     – silently pass a low-risk transaction
• soft_block(txn_id)              – trigger OTP verification for medium-risk
• hard_block(txn_id)              – flag for admin review for high-risk
• freeze_account(account_id)      – freeze account & alert customer via SMS/email
• clear_transaction(txn_id)       – admin clears a flagged transaction
"""

from sqlalchemy.orm import Session
from models.db_models import FrozenAccount
from config import get_settings

settings = get_settings()

def freeze_account(db: Session, account_id: str):
    """Mark account as frozen in PostgreSQL."""
    existing = db.query(FrozenAccount).filter(FrozenAccount.account_id == account_id).first()
    if not existing:
        frozen = FrozenAccount(account_id=account_id)
        db.add(frozen)
        db.commit()
        db.refresh(frozen)
        return frozen
    return existing

def alert_customer(email: str, message: str):
    """Send email alert via Gmail SMTP."""
    if not settings.GMAIL_ADDRESS or not settings.GMAIL_APP_PASSWORD:
        print(f"[Mock Email to {email}]: {message}")
        return "mock_email_id"

    import smtplib
    from email.mime.text import MIMEText

    try:
        msg = MIMEText(message)
        msg['Subject'] = 'URGENT: Fraud Alert'
        msg['From'] = settings.GMAIL_ADDRESS
        msg['To'] = email

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(settings.GMAIL_ADDRESS, settings.GMAIL_APP_PASSWORD)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"SMTP error: {e}")
        return None
