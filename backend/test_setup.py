"""Opt-in synthetic smoke check, excluded from pytest discovery."""
__test__ = False

if __name__ == "__main__":
    raise SystemExit("Use scripts/verify_s3_local.py with explicitly disposable services; no application database is seeded here.")
