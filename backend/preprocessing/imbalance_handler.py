"""
Imbalance Handler Module
════════════════════════
Addresses extreme class imbalance in the PaySim dataset
(fraud ≈ 0.13 % of transactions) using two complementary strategies:

1. **SMOTE** — Synthetic Minority Over-sampling Technique
   Generates synthetic fraud samples so the minority class is better
   represented during training.

2. **Class weighting** — Computes sample weights inversely proportional
   to class frequency, passed directly to the tree-based learners
   via `scale_pos_weight` / `class_weight`.
"""

from __future__ import annotations

import numpy as np
from imblearn.over_sampling import SMOTE
from sklearn.utils.class_weight import compute_class_weight, compute_sample_weight


# ═══════════════════════════════════════════════════════════════
# SMOTE resampling
# ═══════════════════════════════════════════════════════════════

def apply_smote(
    X: np.ndarray,
    y: np.ndarray,
    sampling_strategy: float = 0.3,
    random_state: int = 42,
    k_neighbors: int = 5,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Apply SMOTE to oversample the minority (fraud) class.

    Parameters
    ──────────
    X               : feature matrix  (n_samples, n_features)
    y               : binary labels   (0 = legit, 1 = fraud)
    sampling_strategy: desired ratio of minority / majority after resampling.
                       0.3 means 30 % as many fraud samples as legit.
    random_state    : reproducibility seed
    k_neighbors     : SMOTE neighbour count

    Returns
    ───────
    (X_resampled, y_resampled)
    """
    smote = SMOTE(
        sampling_strategy=sampling_strategy,
        random_state=random_state,
        k_neighbors=k_neighbors,
    )
    X_res, y_res = smote.fit_resample(X, y)

    n_before = int(np.sum(y == 1))
    n_after = int(np.sum(y_res == 1))
    print(
        f"[SMOTE] Fraud samples: {n_before:,} -> {n_after:,}  "
        f"(total rows: {len(y):,} -> {len(y_res):,})"
    )
    return X_res, y_res


# ═══════════════════════════════════════════════════════════════
# Class weight computation
# ═══════════════════════════════════════════════════════════════

def compute_class_weights(y: np.ndarray) -> dict[int, float]:
    """
    Compute balanced class weights using sklearn.

    Returns a dict like {0: 0.51, 1: 385.2} that can be fed
    directly to RandomForest's `class_weight` parameter.
    """
    classes = np.array([0, 1])
    weights = compute_class_weight("balanced", classes=classes, y=y)
    weight_dict = {int(c): float(w) for c, w in zip(classes, weights)}
    print(f"[ClassWeights] {weight_dict}")
    return weight_dict


def compute_xgb_scale_pos_weight(y: np.ndarray) -> float:
    """
    Compute XGBoost's `scale_pos_weight` parameter.

    Formula: count(negative) / count(positive)
    """
    n_pos = int(np.sum(y == 1))
    n_neg = int(np.sum(y == 0))
    ratio = n_neg / max(n_pos, 1)
    print(f"[XGBoost scale_pos_weight] {ratio:.2f}  (neg={n_neg:,}, pos={n_pos:,})")
    return ratio


def compute_sample_weights(y: np.ndarray) -> np.ndarray:
    """
    Per-sample weights (balanced). Useful for models that accept
    a `sample_weight` parameter during fit.
    """
    return compute_sample_weight("balanced", y)


# ═══════════════════════════════════════════════════════════════
# Combined strategy dispatcher
# ═══════════════════════════════════════════════════════════════

def get_balanced_data(
    X: np.ndarray,
    y: np.ndarray,
    method: str = "smote",
    smote_ratio: float = 0.3,
    random_state: int = 42,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Dispatcher — choose a resampling strategy by name.

    Parameters
    ──────────
    method : "smote" | "weights_only" | "undersample"
        • "smote"        → apply SMOTE oversampling
        • "weights_only" → return data unchanged (caller uses class weights)
        • "undersample"  → random majority undersampling

    Returns
    ───────
    (X_balanced, y_balanced)
    """
    if method == "smote":
        return apply_smote(X, y, sampling_strategy=smote_ratio,
                           random_state=random_state)

    if method == "undersample":
        return _undersample_majority(X, y, random_state=random_state)

    # "weights_only" — no resampling, weights are applied at model level
    return X, y


def _undersample_majority(
    X: np.ndarray,
    y: np.ndarray,
    random_state: int = 42,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Randomly undersample the majority class to match the minority.
    Preserves all minority samples.
    """
    rng = np.random.RandomState(random_state)

    minority_idx = np.where(y == 1)[0]
    majority_idx = np.where(y == 0)[0]

    # Sample majority down to same count as minority
    chosen = rng.choice(majority_idx, size=len(minority_idx), replace=False)
    idx = np.concatenate([minority_idx, chosen])
    rng.shuffle(idx)

    print(
        f"[Undersample] Majority {len(majority_idx):,} -> {len(chosen):,}  "
        f"(total rows: {len(y):,} -> {len(idx):,})"
    )
    return X[idx], y[idx]
