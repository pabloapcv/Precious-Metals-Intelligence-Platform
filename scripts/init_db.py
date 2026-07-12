#!/usr/bin/env python3
"""Initialize database schema."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pmip.config import get_settings
from pmip.db.models import Base
from pmip.db.session import get_engine


def main():
  settings = get_settings()
  if settings.database_url.startswith("sqlite"):
    db_path = settings.database_url.replace("sqlite:///", "")
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

  engine = get_engine()
  if "--fresh" in sys.argv:
    Base.metadata.drop_all(bind=engine)
  Base.metadata.create_all(bind=engine)
  print(f"Database schema created: {settings.database_url}")


if __name__ == "__main__":
  main()
