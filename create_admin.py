import getpass

from app import models, security
from app.database import Base, SessionLocal, engine

Base.metadata.create_all(bind=engine)


def main():
    name = input("Name: ").strip() or "Admin"
    email = input("Email: ").strip().lower()
    password = getpass.getpass("Password (min 8 characters): ")

    if not email or len(password) < 8:
        print("Email is required and password must be at least 8 characters.")
        return

    db = SessionLocal()
    try:
        user = db.query(models.User).filter(models.User.email == email).first()
        if user:
            user.role = "admin"
            print(f"Existing user {email} promoted to admin (password unchanged).")
        else:
            db.add(
                models.User(
                    name=name,
                    email=email,
                    password_hash=security.hash_password(password),
                    role="admin",
                )
            )
            print(f"Admin {email} created.")
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main()