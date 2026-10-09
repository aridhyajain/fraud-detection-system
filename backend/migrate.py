import os
from sqlalchemy import create_engine, text
from config import get_settings

def run_migrations():
    settings = get_settings()
    engine = create_engine(settings.DATABASE_URL)
    
    queries = [
        "ALTER TABLE admins ADD COLUMN IF NOT EXISTS role VARCHAR(20) DEFAULT 'admin';",
        "ALTER TABLE admins ADD COLUMN IF NOT EXISTS account_frozen BOOLEAN DEFAULT FALSE;",
        "ALTER TABLE transactions ADD COLUMN IF NOT EXISTS submitted_by INTEGER REFERENCES admins(id);",
        "ALTER TABLE transactions ADD COLUMN IF NOT EXISTS status VARCHAR(30) DEFAULT 'approved';"
    ]
    
    try:
        with engine.connect() as conn:
            for i, query in enumerate(queries):
                conn.execute(text(query))
                conn.commit()
                print(f"Success: Statement {i + 1} executed.")
        print("All migrations applied successfully.")
    except Exception as e:
        print(f"Error applying migrations: {e}")

if __name__ == "__main__":
    run_migrations()
