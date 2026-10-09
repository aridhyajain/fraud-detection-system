"""
Train the fraud-detection ensemble model.

Usage
─────
    cd backend
    python train_model.py
    python train_model.py --csv data/dataset.csv --smote-ratio 0.3
"""

import sys
from pathlib import Path

# Ensure backend/ is on sys.path so relative imports work
sys.path.insert(0, str(Path(__file__).resolve().parent))

from models.ml_model import EnsembleModel


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Train fraud detection ensemble")
    parser.add_argument(
        "--csv", type=str, default=None,
        help="Path to PaySim CSV (default: backend/data/dataset.csv)",
    )
    parser.add_argument("--smote-ratio", type=float, default=0.3,
                        help="SMOTE sampling ratio (default: 0.3)")
    parser.add_argument("--test-size", type=float, default=0.2,
                        help="Test split fraction (default: 0.2)")
    parser.add_argument("--output", type=str, default=None,
                        help="Output dir for saved models (default: backend/saved_models/)")
    args = parser.parse_args()

    print("=" * 60)
    print("  Fraud Detection — Model Training")
    print("=" * 60)

    model = EnsembleModel()
    metrics = model.train(
        csv_path=args.csv,
        smote_ratio=args.smote_ratio,
        test_size=args.test_size,
    )
    save_dir = model.save(model_dir=args.output)

    print(f"\n[OK] Model saved to: {save_dir}")
    print(f"  AUC: {metrics['roc_auc']}  |  F1: {metrics['f1']}  |  "
          f"Precision: {metrics['precision']}  |  Recall: {metrics['recall']}")


if __name__ == "__main__":
    main()
