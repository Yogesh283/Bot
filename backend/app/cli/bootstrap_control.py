"""Create one admin-panel account. This does not change a trading user."""

from __future__ import annotations

import argparse
import sys

from app.core.security import AuthError
from app.database import SessionLocal
from app.services.control_auth import create_control_admin


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create a separate admin-panel login. This is a local command, not an API.")
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--confirm", action="store_true")
    args = parser.parse_args(argv)
    if not args.confirm:
        print("Refused. Re-run with --confirm.", file=sys.stderr)
        return 4
    db = SessionLocal()
    try:
        create_control_admin(db, args.username, args.password)
        db.commit()
    except AuthError as exc:
        db.rollback()
        print(exc.detail, file=sys.stderr)
        return 2
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    print("Admin panel account is ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
