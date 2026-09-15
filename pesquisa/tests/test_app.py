import csv
import io
import json
import re
import sqlite3
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pyotp
import pytest
from cryptography.fernet import Fernet

from app import create_app
from manage import erase, provision, restore, erasures_path
from storage import backup, connect, migrate

PASSWORD = "test-only-password-with-32-chars"
OTP_SECRET = "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP"


@pytest.fixture
def app(tmp_path):
    config = {"TESTING": True, "SECRET_KEY": "local-test-secret-32-characters-only", "ENCRYPTION_KEY": Fernet.generate_key(),
              "DATABASE": str(tmp_path / "responses.sqlite3"), "ORIGIN": "http://localhost", "SESSION_COOKIE_SECURE": False, "MIN_FORM_SECONDS": 0}
    application = create_app(config)
    provision(config["DATABASE"], config["ENCRYPTION_KEY"], "admin", PASSWORD, OTP_SECRET)
    erasures_path(config["DATABASE"]).touch()
    return application


def form_payload(client, **changes):
    html = client.get("/").get_data(as_text=True)
    csrf = re.search(r'name="csrf-token" content="([^"]+)"', html)[1]
    payload = {"submission_key": str(uuid.uuid4()), "form_token": re.search(r'data-token="([^"]+)"', html)[1],
               "stage": "s12", "area": "personal", "format": "short", "gaps": ["training", "sales"],
               "wish": "Quero aprender a planejar uma aula com segurança.", "name": "Pessoa de teste",
               "email": "sintetico@example.com", "phone": "61999999999", "research_consent": True,
               "contact_consent": False}
    payload.update(changes)
    return payload, {"X-CSRFToken": csrf, "Origin": "http://localhost"}


def login(client, code=None, password=PASSWORD):
    html = client.get("/login").get_data(as_text=True)
    csrf = re.search(r'name="csrf_token" value="([^"]+)"', html)[1]
    return client.post("/login", data={"csrf_token": csrf, "username": "admin", "password": password, "code": code or pyotp.TOTP(OTP_SECRET).now()})


def submit(client, **changes):
    payload, headers = form_payload(client, **changes)
    result = client.post("/api/responses", json=payload, headers=headers)
    assert result.status_code == 201, result.get_data(as_text=True)
    return result.json["id"]


def test_complete_flow_persistent_encrypted_and_exported(app):
    client = app.test_client()
    identifier = submit(client, contact_consent=True, wish="=HYPERLINK(\"https://invalid.example\")")
    assert login(client).status_code == 303
    result = client.get("/api/admin/analytics").json
    assert (result["total"], result["total_all"], result["contact_consent"]) == (1, 1, 1)
    rows = client.get("/api/admin/responses").json["rows"]
    assert rows[0]["id"] == identifier and rows[0]["email"] == "sintetico@example.com"
    csv_rows = list(csv.reader(io.StringIO(client.get("/api/admin/export.csv").get_data(as_text=True).lstrip("\ufeff")), delimiter=";"))
    assert len(csv_rows) == 2 and csv_rows[1][6].startswith("'=HYPERLINK")
    assert csv_rows[1][10] == "Sim"
    for file in Path(app.config["DATABASE"]).parent.glob("*.sqlite3*"):
        assert b"sintetico@example.com" not in file.read_bytes()
        assert b"HYPERLINK" not in file.read_bytes()
    restarted = create_app(dict(app.config))
    with connect(restarted.config["DATABASE"]) as db:
        assert db.execute("SELECT COUNT(*) FROM responses").fetchone()[0] == 1


@pytest.mark.parametrize("changes", [
    {"stage": "x' OR 1=1 --"}, {"area": []}, {"format": "invalid"},
    {"gaps": []}, {"gaps": ["training", "sales", "service"]},
    {"gaps": ["all", "sales"]}, {"gaps": ["sales", "sales"]}, {"gaps": [None]},
    {"wish": ""}, {"wish": "x"*2001}, {"wish": None},
    {"email": "bad"}, {"phone": "123"}, {"phone": "61999999999<script>"},
    {"research_consent": False}, {"research_consent": "true"},
    {"contact_consent": "true"}, {"contact_consent": True, "email": "", "phone": ""},
    {"name": "x"*101}, {"submission_key": "invalid"}, {"website": "spam"},
])
def test_server_rejects_invalid_data_without_writing(app, changes):
    client=app.test_client()
    payload, headers = form_payload(client, **changes)
    assert client.post("/api/responses", json=payload, headers=headers).status_code == 422
    with connect(app.config["DATABASE"]) as db:
        assert db.execute("SELECT COUNT(*) FROM responses").fetchone()[0] == 0


def test_optional_identity_and_exclusive_general_gap(app):
    client = app.test_client()
    submit(client, name="", email="", phone="", gaps=["all"])
    assert login(client).status_code == 303
    assert client.get("/api/admin/responses").json["rows"][0]["name"] == ""


def test_anonymous_access_cannot_read_data_or_files(app):
    client = app.test_client()
    submit(client)
    for path in ("/api/admin/responses", "/api/admin/analytics", "/api/admin/export.csv"):
        result=client.get(path)
        assert result.status_code == 401
        assert "sintetico@example.com" not in result.get_data(as_text=True)
    assert client.get("/admin").status_code == 302
    for path in ("/.env", "/responses.sqlite3", "/data/responses.sqlite3", "/static/../app.py", "/backups/"):
        assert client.get(path).status_code == 404


def test_csrf_origin_host_body_limits_and_signed_form(app):
    client = app.test_client()
    payload, headers = form_payload(client)
    assert client.post("/api/responses", json=payload).status_code == 400
    assert client.post("/api/responses", json=payload, headers={**headers, "Origin": "https://hostile.example"}).status_code == 403
    assert client.get("/", headers={"Host": "hostile.example"}).status_code == 400
    assert client.post("/api/responses", json={**payload,"wish":"x"*20000},headers=headers).status_code == 413
    assert client.post("/api/responses",json={**payload,"form_token":"forged"},headers=headers).status_code == 400


def test_idempotency_sequential_and_concurrent(app):
    client=app.test_client()
    payload, headers=form_payload(client)
    first=client.post("/api/responses",json=payload,headers=headers)
    assert first.status_code==201
    assert client.post("/api/responses",json=payload,headers=headers).json["id"]==first.json["id"]
    assert client.post("/api/responses",json={**payload,"wish":"Outra resposta"},headers=headers).status_code==409
    cookie=client.get_cookie("ifp_session").value
    second={**payload,"submission_key":str(uuid.uuid4())}
    def send(_):
        other=app.test_client();other.set_cookie("ifp_session",cookie)
        return other.post("/api/responses",json=second,headers=headers).status_code
    with ThreadPoolExecutor(max_workers=8) as pool:
        statuses=list(pool.map(send,range(12)))
    assert statuses.count(201)==1 and statuses.count(200)==11
    with connect(app.config["DATABASE"]) as db:
        assert db.execute("SELECT COUNT(*) FROM responses").fetchone()[0]==2
        assert db.execute("SELECT COUNT(*) FROM response_gaps").fetchone()[0]==4


def test_mfa_wrong_password_replay_logout_and_expiration(app):
    first=app.test_client()
    assert login(first, password="incorrect").status_code==401
    assert login(first,code="bad").status_code==401
    assert login(first).status_code==303
    second=app.test_client()
    assert login(second).status_code==401
    cookie=first.get_cookie("ifp_session").value
    csrf=re.search(r'name="csrf-token" content="([^"]+)"',first.get("/admin").get_data(as_text=True))[1]
    assert first.post("/logout",headers={"X-CSRFToken":csrf}).status_code==303
    first.set_cookie("ifp_session",cookie)
    assert first.get("/api/admin/responses").status_code==401


def test_login_rate_limit_survives_app_restart(app):
    client=app.test_client()
    for _ in range(5):assert login(client,password="bad").status_code==401
    again=create_app(dict(app.config)).test_client()
    assert login(again,password="bad").status_code==429


def test_session_expiry(app):
    client=app.test_client();assert login(client).status_code==303
    with connect(app.config["DATABASE"]) as db, db:db.execute("UPDATE admin_sessions SET expires_at=0")
    assert client.get("/api/admin/analytics").status_code==401


def test_filters_percentages_crosstab_timezone_and_pagination(app):
    client=app.test_client()
    a=submit(client,gaps=["training"],format="short",stage="s12")
    b=submit(client,gaps=["sales","training"],format="online",stage="s34")
    with connect(app.config["DATABASE"]) as db, db:
        db.execute("UPDATE responses SET created_at=? WHERE id=?",("2026-09-15T02:59:59.000000+00:00",a))
        db.execute("UPDATE responses SET created_at=? WHERE id=?",("2026-09-15T03:00:00.000000+00:00",b))
    assert login(client).status_code==303
    all_data=client.get("/api/admin/analytics").json
    assert all_data["total"]==2
    gaps={x["code"]:x for x in all_data["groups"]["gaps"]}
    assert gaps["training"]["percent"]==100 and gaps["sales"]["percent"]==50
    assert all_data["days"][-1]["cumulative"]==2
    assert len(all_data["cross"])==2
    assert client.get("/api/admin/analytics?from=2026-09-15&to=2026-09-15").json["total"]==1
    assert client.get("/api/admin/analytics?stage=s12").json["total"]==1
    assert client.get("/api/admin/responses?stage=s34").json["rows"][0]["id"]==b
    for query in ("stage=bad", "from=bad", "from=2026-09-20&to=2026-09-10"):
        assert client.get("/api/admin/analytics?"+query).status_code==400
    assert client.get("/api/admin/responses?page=bad").status_code==400
    for i in range(25):submit(client,email=f"test{i}@example.com")
    assert len(client.get("/api/admin/responses?page=1").json["rows"])==25
    assert len(client.get("/api/admin/responses?page=2").json["rows"])==2


def test_empty_analytics_does_not_invent_insights(app):
    client=app.test_client();assert login(client).status_code==303
    data=client.get("/api/admin/analytics").json
    assert data["total"]==0 and data["days"]==[] and data["insights"]==[]


def test_backup_restore_erase_and_migration_invariants(app,tmp_path):
    client=app.test_client();identifier=submit(client)
    snapshot=backup(app.config["DATABASE"],tmp_path/"backup.sqlite3")
    submit(client,stage="s34")
    migrate(app.config["DATABASE"])
    erase(app.config["DATABASE"],identifier)
    restored=tmp_path/"restored.sqlite3"
    restore(snapshot,restored,erasures_path(app.config["DATABASE"]))
    with connect(restored) as db:
        assert db.execute("SELECT COUNT(*) FROM responses").fetchone()[0]==0
        assert db.execute("SELECT COUNT(*) FROM response_gaps").fetchone()[0]==0
        assert not db.execute("PRAGMA foreign_key_check").fetchall()
    with connect(app.config["DATABASE"]) as db:
        assert db.execute("SELECT COUNT(*) FROM responses").fetchone()[0]==1
        assert db.execute("SELECT COUNT(*) FROM schema_version").fetchone()[0]==1
    with pytest.raises(FileExistsError):backup(snapshot,restored)
    with pytest.raises(ValueError):restore(snapshot,tmp_path/"unsafe.sqlite3",tmp_path/"missing.jsonl")


def test_database_constraints_and_transaction_rollback(app):
    client=app.test_client();identifier=submit(client)
    with pytest.raises(sqlite3.IntegrityError):
        with connect(app.config["DATABASE"]) as db,db:db.execute("INSERT INTO response_gaps VALUES(?,?)",(identifier,"service"))
    with pytest.raises(sqlite3.IntegrityError):
        with connect(app.config["DATABASE"]) as db,db:db.execute("UPDATE responses SET stage='invalid' WHERE id=?",(identifier,))
    with connect(app.config["DATABASE"]) as db:
        assert db.execute("SELECT COUNT(*) FROM response_gaps").fetchone()[0]==2


def test_security_headers_and_no_external_trackers(app):
    client=app.test_client();response=client.get("/")
    assert "script-src 'self'" in response.headers["Content-Security-Policy"]
    assert response.headers["X-Frame-Options"]=="DENY"
    assert response.headers["Cache-Control"]=="no-store"
    assert "HttpOnly" in response.headers["Set-Cookie"] and "SameSite=Lax" in response.headers["Set-Cookie"]
    assert 'src="http' not in response.get_data(as_text=True)
    prod=create_app({**dict(app.config),"ORIGIN":"https://survey.example","SESSION_COOKIE_SECURE":True})
    response=prod.test_client().get("/",base_url="https://survey.example")
    assert "Secure" in response.headers["Set-Cookie"]
    assert response.headers["Strict-Transport-Security"]=="max-age=31536000"
