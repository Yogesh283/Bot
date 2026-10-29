from __future__ import annotations

import argparse
import sys

from app.database import SessionLocal
from app.services.bootstrap import BootstrapStatus, promote_verified_user


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Promote one existing, email-verified user to administrator. This is a local command, not an API."
    )
    parser.add_argument("--email", required=True, help="Email of an account that has already verified its address.")
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Required. Confirms that you intend to grant administrator access to this email.",
    )
    args = parser.parse_args(argv)
    if not args.confirm:
        print("Refused. Re-run with --confirm after checking the email address.", file=sys.stderr)
        return 4

    db = SessionLocal()
    try:
        status = promote_verified_user(db, args.email)
        if status is BootstrapStatus.not_found:
            print("No account is registered with that email.", file=sys.stderr)
            db.rollback()
            return 2
        if status is BootstrapStatus.not_verified:
            print("That account has not verified its email. Promotion was refused.", file=sys.stderr)
            db.rollback()
            return 3
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    if status is BootstrapStatus.already_admin:
        print("That account is already an administrator.")
        return 0
    print("Administrator access granted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
