from passlib.context import CryptContext
from models.db_models import SessionLocal, Admin, init_db

init_db()
pwd = CryptContext(schemes=["bcrypt"])
db = SessionLocal()
db.add(Admin(
    username="admin",
    password_hash=pwd.hash("admin"),
    phone="+910000000000",
    email="admin@example.com",
    role="admin"
))
db.commit()
db.close()
print("Admin seeded successfully")