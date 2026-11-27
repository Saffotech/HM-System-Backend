"""Copy legal files into private storage. Does not run automatically.

Usage (against a database you choose, never implied production):
  python scripts/migrate_legal_uploads.py --dry-run
"""
import argparse
import hashlib
import shutil
from pathlib import Path

from config import settings
from database import SessionLocal
from Models.legal_case import LegalDocument
from client_documents.Services.document_storage_service import private_root


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    root = private_root()
    db = SessionLocal()
    try:
        rows = db.query(LegalDocument).all()
        for row in rows:
            source = Path(row.stored_path)
            if not source.is_file():
                print(f"missing {row.id}")
                continue
            if root in source.resolve().parents:
                continue
            destination = root / source.name
            if args.dry_run:
                print(f"would copy {row.id} -> {destination}")
                continue
            shutil.copy2(source, destination)
            if _digest(source) != _digest(destination):
                raise SystemExit(f"integrity failed for {row.id}")
            row.stored_path = str(destination)
        if not args.dry_run:
            db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main()
