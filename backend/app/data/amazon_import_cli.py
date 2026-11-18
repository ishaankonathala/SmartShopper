"""CLI for dry-running or importing the Amazon Discover catalogue."""

from __future__ import annotations

import argparse
from decimal import Decimal, InvalidOperation
from pathlib import Path

from app.services.amazon_catalogue_import import (
    DEFAULT_IMPORT_LIMIT,
    DEFAULT_USD_TO_INR_RATE,
    import_selected_records,
    read_parquet_records,
    select_import_records,
)

DEFAULT_DATASET_PATH = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "amazon_reviews"
    / "electronics.parquet"
)


def _positive_decimal(value: str) -> Decimal:
    try:
        parsed = Decimal(value)
    except InvalidOperation as error:
        raise argparse.ArgumentTypeError("must be a positive decimal") from error
    if not parsed.is_finite() or parsed <= 0:
        raise argparse.ArgumentTypeError("must be a positive decimal")
    return parsed


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_DATASET_PATH)
    parser.add_argument("--limit", type=int, default=DEFAULT_IMPORT_LIMIT)
    parser.add_argument(
        "--usd-to-inr",
        type=_positive_decimal,
        default=DEFAULT_USD_TO_INR_RATE,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Select and report products without writing to the database.",
    )
    return parser


def main() -> None:
    args = _parser().parse_args()
    if args.limit < 1:
        raise SystemExit("--limit must be positive")

    selection = select_import_records(
        read_parquet_records(args.source),
        limit=args.limit,
        usd_to_inr_rate=args.usd_to_inr,
    )
    print(f"Source records scanned: {selection.source_count}")
    print(f"Quality candidates: {selection.candidate_count}")
    print(f"Selected: {len(selection.selected)}")
    print("Selected by category:")
    for category, count in selection.selected_by_category.items():
        print(f"  {category}: {count}")
    print("Rejected by reason:")
    for reason, count in sorted(selection.rejected_by_reason.items()):
        print(f"  {reason}: {count}")

    if args.dry_run:
        print("Dry run: database unchanged.")
        return

    from app.database.session import SessionLocal

    with SessionLocal() as db:
        result = import_selected_records(db, selection.selected)
    print(
        f"Inserted {result.inserted_count}; "
        f"already present {result.already_present_count}."
    )
    print("Inserted by category:")
    for category, count in result.inserted_by_category.items():
        print(f"  {category}: {count}")


if __name__ == "__main__":
    main()
