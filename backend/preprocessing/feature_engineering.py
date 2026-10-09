"""
Feature Engineering Module
══════════════════════════
Derives ML-ready features from raw PaySim transaction data.

PaySim columns
──────────────
step, type, amount, nameOrig, oldbalanceOrg, newbalanceOrig,
nameDest, oldbalanceDest, newbalanceDest, isFraud, isFlaggedFraud

Engineered feature groups
─────────────────────────
1. Transaction velocity   – count of txns by the same originator in 1 hr / 24 hr
2. Time-based             – hour of day, day of week, is_weekend
3. Amount deviation       – z-score relative to user's historical average
4. Account age            – how many steps (hours) since first txn by originator
5. Balance anomaly flags  – discrepancies in pre/post balances (proxy for location anomaly)
6. Transaction type       – one-hot encoded
"""

from __future__ import annotations

import numpy as np
import pandas as pd


# ── Feature column list (defines model input order) ─────────────
FEATURE_COLUMNS: list[str] = [
    # Amount & balance
    "amount",
    "amount_log",
    "balance_delta_orig",
    "balance_delta_dest",
    "balance_error_orig",
    "balance_error_dest",
    # Velocity
    "velocity_1h",
    "velocity_24h",
    # Time
    "hour_of_day",
    "day_of_week",
    "is_weekend",
    # Amount deviation
    "amount_zscore",
    "amount_over_avg_ratio",
    # Account age
    "account_age_hours",
    # Type one-hot  (PaySim types: CASH_IN, CASH_OUT, DEBIT, PAYMENT, TRANSFER)
    "type_CASH_IN",
    "type_CASH_OUT",
    "type_DEBIT",
    "type_PAYMENT",
    "type_TRANSFER",
]


# ═══════════════════════════════════════════════════════════════
# Batch feature engineering (for training on full DataFrame)
# ═══════════════════════════════════════════════════════════════

def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Accept a raw PaySim DataFrame, return a new DataFrame with only
    the engineered feature columns plus the 'isFraud' target.

    The input DataFrame is **not** mutated.
    """
    data = df.copy()

    # ── Normalise type names (sometimes contain hyphens) ────
    data["type"] = data["type"].str.replace("-", "_").str.upper()

    # ── 1. Amount & balance features ────────────────────────
    data["amount_log"] = np.log1p(data["amount"])
    data["balance_delta_orig"] = data["newbalanceOrig"] - data["oldbalanceOrg"]
    data["balance_delta_dest"] = data["newbalanceDest"] - data["oldbalanceDest"]

    # Balance error: expected new = old - amount (orig) / old + amount (dest)
    # Deviation from this expectation is a strong fraud signal.
    data["balance_error_orig"] = (
        data["oldbalanceOrg"] - data["amount"] - data["newbalanceOrig"]
    )
    data["balance_error_dest"] = (
        data["oldbalanceDest"] + data["amount"] - data["newbalanceDest"]
    )

    # ── 2. Transaction velocity ─────────────────────────────
    data = _add_velocity_features(data)

    # ── 3. Time-based features ──────────────────────────────
    data["hour_of_day"] = data["step"] % 24
    data["day_of_week"] = (data["step"] // 24) % 7
    data["is_weekend"] = (data["day_of_week"] >= 5).astype(int)

    # ── 4. Amount deviation from user average ───────────────
    data = _add_amount_deviation(data)

    # ── 5. Account age (hours since first txn) ──────────────
    first_step = data.groupby("nameOrig")["step"].transform("min")
    data["account_age_hours"] = data["step"] - first_step

    # ── 6. One-hot encode transaction type ──────────────────
    for txn_type in ["CASH_IN", "CASH_OUT", "DEBIT", "PAYMENT", "TRANSFER"]:
        col = f"type_{txn_type}"
        data[col] = (data["type"] == txn_type).astype(int)

    # ── Select only the feature columns + target ────────────
    target_col = "isFraud" if "isFraud" in data.columns else None
    out_cols = [c for c in FEATURE_COLUMNS if c in data.columns]
    if target_col:
        out_cols.append(target_col)

    return data[out_cols]


# ═══════════════════════════════════════════════════════════════
# Single-transaction feature extraction (for real-time inference)
# ═══════════════════════════════════════════════════════════════

def extract_single_transaction_features(
    txn: dict,
    history_df: pd.DataFrame | None = None,
) -> np.ndarray:
    """
    Given a single transaction dict (with PaySim column names) and
    optionally a DataFrame of the originator's recent history, return
    a 1-D numpy feature vector matching FEATURE_COLUMNS order.

    If *history_df* is None, velocity / deviation features default to 0.
    """
    f: dict[str, float] = {}

    amount = float(txn.get("amount", 0))
    f["amount"] = amount
    f["amount_log"] = np.log1p(amount)

    old_bo = float(txn.get("oldbalanceOrg", 0))
    new_bo = float(txn.get("newbalanceOrig", 0))
    old_bd = float(txn.get("oldbalanceDest", 0))
    new_bd = float(txn.get("newbalanceDest", 0))

    f["balance_delta_orig"] = new_bo - old_bo
    f["balance_delta_dest"] = new_bd - old_bd
    f["balance_error_orig"] = old_bo - amount - new_bo
    f["balance_error_dest"] = old_bd + amount - new_bd

    step = int(txn.get("step", 0))
    f["hour_of_day"] = step % 24
    f["day_of_week"] = (step // 24) % 7
    f["is_weekend"] = 1.0 if f["day_of_week"] >= 5 else 0.0

    # Velocity & deviation from history
    if history_df is not None and len(history_df) > 0:
        recent_steps = history_df["step"]
        f["velocity_1h"] = float((recent_steps >= step - 1).sum())
        f["velocity_24h"] = float((recent_steps >= step - 24).sum())

        avg = history_df["amount"].mean()
        std = history_df["amount"].std()
        f["amount_zscore"] = (amount - avg) / std if std > 0 else 0.0
        f["amount_over_avg_ratio"] = amount / avg if avg > 0 else 0.0

        f["account_age_hours"] = float(step - history_df["step"].min())
    else:
        f["velocity_1h"] = 0.0
        f["velocity_24h"] = 0.0
        f["amount_zscore"] = 0.0
        f["amount_over_avg_ratio"] = 0.0
        f["account_age_hours"] = 0.0

    # One-hot type
    txn_type = str(txn.get("type", "")).replace("-", "_").upper()
    for t in ["CASH_IN", "CASH_OUT", "DEBIT", "PAYMENT", "TRANSFER"]:
        f[f"type_{t}"] = 1.0 if txn_type == t else 0.0

    return np.array([f.get(c, 0.0) for c in FEATURE_COLUMNS], dtype=np.float64)


# ═══════════════════════════════════════════════════════════════
# Internal helpers
# ═══════════════════════════════════════════════════════════════

def _add_velocity_features(df: pd.DataFrame) -> pd.DataFrame:
    """Count of transactions by the same originator within 1h and 24h windows."""
    df = df.sort_values(["nameOrig", "step"])

    # Rolling count within time window (step-based, 1 step = 1 hour)
    vel_1h = (
        df.groupby("nameOrig")
        .rolling(window=2, on="step", min_periods=1)["step"]
        .count()
        .reset_index(level=0, drop=True)
    )
    vel_24h = (
        df.groupby("nameOrig")
        .rolling(window=25, on="step", min_periods=1)["step"]
        .count()
        .reset_index(level=0, drop=True)
    )

    df["velocity_1h"] = vel_1h.values
    df["velocity_24h"] = vel_24h.values
    return df


def _add_amount_deviation(df: pd.DataFrame) -> pd.DataFrame:
    """Z-score and ratio of current amount vs. user's historical average."""
    user_stats = df.groupby("nameOrig")["amount"].agg(["mean", "std"])
    user_stats.columns = ["user_avg", "user_std"]
    user_stats["user_std"] = user_stats["user_std"].fillna(0)

    df = df.merge(user_stats, left_on="nameOrig", right_index=True, how="left")

    df["amount_zscore"] = np.where(
        df["user_std"] > 0,
        (df["amount"] - df["user_avg"]) / df["user_std"],
        0.0,
    )
    df["amount_over_avg_ratio"] = np.where(
        df["user_avg"] > 0,
        df["amount"] / df["user_avg"],
        0.0,
    )

    df.drop(columns=["user_avg", "user_std"], inplace=True)
    return df
