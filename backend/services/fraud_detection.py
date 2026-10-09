"""
Fraud Detection Service

Will contain:
─────────────
• run_rule_based_filter(transaction) – hard rules for obvious fraud flags
• run_ml_prediction(transaction)     – invoke the ensemble model
• detect(transaction)                – orchestrate rule filter + ML scoring
"""

from typing import Any, Dict, Optional
from models.ml_model import predict
from services.risk_scorer import score_transaction

def run_rule_based_filter(transaction: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Apply hard business rules for obvious fraud cases.
    If a rule hits, we bypass the ML model and directly assign a high risk score.
    """
    amount = transaction.get("amount", 0)
    oldbalanceOrg = transaction.get("oldbalanceOrg", 0)
    newbalanceDest = transaction.get("newbalanceDest", 0)
    step = transaction.get("step", 0)
    
    # 0. Medium risk rule: Moderate amount from a new account (< 30 days)
    account_age_days = transaction.get("account_age_days", transaction.get("account_age_hours", float("inf")) / 24.0)
    print(f"[DEBUG] Medium risk check: amount={amount}, account_age_days={account_age_days:.2f}")
    if 10000 <= amount <= 100000 and account_age_days < 30:
        return score_transaction(0.60, context=transaction)

    # 1. Amount > threshold from a new account (or generally large amount)
    if amount > 200000:
        return score_transaction(0.99, context=transaction)
        
    # 2. Transaction at unusual hour (PaySim 'step' is 1 hour, so step % 24 gives hour of day)
    hour = step % 24
    if hour >= 0 and hour <= 4 and amount > 50000:
        return score_transaction(0.90, context=transaction)
        
    # 3. Complete drain of account (amount == oldbalanceOrg and amount is significant)
    if amount > 0 and amount == oldbalanceOrg and amount > 10000:
        return score_transaction(0.95, context=transaction)
        
    return None

def run_ml_prediction(transaction: Dict[str, Any]) -> Dict[str, Any]:
    """Invoke the ensemble ML model."""
    prob = predict(transaction)
    return score_transaction(prob, context=transaction)

def detect(transaction: Dict[str, Any]) -> Dict[str, Any]:
    """Orchestrate rule filter + ML scoring."""
    rule_result = run_rule_based_filter(transaction)
    if rule_result is not None:
        return rule_result
        
    return run_ml_prediction(transaction)
