"""Tao nguoi dung (dung de tao admin dau tien). In token MOT LAN.

  python -m scripts.create_user --email you@example.com --name "Ten" --department admin
"""
import argparse
import sys

from app import access
from app.db import SessionLocal
from app.migrations import init_db
from app.db import engine


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--email", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--department", required=True, choices=access.DEPARTMENTS)
    a = ap.parse_args()
    init_db(engine)
    with SessionLocal() as db:
        if db.query(access.models.User).filter_by(email=a.email.strip().lower()).first():
            print("Email da ton tai.", file=sys.stderr)
            return 1
        user, token = access.create_user(db, a.email, a.name, a.department)
        db.commit()
    print(f"Da tao {user.email} ({user.department}). Token (luu lai, khong hien lai):\n{token}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
