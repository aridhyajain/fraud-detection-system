"""
Admin API  (/api/v1/admin)
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timezone

from models.db_models import Admin, Transaction, get_db
from api.auth import require_role, pwd_ctx

router = APIRouter(prefix="/api/v1/admin", tags=["Admin"])

class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: str

class UserCreateResponse(BaseModel):
    id: int
    username: str
    email: str
    role: str
    
    class Config:
        from_attributes = True

@router.post("/users/create", response_model=UserCreateResponse)
def create_user(
    user_in: UserCreate,
    db: Session = Depends(get_db),
    current_admin=Depends(require_role("admin"))
):
    """Admin creates a new user or admin."""
    if user_in.role not in ["admin", "user"]:
        raise HTTPException(status_code=400, detail="Role must be admin or user")
        
    # Check if username or email exists
    if db.query(Admin).filter(Admin.username == user_in.name).first():
        raise HTTPException(status_code=400, detail="Username already registered")
    if db.query(Admin).filter(Admin.email == user_in.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
        
    hashed_password = pwd_ctx.hash(user_in.password)
    
    new_user = Admin(
        username=user_in.name,
        email=user_in.email,
        password_hash=hashed_password,
        role=user_in.role,
        phone="0000000000"  # default placeholder
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return new_user

class UserListResponse(BaseModel):
    id: int
    name: str
    email: str
    account_frozen: bool

    class Config:
        from_attributes = True

@router.get("/users", response_model=List[UserListResponse])
def get_users(
    db: Session = Depends(get_db),
    current_admin=Depends(require_role("admin"))
):
    """Returns a list of all users."""
    users = db.query(Admin).all()
    
    # Map 'username' to 'name' for the response
    response = []
    for u in users:
        response.append(UserListResponse(
            id=u.id,
            name=u.username,
            email=u.email,
            account_frozen=u.account_frozen
        ))
    return response

class StatsResponse(BaseModel):
    total_transactions_today: int
    total_blocked_today: int
    total_pending_otp: int
    total_confirmed_fraud_all_time: int
    fraud_rate_percentage: float

@router.get("/stats", response_model=StatsResponse)
def get_stats(
    db: Session = Depends(get_db),
    current_admin=Depends(require_role("admin"))
):
    """Returns aggregated statistics for the admin dashboard."""
    now = datetime.now(timezone.utc)
    start_of_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    total_transactions_today = db.query(Transaction).filter(Transaction.timestamp >= start_of_today).count()
    total_blocked_today = db.query(Transaction).filter(
        Transaction.timestamp >= start_of_today,
        Transaction.status == "blocked"
    ).count()
    
    total_pending_otp = db.query(Transaction).filter(Transaction.status == "pending_otp").count()
    
    total_confirmed_fraud_all_time = db.query(Transaction).filter(Transaction.isFraud == 1).count()
    total_transactions_all_time = db.query(Transaction).count()
    
    fraud_rate_percentage = 0.0
    if total_transactions_all_time > 0:
        fraud_rate_percentage = (total_confirmed_fraud_all_time / total_transactions_all_time) * 100.0
        
    return StatsResponse(
        total_transactions_today=total_transactions_today,
        total_blocked_today=total_blocked_today,
        total_pending_otp=total_pending_otp,
        total_confirmed_fraud_all_time=total_confirmed_fraud_all_time,
        fraud_rate_percentage=round(fraud_rate_percentage, 2)
    )
