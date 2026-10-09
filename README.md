# Real-Time Fraudulent Transaction Detection System

A comprehensive UPI / bank transfer fraud detection system featuring a robust ML pipeline, role-based access control, and 2FA authentication.

## Tech Stack

* **Frontend:** React 18 + Vite + React Router
* **Backend:** Python 3.11+ / FastAPI
* **Database:** PostgreSQL
* **Auth:** JWT + Gmail SMTP OTP (2FA)
* **ML:** XGBoost + Random Forest ensemble with SMOTE for class imbalance

## Features

### Fraud Detection Pipeline
* **Rule-based Pre-filter:** Flags obvious fraud (e.g. large amount from a new account, unusual hour, many transactions in a short window) and assigns High risk directly, skipping the ML model.
* **ML Ensemble:** XGBoost + Random Forest ensemble with SMOTE handling class imbalance.
* **Risk Scoring:** 
  * **Low (0-40):** Approved automatically.
  * **Medium (41-70):** Triggers email OTP verification flow.
  * **High (71-100):** Blocked and flagged for admin review.
* **Feedback Loop:** Every confirmed fraud / false positive label is logged. The model automatically retrains after 50 new labels.

### User Workflows
* **User Dashboard:** 
  * Send money form (UPI only, amounts restricted to digits).
  * View transaction history.
  * Submissions integrate directly with the fraud pipeline.
* **Email Verification (Medium Risk):** Users must verify transactions using OTP sent via Gmail SMTP.
* **Account Freeze:** Accounts are frozen upon confirmed fraud with automatic email alerts.

### Admin Workflows
* **Admin Dashboard:**
  * Real-time stats cards (Total Today, Blocked Today, Pending OTP, Fraud Rate %).
  * Review "Pending OTP" verification section.
  * Review "Flagged Transactions (Action Required)" section.
  * Actions: Confirm fraud, mark false positive, manually clear OTP.
  * Add User: Create new user accounts via modal.
  * View All Users: Dedicated page with status indicators (Active/Frozen).
* **2FA Login:** Username + Password + Email OTP (via Gmail SMTP).

## Project Structure

```text
fraud-detection/
├── backend/
│   ├── api/
│   │   ├── admin.py
│   │   ├── auth.py
│   │   └── transactions.py
│   ├── data/
│   │   └── generate_dataset.py
│   ├── models/
│   │   ├── db_models.py
│   │   └── ml_model.py
│   ├── preprocessing/
│   │   ├── feature_engineering.py
│   │   └── imbalance_handler.py
│   ├── saved_models/
│   ├── services/
│   │   ├── actions.py
│   │   ├── fraud_detection.py
│   │   ├── retraining.py
│   │   └── risk_scorer.py
│   ├── config.py
│   ├── import_transactions.py
│   ├── main.py
│   ├── migrate.py
│   ├── seed.py
│   └── train_model.py
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── CreateUserModal.jsx
│   │   │   ├── RiskBadge.jsx
│   │   │   └── TransactionTable.jsx
│   │   ├── pages/
│   │   │   ├── Dashboard.jsx
│   │   │   ├── Login.jsx
│   │   │   ├── UserDashboard.jsx
│   │   │   └── UsersPage.jsx
│   │   ├── App.jsx
│   │   └── main.jsx
│   └── package.json
└── README.md
```

## Authentication Flow
1. User/Admin enters Username and Password.
2. System verifies credentials and generates a 6-digit OTP.
3. OTP is sent to the registered email address via Gmail SMTP.
4. User/Admin enters the OTP to complete login and receive their JWT token.

## Getting Started

### Prerequisites
* Python 3.11+
* Node.js 18+
* PostgreSQL
* Gmail Account with an **App Password** configured (for SMTP).

### Backend Setup
1. Navigate to the `backend/` directory:
   ```bash
   cd backend
   ```
2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Create a `.env` file in the `backend/` directory:
   ```env
   DATABASE_URL=postgresql://user:password@localhost/dbname
   JWT_SECRET_KEY=your_jwt_secret_key
   GMAIL_ADDRESS=your.email@gmail.com
   GMAIL_APP_PASSWORD=your_gmail_app_password
   ```
5. Run the database seed script to initialize tables and create an initial admin account:
   ```bash
   python seed.py
   ```
6. Generate the synthetic training dataset (saves to `data/dataset.csv`):
   ```bash
   python data/generate_dataset.py
   ```
7. Train the ML ensemble model (saves to `saved_models/`):
   ```bash
   python train_model.py
   ```
   Optionally, override defaults:
   ```bash
   python train_model.py --csv data/dataset.csv --smote-ratio 0.3 --test-size 0.2
   ```
8. Start the FastAPI server:
   ```bash
   uvicorn main:app --reload
   ```

### Frontend Setup
1. Navigate to the `frontend/` directory:
   ```bash
   cd frontend
   ```
2. Install dependencies:
   ```bash
   npm install
   ```
3. Start the Vite development server:
   ```bash
   npm run dev
   ```

## License
Academic project. All rights reserved.
