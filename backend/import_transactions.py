"""
import_transactions.py
═════════════════════
Reads backend/data/dataset.csv, runs every row through the saved
ensemble fraud-detection model, and bulk-inserts the results into
the `transactions` PostgreSQL table.

Usage (from the backend/ directory, with the venv activated):
    python import_transactions.py
    python import_transactions.py --limit 5000
    python import_transactions.py --batch-size 500 --limit 20000
    python import_transactions.py --clear          # wipe existing rows first

Options
───────
--csv         Path to the CSV file  (default: data/dataset.csv)
--limit       Max rows to import    (default: all)
--batch-size  DB insert batch size  (default: 1000)
--clear       Delete existing transactions before importing
--model-dir   Path to saved_models/ (default: saved_models/)
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

# ── Make sure backend/ is on sys.path when run directly ─────────
_BACKEND_DIR = Path(__file__).resolve().parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from models.db_models import SessionLocal, Transaction, init_db
from models.ml_model import EnsembleModel
from preprocessing.feature_engineering import engineer_features, FEATURE_COLUMNS

# ── Paths ────────────────────────────────────────────────────────
_DEFAULT_CSV = _BACKEND_DIR / "data" / "dataset.csv"
_DEFAULT_MODEL_DIR = _BACKEND_DIR / "saved_models"


# ════════════════════════════════════════════════════════════════
# Risk scoring helpers
# ════════════════════════════════════════════════════════════════

def score_to_risk_tier(score: int) -> str:
    """Convert 0-100 integer risk score to a labelled tier."""
    if score >= 80:
        return "CRITICAL"
    if score >= 60:
        return "HIGH"
    if score >= 40:
        return "MEDIUM"
    return "LOW"


def prob_to_risk_score(prob: float) -> int:
    """Map a [0, 1] fraud probability to an integer 0-100 risk score."""
    return int(round(min(max(prob * 100, 0), 100)))


# ════════════════════════════════════════════════════════════════
# Batch prediction — uses predict_batch for efficiency
# ════════════════════════════════════════════════════════════════

def compute_risk_scores_batch(
    model: EnsembleModel,
    feat_df: pd.DataFrame,
) -> np.ndarray:
    """
    Run all engineered feature rows through the model in one shot.
    Returns a 1-D float array of fraud probabilities (same length as feat_df).
    """
    X = feat_df[FEATURE_COLUMNS].values.astype(np.float32)
    return model.predict_batch(X)


# ════════════════════════════════════════════════════════════════
# Main import routine
# ════════════════════════════════════════════════════════════════

def import_transactions(
    csv_path: Path,
    model_dir: Path,
    limit: int | None,
    batch_size: int,
    clear_first: bool,
) -> None:
    # ── 1. Ensure DB tables exist ────────────────────────────────
    print("[DB]    Initialising database tables …")
    init_db()

    # ── 2. Load the trained ensemble ─────────────────────────────
    print(f"[Model] Loading ensemble from {model_dir} …")
    model = EnsembleModel.load(model_dir)

    # ── 3. Read CSV ───────────────────────────────────────────────
    print(f"[CSV]   Reading {csv_path} …")
    raw_df = pd.read_csv(csv_path, nrows=limit)
    total_rows = len(raw_df)
    print(f"[CSV]   {total_rows:,} rows loaded (limit={limit})")

    # ── 4. Engineer features for the whole dataset ────────────────
    print("[Feat]  Engineering features …")
    feat_df = engineer_features(raw_df)

    # ── 5. Score all rows in one vectorised pass ──────────────────
    print("[Model] Running batch prediction …")
    t0 = time.perf_counter()
    probs = compute_risk_scores_batch(model, feat_df)
    elapsed = time.perf_counter() - t0
    print(f"[Model] Scored {total_rows:,} rows in {elapsed:.1f}s  "
          f"({total_rows / elapsed:,.0f} rows/sec)")

    # ── 6. Optionally wipe existing rows ─────────────────────────
    db: Session = SessionLocal()
    try:
        if clear_first:
            deleted = db.query(Transaction).delete()
            db.commit()
            print(f"[DB]    Cleared {deleted:,} existing transaction(s).")

        # ── 7. Build and insert Transaction objects in batches ────
        print(f"[DB]    Inserting {total_rows:,} rows in batches of {batch_size} …")

        # Spread timestamps evenly over the last 30 days so the
        # dashboard's time-series charts look realistic.
        now_utc = datetime.now(timezone.utc)
        start_ts = now_utc - timedelta(days=30)
        ts_delta = timedelta(days=30) / max(total_rows, 1)

        inserted = 0
        batch: list[Transaction] = []

        for i, (raw_row, feat_row, prob) in enumerate(
            zip(raw_df.itertuples(index=False), feat_df.itertuples(index=False), probs)
        ):
            risk_score = prob_to_risk_score(float(prob))
            risk_tier = score_to_risk_tier(risk_score)
            timestamp = start_ts + ts_delta * i

            txn = Transaction(
                step=int(raw_row.step),
                type=str(raw_row.type),
                amount=float(raw_row.amount),
                nameOrig=str(raw_row.nameOrig),
                oldbalanceOrg=float(raw_row.oldbalanceOrg),
                newbalanceOrig=float(raw_row.newbalanceOrig),
                nameDest=str(raw_row.nameDest),
                oldbalanceDest=float(raw_row.oldbalanceDest),
                newbalanceDest=float(raw_row.newbalanceDest),
                isFraud=int(raw_row.isFraud),
                isFlaggedFraud=int(raw_row.isFlaggedFraud),
                risk_score=risk_score,
                risk_tier=risk_tier,
                timestamp=timestamp,
            )
            batch.append(txn)

            if len(batch) >= batch_size:
                db.bulk_save_objects(batch)
                db.commit()
                inserted += len(batch)
                batch = []
                pct = inserted / total_rows * 100
                print(f"  … {inserted:,}/{total_rows:,} ({pct:.1f}%)", end="\r")

        # Flush remaining rows
        if batch:
            db.bulk_save_objects(batch)
            db.commit()
            inserted += len(batch)

        print(f"\n[DB]    OK Inserted {inserted:,} transactions successfully.")

    except Exception as exc:
        db.rollback()
        print(f"\n[ERROR] Import failed: {exc}", file=sys.stderr)
        raise
    finally:
        db.close()

    # ── 8. Summary ────────────────────────────────────────────────
    fraud_count = int((probs >= 0.5).sum())  # noqa: E501
    print("\n-- Import Summary -------------------------------------------")
    print(f"  Total rows imported : {total_rows:,}")
    print(f"  Fraud (prob >= 0.50): {fraud_count:,}  "
          f"({fraud_count / total_rows * 100:.1f}%)")
    print(f"  Avg risk score      : {probs.mean() * 100:.1f}")
    print(f"  Max risk score      : {probs.max() * 100:.0f}")
    print("-------------------------------------------------------------")
    print("Dashboard should now show transactions. Refresh the UI.")


# ════════════════════════════════════════════════════════════════
# CLI entry point
# ════════════════════════════════════════════════════════════════

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import dataset.csv transactions into PostgreSQL with fraud risk scores",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--csv", type=Path, default=_DEFAULT_CSV,
        help="Path to the PaySim CSV file",
    )
    parser.add_argument(
        "--model-dir", type=Path, default=_DEFAULT_MODEL_DIR,
        help="Directory containing saved model files",
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Maximum number of rows to import (default: all)",
    )
    parser.add_argument(
        "--batch-size", type=int, default=1000,
        help="Number of rows per DB commit",
    )
    parser.add_argument(
        "--clear", action="store_true",
        help="Delete all existing transactions before importing",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    import_transactions(
        csv_path=args.csv,
        model_dir=args.model_dir,
        limit=args.limit,
        batch_size=args.batch_size,
        clear_first=args.clear,
    )
