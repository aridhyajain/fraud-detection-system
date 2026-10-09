import pandas as pd
import numpy as np
import random
from pathlib import Path

def generate_synthetic_paysim(num_samples=10000):
    np.random.seed(42)
    random.seed(42)
    
    steps = np.random.randint(1, 744, num_samples)
    types = np.random.choice(['CASH_IN', 'CASH_OUT', 'DEBIT', 'PAYMENT', 'TRANSFER'], num_samples, p=[0.2, 0.35, 0.05, 0.3, 0.1])
    amounts = np.abs(np.random.lognormal(mean=6, sigma=1.5, size=num_samples))
    
    nameOrig = [f"C{random.randint(100000, 999999)}" for _ in range(num_samples)]
    nameDest = [f"M{random.randint(100000, 999999)}" if t == 'PAYMENT' else f"C{random.randint(100000, 999999)}" for t in types]
    
    oldbalanceOrg = np.abs(np.random.lognormal(mean=6, sigma=1.5, size=num_samples))
    newbalanceOrig = oldbalanceOrg - amounts
    newbalanceOrig = np.where((types == 'CASH_IN'), oldbalanceOrg + amounts, newbalanceOrig)
    newbalanceOrig = np.where(newbalanceOrig < 0, 0, newbalanceOrig)
    
    oldbalanceDest = np.abs(np.random.lognormal(mean=6, sigma=1.5, size=num_samples))
    newbalanceDest = oldbalanceDest + amounts
    newbalanceDest = np.where((types == 'CASH_IN'), oldbalanceDest - amounts, newbalanceDest)
    newbalanceDest = np.where(newbalanceDest < 0, 0, newbalanceDest)
    
    isFraud = np.zeros(num_samples, dtype=int)
    
    # Introduce some logic for fraud
    # Transfer and Cash_out with large amounts
    fraud_candidates = np.where((amounts > 10000) & (np.isin(types, ['TRANSFER', 'CASH_OUT'])))[0]
    
    num_frauds = int(num_samples * 0.05) # 5% fraud for good minority class size
    if len(fraud_candidates) > num_frauds:
        fraud_indices = np.random.choice(fraud_candidates, num_frauds, replace=False)
    else:
        fraud_indices = fraud_candidates
        
    isFraud[fraud_indices] = 1
    
    # Create balance errors for fraud to make the model learn something
    for idx in fraud_indices:
        newbalanceOrig[idx] -= amounts[idx] * np.random.uniform(0.1, 0.5) 
        newbalanceDest[idx] -= amounts[idx] * np.random.uniform(0.1, 0.5)

    df = pd.DataFrame({
        'step': steps,
        'type': types,
        'amount': amounts,
        'nameOrig': nameOrig,
        'oldbalanceOrg': oldbalanceOrg,
        'newbalanceOrig': newbalanceOrig,
        'nameDest': nameDest,
        'oldbalanceDest': oldbalanceDest,
        'newbalanceDest': newbalanceDest,
        'isFraud': isFraud,
        'isFlaggedFraud': 0
    })
    
    return df

if __name__ == '__main__':
    print("Generating synthetic PaySim data...")
    df = generate_synthetic_paysim(50000)
    out_path = Path(__file__).parent / 'dataset.csv'
    df.to_csv(out_path, index=False)
    print(f"Dataset generated at {out_path} with {len(df)} rows. Fraud cases: {df['isFraud'].sum()}")
