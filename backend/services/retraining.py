import pandas as pd
from sqlalchemy.orm import Session
from models.db_models import FraudLabel, Transaction, SessionLocal
import models.ml_model as ml_model
from pathlib import Path

def trigger_retraining_if_needed(background_tasks):
    """
    Checks if there are 50 or more unprocessed labels.
    If so, triggers the retraining background task.
    """
    db = SessionLocal()
    try:
        count = db.query(FraudLabel).filter(FraudLabel.processed == False).count()
        if count >= 50:
            background_tasks.add_task(retrain_model_task)
    finally:
        db.close()

def retrain_model_task():
    """
    Background task to retrain the model with the combined dataset.
    """
    db = SessionLocal()
    try:
        labels = db.query(FraudLabel).filter(FraudLabel.processed == False).all()
        if not labels:
            return
            
        label_dict = {label.transaction_id: label for label in labels}
        txn_ids = list(label_dict.keys())
        
        txns = db.query(Transaction).filter(Transaction.id.in_(txn_ids)).all()
        
        new_data = []
        for txn in txns:
            label = label_dict[txn.id]
            new_data.append({
                "step": txn.step,
                "type": txn.type,
                "amount": txn.amount,
                "nameOrig": txn.nameOrig,
                "oldbalanceOrg": txn.oldbalanceOrg,
                "newbalanceOrig": txn.newbalanceOrig,
                "nameDest": txn.nameDest,
                "oldbalanceDest": txn.oldbalanceDest,
                "newbalanceDest": txn.newbalanceDest,
                "isFraud": 1 if label.is_fraud else 0,
                "isFlaggedFraud": txn.isFlaggedFraud
            })
            
        if not new_data:
            return
            
        new_df = pd.DataFrame(new_data)
        
        # Load original dataset
        base_dir = Path(__file__).resolve().parent.parent
        data_path = base_dir / "data" / "dataset.csv"
        
        if data_path.exists():
            original_df = pd.read_csv(data_path)
            combined_df = pd.concat([original_df, new_df], ignore_index=True)
        else:
            combined_df = new_df
            
        # Overwrite dataset
        combined_df.to_csv(data_path, index=False)
        
        # Trigger retraining
        ensemble = ml_model.EnsembleModel()
        ensemble.train(csv_path=data_path)
        ensemble.save()
        
        # Reload model into memory
        ml_model._model_instance = ensemble
        
        # Mark labels as processed (reset count)
        for label in labels:
            label.processed = True
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Error in retraining task: {e}")
    finally:
        db.close()
