"""
ML Model Module — Ensemble Fraud Detector
══════════════════════════════════════════
Trains, persists, loads, and serves predictions from an ensemble of:
  • XGBoost (gradient-boosted trees)
  • Random Forest

The two models are combined via **soft voting** — their predicted
fraud probabilities are averaged to produce a single score.

Persistence
───────────
Models are saved to  backend/saved_models/  as:
  • xgboost_model.json
  • random_forest.joblib
  • ensemble_metadata.json   (training date, metrics, feature list)
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    classification_report,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier

from preprocessing.feature_engineering import (
    FEATURE_COLUMNS,
    engineer_features,
    extract_single_transaction_features,
)
from preprocessing.imbalance_handler import (
    apply_smote,
    compute_class_weights,
    compute_xgb_scale_pos_weight,
)

# ── Paths ───────────────────────────────────────────────────────
_BASE_DIR = Path(__file__).resolve().parent.parent          # backend/
_DATA_PATH = _BASE_DIR / "data" / "dataset.csv"
_MODEL_DIR = _BASE_DIR / "saved_models"


# ═══════════════════════════════════════════════════════════════
# Ensemble model class
# ═══════════════════════════════════════════════════════════════

class EnsembleModel:
    """
    Wraps XGBoost + Random Forest with soft-voting.

    Usage
    ─────
    # Training
    model = EnsembleModel()
    model.train()                      # reads dataset.csv, engineers features, trains
    model.save()                       # persists to disk

    # Inference
    model = EnsembleModel.load()       # loads from disk
    prob  = model.predict(txn_dict)    # returns float 0.0 – 1.0
    """

    def __init__(self):
        self.xgb: XGBClassifier | None = None
        self.rf: RandomForestClassifier | None = None
        self.metadata: dict[str, Any] = {}
        self._is_trained = False

    # ── Training ────────────────────────────────────────────
    def train(
        self,
        csv_path: str | Path | None = None,
        test_size: float = 0.2,
        smote_ratio: float = 0.3,
        xgb_weight: float = 0.6,
        rf_weight: float = 0.4,
        random_state: int = 42,
    ) -> dict[str, Any]:
        """
        End-to-end training pipeline:
        1. Load CSV  →  2. Feature engineering  →  3. SMOTE
        4. Train XGBoost + RF  →  5. Evaluate on held-out test set

        Returns a metrics dictionary.
        """
        csv_path = Path(csv_path) if csv_path else _DATA_PATH
        print(f"[Train] Loading data from {csv_path} ...")
        raw_df = pd.read_csv(csv_path)
        print(f"[Train] Raw rows: {len(raw_df):,}")

        # Feature engineering
        print("[Train] Engineering features ...")
        feat_df = engineer_features(raw_df)
        print(f"[Train] Feature columns: {len(FEATURE_COLUMNS)}")

        X = feat_df[FEATURE_COLUMNS].values.astype(np.float32)
        y = feat_df["isFraud"].values.astype(np.int32)

        # Train / test split (stratified)
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size,
            stratify=y, random_state=random_state,
        )
        print(f"[Train] Split — train: {len(y_train):,}  test: {len(y_test):,}")

        # Handle imbalance with SMOTE on train set only
        print("[Train] Applying SMOTE ...")
        X_train_res, y_train_res = apply_smote(
            X_train, y_train,
            sampling_strategy=smote_ratio,
            random_state=random_state,
        )

        # Class weights for additional model-level balancing
        scale_pos = compute_xgb_scale_pos_weight(y_train)
        class_w = compute_class_weights(y_train)

        # ── XGBoost ─────────────────────────────────────────
        print("[Train] Training XGBoost ...")
        self.xgb = XGBClassifier(
            n_estimators=300,
            max_depth=6,
            learning_rate=0.05,
            scale_pos_weight=scale_pos,
            subsample=0.8,
            colsample_bytree=0.8,
            reg_alpha=0.1,
            reg_lambda=1.0,
            use_label_encoder=False,
            eval_metric="aucpr",
            random_state=random_state,
            n_jobs=-1,
        )
        self.xgb.fit(
            X_train_res, y_train_res,
            eval_set=[(X_test, y_test)],
            verbose=False,
        )

        # ── Random Forest ──────────────────────────────────
        print("[Train] Training Random Forest ...")
        self.rf = RandomForestClassifier(
            n_estimators=200,
            max_depth=12,
            min_samples_split=10,
            min_samples_leaf=4,
            class_weight=class_w,
            random_state=random_state,
            n_jobs=-1,
        )
        self.rf.fit(X_train_res, y_train_res)

        # ── Evaluate ensemble on test set ──────────────────
        print("[Train] Evaluating ensemble ...")
        metrics = self._evaluate(X_test, y_test, xgb_weight, rf_weight)

        # Store metadata
        self.metadata = {
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "dataset": str(csv_path.name),
            "total_rows": int(len(raw_df)),
            "train_rows": int(len(y_train_res)),
            "test_rows": int(len(y_test)),
            "smote_ratio": smote_ratio,
            "xgb_weight": xgb_weight,
            "rf_weight": rf_weight,
            "feature_columns": FEATURE_COLUMNS,
            "metrics": metrics,
        }
        self._is_trained = True
        print("[Train] Done OK")
        return metrics

    # ── Prediction ──────────────────────────────────────────
    def predict(
        self,
        transaction: dict | np.ndarray,
        history_df: pd.DataFrame | None = None,
    ) -> float:
        """
        Predict fraud probability for a single transaction.

        Parameters
        ──────────
        transaction : raw transaction dict (PaySim columns) OR a
                      pre-computed feature vector (np.ndarray).
        history_df  : originator's recent transactions (for velocity
                      features). Ignored if transaction is an ndarray.

        Returns
        ───────
        float in [0.0, 1.0] — probability of fraud.
        """
        if not self._is_trained:
            raise RuntimeError("Model is not trained / loaded. Call train() or load().")

        if isinstance(transaction, dict):
            features = extract_single_transaction_features(transaction, history_df)
        else:
            features = np.asarray(transaction, dtype=np.float64)

        X = features.reshape(1, -1).astype(np.float32)

        xgb_prob = float(self.xgb.predict_proba(X)[0, 1])
        rf_prob = float(self.rf.predict_proba(X)[0, 1])

        xgb_w = self.metadata.get("xgb_weight", 0.6)
        rf_w = self.metadata.get("rf_weight", 0.4)
        combined = xgb_w * xgb_prob + rf_w * rf_prob

        return round(min(max(combined, 0.0), 1.0), 6)

    def predict_batch(self, X: np.ndarray) -> np.ndarray:
        """Predict fraud probabilities for a batch of feature vectors."""
        if not self._is_trained:
            raise RuntimeError("Model is not trained / loaded.")

        X = X.astype(np.float32)
        xgb_probs = self.xgb.predict_proba(X)[:, 1]
        rf_probs = self.rf.predict_proba(X)[:, 1]

        xgb_w = self.metadata.get("xgb_weight", 0.6)
        rf_w = self.metadata.get("rf_weight", 0.4)
        return np.clip(xgb_w * xgb_probs + rf_w * rf_probs, 0.0, 1.0)

    # ── Persistence ─────────────────────────────────────────
    def save(self, model_dir: str | Path | None = None) -> Path:
        """Save both models + metadata to disk."""
        if not self._is_trained:
            raise RuntimeError("Nothing to save — model is not trained.")

        d = Path(model_dir) if model_dir else _MODEL_DIR
        d.mkdir(parents=True, exist_ok=True)

        xgb_path = d / "xgboost_model.json"
        rf_path = d / "random_forest.joblib"
        meta_path = d / "ensemble_metadata.json"

        self.xgb.save_model(str(xgb_path))
        joblib.dump(self.rf, str(rf_path))
        with open(meta_path, "w") as f:
            json.dump(self.metadata, f, indent=2)

        print(f"[Save] Models saved to {d}")
        return d

    @classmethod
    def load(cls, model_dir: str | Path | None = None) -> "EnsembleModel":
        """Load a previously saved ensemble from disk."""
        d = Path(model_dir) if model_dir else _MODEL_DIR

        xgb_path = d / "xgboost_model.json"
        rf_path = d / "random_forest.joblib"
        meta_path = d / "ensemble_metadata.json"

        for p in [xgb_path, rf_path, meta_path]:
            if not p.exists():
                raise FileNotFoundError(f"Missing model file: {p}")

        obj = cls()
        obj.xgb = XGBClassifier()
        obj.xgb.load_model(str(xgb_path))
        obj.rf = joblib.load(str(rf_path))

        with open(meta_path) as f:
            obj.metadata = json.load(f)

        obj._is_trained = True
        print(f"[Load] Ensemble loaded from {d}")
        return obj

    # ── Metadata ────────────────────────────────────────────
    def get_model_metadata(self) -> dict[str, Any]:
        """Return training metadata and evaluation metrics."""
        return self.metadata

    # ── Internal evaluation ─────────────────────────────────
    def _evaluate(
        self,
        X_test: np.ndarray,
        y_test: np.ndarray,
        xgb_weight: float,
        rf_weight: float,
    ) -> dict[str, Any]:
        """Evaluate the ensemble on a test set and return metrics."""
        X_test = X_test.astype(np.float32)

        xgb_probs = self.xgb.predict_proba(X_test)[:, 1]
        rf_probs = self.rf.predict_proba(X_test)[:, 1]
        ensemble_probs = xgb_weight * xgb_probs + rf_weight * rf_probs

        # Threshold at 0.5
        y_pred = (ensemble_probs >= 0.5).astype(int)

        metrics = {
            "roc_auc": round(float(roc_auc_score(y_test, ensemble_probs)), 4),
            "f1": round(float(f1_score(y_test, y_pred)), 4),
            "precision": round(float(precision_score(y_test, y_pred)), 4),
            "recall": round(float(recall_score(y_test, y_pred)), 4),
        }

        # Per-model AUC for comparison
        metrics["xgb_auc"] = round(float(roc_auc_score(y_test, xgb_probs)), 4)
        metrics["rf_auc"] = round(float(roc_auc_score(y_test, rf_probs)), 4)

        print(f"\n{'='*50}")
        print(f"  Ensemble AUC:  {metrics['roc_auc']}")
        print(f"  XGBoost AUC:   {metrics['xgb_auc']}")
        print(f"  RandomForest:  {metrics['rf_auc']}")
        print(f"  F1: {metrics['f1']}  Prec: {metrics['precision']}  Rec: {metrics['recall']}")
        print(f"{'='*50}")
        print(classification_report(y_test, y_pred, target_names=["Legit", "Fraud"]))

        return metrics


# ═══════════════════════════════════════════════════════════════
# Module-level convenience (singleton pattern)
# ═══════════════════════════════════════════════════════════════

_model_instance: EnsembleModel | None = None


def load_model(model_dir: str | Path | None = None) -> EnsembleModel:
    """Load (or return cached) ensemble model singleton."""
    global _model_instance
    if _model_instance is None:
        _model_instance = EnsembleModel.load(model_dir)
    return _model_instance


def predict(transaction: dict, history_df: pd.DataFrame | None = None) -> float:
    """Convenience: predict fraud probability for a single transaction."""
    model = load_model()
    return model.predict(transaction, history_df)


def get_model_metadata() -> dict[str, Any]:
    """Convenience: return metadata of the loaded model."""
    model = load_model()
    return model.get_model_metadata()


# ═══════════════════════════════════════════════════════════════
# CLI entry point — train from command line
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Train fraud detection ensemble")
    parser.add_argument("--csv", type=str, default=None,
                        help="Path to PaySim CSV (default: backend/data/dataset.csv)")
    parser.add_argument("--smote-ratio", type=float, default=0.3)
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument("--output", type=str, default=None,
                        help="Output directory for saved models")
    args = parser.parse_args()

    ensemble = EnsembleModel()
    ensemble.train(
        csv_path=args.csv,
        smote_ratio=args.smote_ratio,
        test_size=args.test_size,
    )
    ensemble.save(model_dir=args.output)
