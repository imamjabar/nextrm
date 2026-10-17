#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'services/api')]

from app.core.database import SessionLocal
from app.services.market_feed import fetch_market_snapshot, format_market_note, sync_market_note_to_db


def main():
    parser = argparse.ArgumentParser(description="Sync real market snapshot into NextRM Knowledge Base")
    parser.add_argument("--tenant", default="demo-bank", help="Tenant ID to update")
    parser.add_argument("--session", choices=["auto", "open", "close"], default="auto", help="Market session (open/close)")
    parser.add_argument("--dry-run", action="store_true", help="Print note without writing to DB")
    args = parser.parse_args()

    snapshot = fetch_market_snapshot(args.session)
    note = format_market_note(snapshot)

    if args.dry_run:
        print("=== DRY RUN: Market Note Content ===")
        print(note)
        return

    with SessionLocal() as db:
        source = sync_market_note_to_db(db, tenant_id=args.tenant, snapshot=snapshot)
        print(f"Updated {source.id} (v{source.version}) for tenant '{args.tenant}' [hash: {source.content_hash[:12]}]")


if __name__ == "__main__":
    main()
