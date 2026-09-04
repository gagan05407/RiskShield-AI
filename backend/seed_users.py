import os
import sys

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BACKEND_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from database import init_db, get_user_by_username, create_user
from auth import hash_password

DEFAULT_DEMO_USERS = [
    {
        "username": "admin",
        "email": "admin@riskshield.ai",
        "password": "admin123",
        "role": "admin",
        "full_name": "System Administrator"
    },
    {
        "username": "analyst",
        "email": "analyst@riskshield.ai",
        "password": "analyst123",
        "role": "analyst",
        "full_name": "Lead Fraud Analyst"
    },
    {
        "username": "viewer",
        "email": "viewer@riskshield.ai",
        "password": "viewer123",
        "role": "viewer",
        "full_name": "Audit Viewer"
    }
]

def seed_users():
    """Seeds the SQLite database with default demo accounts if they do not exist."""
    init_db()
    seeded_count = 0
    for user_data in DEFAULT_DEMO_USERS:
        existing = get_user_by_username(user_data["username"])
        if not existing:
            hashed_pwd = hash_password(user_data["password"])
            create_user(
                username=user_data["username"],
                email=user_data["email"],
                hashed_password=hashed_pwd,
                role=user_data["role"],
                full_name=user_data["full_name"],
                status="ACTIVE"
            )
            print(f"[+] Seeded demo user: {user_data['username']} ({user_data['role']} - ACTIVE)")
            seeded_count += 1
        else:
            # Ensure existing demo accounts are active and have current valid password hash
            hashed_pwd = hash_password(user_data["password"])
            from database import get_connection
            conn = get_connection()
            conn.execute("UPDATE users SET status = 'ACTIVE', hashed_password = ? WHERE username = ?", (hashed_pwd, user_data["username"]))
            conn.commit()
            conn.close()
            print(f"[-] Demo user '{user_data['username']}' verified ACTIVE with updated credentials.")
    
    print(f"\nUser seeding complete. Total newly seeded: {seeded_count}")

if __name__ == "__main__":
    seed_users()
