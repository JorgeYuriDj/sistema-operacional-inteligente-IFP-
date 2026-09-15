import sqlite3
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def connect(path):
    db = sqlite3.connect(str(path), timeout=15)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA busy_timeout=15000")
    db.execute("PRAGMA synchronous=FULL")
    try:
        yield db
    finally:
        db.close()


def migrate(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with connect(path) as db:
        db.execute("PRAGMA journal_mode=WAL")
        db.executescript((Path(__file__).parent / "migrations/001_initial.sql").read_text(encoding="utf-8"))


def backup(source, destination):
    """Snapshot consistente com escrita concorrente; destino nunca sobrescrito."""
    destination = Path(destination)
    if destination.exists():
        raise FileExistsError(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with connect(source) as db, sqlite3.connect(str(destination)) as target:
        db.backup(target)
        assert target.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert not target.execute("PRAGMA foreign_key_check").fetchall()
    return destination
