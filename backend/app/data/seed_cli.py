"""CLI entrypoint: python -m app.data.seed_cli

Seeds the demo catalogue into the configured SQLite database.
Safe to run multiple times — does not duplicate SKUs or touch user data.
"""

from app.database.session import SessionLocal
from app.services.seed import seed_products


def main() -> None:
    db = SessionLocal()
    try:
        result = seed_products(db)
        print("Catalogue seed complete (demo/mock data).")
        print(
            f"  inserted={result['inserted']} "
            f"skipped={result['skipped']} "
            f"seed_file={result['total_in_seed_file']}"
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
