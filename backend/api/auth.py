"""
Authentication API  (/api/v1/auth)

Endpoints
─────────
POST /login         – validate username + password → send OTP via Twilio
POST /verify-otp    – validate OTP → issue JWT access token
POST /refresh       – refresh an existing JWT before it expires
GET  /me            – return the currently-authenticated admin profile

Lockout policy
──────────────
After MAX_LOGIN_ATTEMPTS consecutive failures the account is locked for
LOCKOUT_DURATION_MINUTES.  A successful login resets the counter.

Role-based access
─────────────────
The JWT payload carries `role` and `user_id`.  Use the reusable
`require_role(*roles)` dependency to restrict endpoints by role.
"""

import random
import string
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy.orm import Session

from config import get_settings
from models.db_models import Admin, OTPCode, get_db

# ── Router ──────────────────────────────────────────────────────
router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])
settings = get_settings()

# ── Security helpers ────────────────────────────────────────────
pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")



# ── Pydantic schemas ───────────────────────────────────────────
class LoginRequest(BaseModel):
    username: str
    password: str


class OTPVerifyRequest(BaseModel):
    username: str
    otp_code: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int          # seconds
    role: str = ""           # echoed back so the frontend can adapt UI


class MessageResponse(BaseModel):
    message: str


class AdminProfile(BaseModel):
    id: int
    username: str
    email: str
    phone: str
    role: str
    account_frozen: bool
    is_active: bool

    model_config = {"from_attributes": True}


# ── Utility functions ──────────────────────────────────────────
def _generate_otp(length: int = 6) -> str:
    """Return a random numeric OTP."""
    return "".join(random.choices(string.digits, k=length))


def _create_access_token(data: dict) -> tuple[str, int]:
    """Create a signed JWT and return (token, expires_in_seconds)."""
    expires_delta = timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    expire = datetime.now(timezone.utc) + expires_delta
    to_encode = {**data, "exp": expire}
    token = jwt.encode(
        to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM,
    )
    return token, int(expires_delta.total_seconds())


def _send_otp_email(to_email: str, otp: str, role: str = "admin") -> None:
    """Send the OTP via Gmail SMTP."""
    import smtplib
    from email.mime.text import MIMEText
    
    if not settings.GMAIL_ADDRESS or not settings.GMAIL_APP_PASSWORD:
        print(f"[Mock OTP Email to {to_email}]: {otp}")
        return

    if role == "user":
        msg = MIMEText(f"Your OTP code is: {otp}")
        msg['Subject'] = 'Your OTP Code'
    else:
        msg = MIMEText(f"Your fraud-detection admin OTP is: {otp}")
        msg['Subject'] = 'Your Admin OTP Code'
        
    msg['From'] = settings.GMAIL_ADDRESS
    msg['To'] = to_email

    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login(settings.GMAIL_ADDRESS, settings.GMAIL_APP_PASSWORD)
    server.send_message(msg)
    server.quit()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ── Dependency: get current admin from JWT ──────────────────────
async def get_current_admin(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Admin:
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        username: str | None = payload.get("sub")
        if username is None:
            raise credentials_exc
    except JWTError:
        raise credentials_exc

    admin = db.query(Admin).filter(Admin.username == username).first()
    if admin is None or not admin.is_active:
        raise credentials_exc
    return admin


# ── Dependency: role-based access control ───────────────────
def require_role(*allowed_roles: str):
    """
    Return a FastAPI dependency that ensures the authenticated user
    has one of the *allowed_roles*.  Raises HTTP 403 otherwise.

    Usage:
        @router.get("/admin-only", dependencies=[Depends(require_role("admin"))])
        @router.post("/any-user",  dependencies=[Depends(require_role("admin", "user"))])
    """
    async def _role_checker(
        current_user: Admin = Depends(get_current_admin),
    ) -> Admin:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{current_user.role}' is not authorised for this action. "
                       f"Required: {', '.join(allowed_roles)}",
            )
        return current_user
    return _role_checker


# ── POST /login ─────────────────────────────────────────────────
@router.post("/login", response_model=MessageResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    """
    Step 1 of 2FA:
    Validate credentials → on success send OTP to admin's phone.
    """
    admin = db.query(Admin).filter(Admin.username == body.username).first()

    # --- unknown user → generic error (don't reveal existence) ---
    if admin is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    # --- check lockout ---
    if admin.locked_until and admin.locked_until > _utcnow():
        remaining = int((admin.locked_until - _utcnow()).total_seconds())
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=f"Account locked. Try again in {remaining} seconds.",
        )

    # --- verify password ---
    if not pwd_ctx.verify(body.password, admin.password_hash):
        admin.failed_attempts += 1
        if admin.failed_attempts >= settings.MAX_LOGIN_ATTEMPTS:
            admin.locked_until = _utcnow() + timedelta(
                minutes=settings.LOCKOUT_DURATION_MINUTES,
            )
            admin.failed_attempts = 0        # reset counter after lockout
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    # --- credentials OK → reset counter ---
    admin.failed_attempts = 0
    admin.locked_until = None

    # --- invalidate any previous unused OTPs ---
    db.query(OTPCode).filter(
        OTPCode.admin_id == admin.id,
        OTPCode.used == False,              # noqa: E712
    ).update({"used": True})

    # --- generate & persist new OTP ---
    otp = _generate_otp()
    otp_record = OTPCode(
        admin_id=admin.id,
        code=otp,
        expires_at=_utcnow() + timedelta(seconds=settings.OTP_EXPIRY_SECONDS),
    )
    db.add(otp_record)
    db.commit()

    # --- send Email ---
    try:
        _send_otp_email(admin.email, otp, role=admin.role)
    except Exception as e:
        print(f"Failed to send email: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to send OTP. Please try again.",
        )

    return {"message": "OTP sent to your registered email address"}


# ── POST /verify-otp ───────────────────────────────────────────
@router.post("/verify-otp", response_model=TokenResponse)
def verify_otp(body: OTPVerifyRequest, db: Session = Depends(get_db)):
    """
    Step 2 of 2FA:
    Validate the OTP → on success issue a JWT access token.
    """
    admin = db.query(Admin).filter(Admin.username == body.username).first()
    if admin is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid request",
        )

    otp_record = (
        db.query(OTPCode)
        .filter(
            OTPCode.admin_id == admin.id,
            OTPCode.code == body.otp_code,
            OTPCode.used == False,           # noqa: E712
        )
        .order_by(OTPCode.created_at.desc())
        .first()
    )

    if otp_record is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid OTP",
        )

    if otp_record.expires_at < _utcnow():
        otp_record.used = True
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="OTP has expired. Please login again.",
        )

    # --- OTP valid → mark used & issue JWT ---
    otp_record.used = True
    db.commit()

    token, expires_in = _create_access_token({
        "sub": admin.username,
        "role": admin.role,
        "user_id": admin.id,
    })
    return TokenResponse(
        access_token=token,
        expires_in=expires_in,
        role=admin.role,
    )


# ── POST /refresh ──────────────────────────────────────────────
@router.post("/refresh", response_model=TokenResponse)
def refresh_token(admin: Admin = Depends(require_role("admin", "user"))):
    """Issue a fresh JWT for an already-authenticated user (any role)."""
    token, expires_in = _create_access_token({
        "sub": admin.username,
        "role": admin.role,
        "user_id": admin.id,
    })
    return TokenResponse(
        access_token=token,
        expires_in=expires_in,
        role=admin.role,
    )


# ── GET /me ────────────────────────────────────────────────────
@router.get("/me", response_model=AdminProfile)
def read_current_admin(admin: Admin = Depends(require_role("admin", "user"))):
    """Return the profile of the currently-authenticated user (any role)."""
    return admin
