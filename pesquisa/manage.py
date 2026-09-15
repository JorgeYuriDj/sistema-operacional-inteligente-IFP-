"""Operações locais. Não imprime senhas, contatos ou respostas."""
import argparse
import json
import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pyotp
from cryptography.fernet import Fernet
from werkzeug.security import generate_password_hash

from storage import backup, connect, migrate


def provision(database, key, username, password, totp_secret):
    if len(password) < 16:
        raise ValueError("Use uma senha de pelo menos 16 caracteres.")
    migrate(database)
    with connect(database) as conn, conn:
        conn.execute("INSERT INTO administrators(username,password_hash,totp_encrypted) VALUES(?,?,?)",
                     (username, generate_password_hash(password, method="scrypt"), Fernet(key).encrypt(totp_secret.encode()).decode()))


def erasures_path(database):
    return Path(database).parent / "erasures.jsonl"


def erase(database, identifier):
    with connect(database) as conn:
        if not conn.execute("SELECT 1 FROM responses WHERE id=?", (identifier,)).fetchone():
            raise ValueError("Protocolo não encontrado.")
    timestamp = datetime.now(timezone.utc).isoformat()
    with erasures_path(database).open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({"id": identifier, "at": timestamp}) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    with connect(database) as conn, conn:
        conn.execute("DELETE FROM responses WHERE id=?", (identifier,))
        conn.execute("INSERT INTO audit_events(created_at,action,record_id,actor) VALUES(?,?,?,?)", (timestamp, "response_erased", identifier, "operator"))


def restore(source, destination, erasures):
    if not Path(erasures).is_file():
        raise ValueError("Registro atual de exclusões é obrigatório para restaurar.")
    backup(source, destination)
    identifiers = [json.loads(line)["id"] for line in Path(erasures).read_text(encoding="utf-8").splitlines() if line.strip()]
    with connect(destination) as conn, conn:
        conn.executemany("DELETE FROM responses WHERE id=?", [(identifier,) for identifier in identifiers])
        conn.execute("DELETE FROM admin_sessions")
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    return len(identifiers)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["provision", "backup", "restore", "erase", "check"])
    parser.add_argument("--destination")
    parser.add_argument("--source")
    parser.add_argument("--erasures")
    parser.add_argument("--id")
    parser.add_argument("--confirm-id")
    args = parser.parse_args()
    database = os.environ["IFP_DATABASE"]
    if args.action == "provision":
        provision(database, os.environ["IFP_ENCRYPTION_KEY"], os.environ["IFP_ADMIN_USERNAME"], os.environ["IFP_ADMIN_PASSWORD"], os.environ["IFP_ADMIN_TOTP"])
        erasures_path(database).touch(exist_ok=True)
        print("Administrador criado.")
    elif args.action == "backup":
        directory = Path(args.destination or "/backups")
        directory.mkdir(parents=True, exist_ok=True)
        name = datetime.now(timezone.utc).strftime("ifp-%Y%m%dT%H%M%S%f.sqlite3")
        path = backup(database, directory / name)
        os.chmod(path, 0o600)
        cutoff = datetime.now(timezone.utc).timestamp() - 30*86400
        for old in directory.glob("ifp-*.sqlite3"):
            if old.is_file() and old.stat().st_mtime < cutoff:
                old.unlink()
        print("Backup consistente concluído.")
    elif args.action == "restore":
        if not (args.source and args.destination and args.erasures):
            parser.error("Informe origem, destino novo e registro atual de exclusões.")
        restore(args.source, args.destination, args.erasures)
        print("Cópia restaurada e exclusões reaplicadas. Não substitui o banco ativo.")
    elif args.action == "erase":
        if not args.id or args.id != args.confirm_id:
            parser.error("Repita o protocolo em --confirm-id para confirmar a exclusão solicitada.")
        erase(database, args.id)
        print("Resposta excluída; solicitação registrada para futuras restaurações.")
    else:
        with connect(database) as conn:
            assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            assert not conn.execute("PRAGMA foreign_key_check").fetchall()
            print(json.dumps({"integrity": "ok", "responses": conn.execute("SELECT COUNT(*) FROM responses").fetchone()[0], "schema": conn.execute("SELECT MAX(version) FROM schema_version").fetchone()[0]}))


if __name__ == "__main__":
    main()
