import csv
import hashlib
import hmac
import io
import json
import os
import re
import secrets
import time
import uuid
from datetime import datetime, timedelta, timezone
from functools import wraps
from pathlib import Path
from urllib.parse import urlsplit

import pyotp
from cryptography.fernet import Fernet
from flask import Flask, Response, abort, jsonify, redirect, render_template, request, session
from flask_wtf.csrf import CSRFError, CSRFProtect
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from werkzeug.security import check_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix

from storage import connect, migrate
from survey import CONTACT_URL, LABELS, PRIVACY_VERSION, QUESTIONS, VERSION

BRASILIA = timezone(timedelta(hours=-3))


def utcnow():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def create_app(config=None):
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.environ.get("IFP_SECRET_KEY"),
        ENCRYPTION_KEY=os.environ.get("IFP_ENCRYPTION_KEY"),
        DATABASE=os.environ.get("IFP_DATABASE", "/data/responses.sqlite3"),
        ORIGIN=os.environ.get("IFP_ORIGIN", "http://127.0.0.1:8791"),
        SESSION_COOKIE_NAME="ifp_session", SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax", SESSION_COOKIE_SECURE=True,
        PERMANENT_SESSION_LIFETIME=timedelta(hours=8), SESSION_REFRESH_EACH_REQUEST=False,
        MAX_CONTENT_LENGTH=16_384, MAX_FORM_MEMORY_SIZE=16_384, MAX_FORM_PARTS=25,
        WTF_CSRF_TIME_LIMIT=8*3600, MIN_FORM_SECONDS=2,
        TRUST_PROXY=os.environ.get("IFP_TRUST_PROXY") == "1",
    )
    if config:
        app.config.update(config)
    if not app.config["SECRET_KEY"] or len(app.config["SECRET_KEY"]) < 32:
        raise RuntimeError("Configure IFP_SECRET_KEY com pelo menos 32 caracteres.")
    cipher = Fernet(app.config["ENCRYPTION_KEY"])
    signer = URLSafeTimedSerializer(app.config["SECRET_KEY"], salt="ifp-form-v1")
    origin = app.config["ORIGIN"].rstrip("/")
    app.config["TRUSTED_HOSTS"] = [urlsplit(origin).hostname]
    if app.config["TRUST_PROXY"]:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)
    CSRFProtect(app)
    migrate(app.config["DATABASE"])

    def db():
        return connect(app.config["DATABASE"])

    def fail(message, status=400):
        response = jsonify(error=message)
        response.status_code = status
        return response

    def audit(conn, action, record_id=None, actor="public"):
        conn.execute("INSERT INTO audit_events(created_at,action,record_id,actor) VALUES(?,?,?,?)",
                     (utcnow(), action, record_id, actor))

    def limit(scope, maximum, window, identifier=None):
        now = int(time.time())
        subject = identifier if identifier is not None else request.remote_addr or "unknown"
        bucket = hmac.new(app.config["SECRET_KEY"].encode(),
                          f"{scope}:{now // window}:{subject}".encode(), hashlib.sha256).hexdigest()
        with db() as conn, conn:
            conn.execute("DELETE FROM rate_limits WHERE expires_at<?", (now,))
            conn.execute("INSERT INTO rate_limits VALUES(?,1,?) ON CONFLICT(bucket) DO UPDATE SET count=count+1",
                         (bucket, now + window))
            count = conn.execute("SELECT count FROM rate_limits WHERE bucket=?", (bucket,)).fetchone()[0]
        return count <= maximum

    def admin_identity():
        token = session.get("admin_token", "")
        if not isinstance(token, str) or len(token) != 64:
            return None
        with db() as conn:
            row = conn.execute("SELECT username FROM admin_sessions WHERE token_hash=? AND expires_at>?",
                               (hashlib.sha256(token.encode()).hexdigest(), int(time.time()))).fetchone()
        return row["username"] if row else None

    def admin_required(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            if not admin_identity():
                return fail("Entre na administração para acessar estes dados.", 401)
            return fn(*args, **kwargs)
        return wrapped

    @app.before_request
    def require_origin():
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            if request.headers.get("Origin") not in {None, origin}:
                return fail("Origem da solicitação inválida.", 403)
            if request.headers.get("Sec-Fetch-Site") == "cross-site":
                return fail("Solicitação externa recusada.", 403)

    @app.after_request
    def headers(response):
        response.headers.update({
            "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'",
            "X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY",
            "Referrer-Policy": "same-origin", "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
            "Cache-Control": "no-store", "Cross-Origin-Resource-Policy": "same-origin",
        })
        if origin.startswith("https://"):
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        if request.path.startswith(("/admin", "/api/", "/login")):
            response.headers["X-Robots-Tag"] = "noindex, nofollow"
        return response

    @app.errorhandler(CSRFError)
    def csrf_error(_error):
        return fail("Sua sessão expirou. Recarregue a página e tente novamente.", 400)

    @app.errorhandler(413)
    def too_large(_error):
        return fail("O conteúdo excede o tamanho permitido.", 413)

    @app.errorhandler(404)
    def missing(_error):
        return render_template("error.html", message="Esta página não foi encontrada."), 404

    @app.get("/healthz")
    def health():
        with db() as conn:
            conn.execute("SELECT version FROM schema_version WHERE version=1").fetchone()
        return jsonify(status="ok")

    @app.get("/robots.txt")
    def robots():
        return Response("User-agent: *\nDisallow: /admin\nDisallow: /api/\nDisallow: /login\n", mimetype="text/plain")

    @app.get("/")
    def public():
        return render_template("index.html", questions=QUESTIONS, contact=CONTACT_URL,
                               form_token=signer.dumps({"nonce": secrets.token_hex(16)}),
                               submission_key=str(uuid.uuid4()))

    def validate(payload):
        if not isinstance(payload, dict):
            raise ValueError("Envie as respostas no formato esperado.")
        for field in ("stage", "area", "format"):
            if not isinstance(payload.get(field), str) or payload[field] not in LABELS[field]:
                raise ValueError("Responda todas as perguntas de escolha única.")
        gaps = payload.get("gaps")
        if not isinstance(gaps, list) or not 1 <= len(gaps) <= 2:
            raise ValueError("Na pergunta 3, selecione uma ou duas opções.")
        if any(not isinstance(g, str) or g not in LABELS["gaps"] for g in gaps) or len(set(gaps)) != len(gaps):
            raise ValueError("Confira as opções da pergunta 3.")
        if "all" in gaps and len(gaps) > 1:
            raise ValueError("A opção ‘nenhuma dessas áreas’ deve ser marcada sozinha.")
        private = {}
        for field, maximum in (("wish", 2000), ("name", 100), ("email", 254), ("phone", 25)):
            value = payload.get(field, "")
            if not isinstance(value, str) or len(value) > maximum or any(ord(c) < 32 and c not in "\n\r\t" for c in value):
                raise ValueError("Confira o tamanho e os caracteres dos campos de texto.")
            private[field] = value.strip()
        if not 3 <= len(private["wish"]) <= 2000:
            raise ValueError("Conte sua principal dificuldade em 3 a 2.000 caracteres.")
        if private["email"] and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", private["email"]):
            raise ValueError("Confira o endereço de e-mail.")
        if private["phone"] and (not re.fullmatch(r"[+()\d\s.-]+", private["phone"]) or not 10 <= len(re.sub(r"\D", "", private["phone"])) <= 15):
            raise ValueError("Informe um WhatsApp com DDD ou deixe o campo vazio.")
        if payload.get("research_consent") is not True:
            raise ValueError("É necessário concordar com o uso das respostas para participar.")
        contact = payload.get("contact_consent", False)
        if not isinstance(contact, bool):
            raise ValueError("Confira sua preferência de contato.")
        if contact and not (private["email"] or private["phone"]):
            raise ValueError("Para receber contato, informe e-mail ou WhatsApp.")
        if payload.get("website"):
            raise ValueError("Não foi possível validar este envio.")
        try:
            key = str(uuid.UUID(payload.get("submission_key", "")))
        except (ValueError, AttributeError, TypeError):
            raise ValueError("Recarregue a página para iniciar um novo envio.")
        return {"stage": payload["stage"], "area": payload["area"], "format": payload["format"],
                "gaps": sorted(gaps), "private": private, "contact": int(contact), "key": key}

    @app.post("/api/responses")
    def submit():
        if not limit("submission", 60, 3600):
            return fail("Muitos envios desta conexão. Tente novamente mais tarde.", 429)
        payload = request.get_json(silent=True)
        try:
            data = validate(payload)
            _, issued = signer.loads(payload.get("form_token", ""), max_age=86400, return_timestamp=True)
            if time.time() - issued.timestamp() < app.config["MIN_FORM_SECONDS"]:
                return fail("Aguarde alguns segundos e confira suas respostas antes de enviar.", 422)
        except (BadSignature, SignatureExpired, TypeError):
            return fail("O formulário expirou. Recarregue a página antes de enviar.", 400)
        except ValueError as error:
            return fail(str(error), 422)
        encoded = json.dumps(data, ensure_ascii=False, sort_keys=True).encode()
        digest = hmac.new(app.config["SECRET_KEY"].encode(), encoded, hashlib.sha256).hexdigest()
        with db() as conn, conn:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute("SELECT id,payload_hash FROM responses WHERE submission_key=?", (data["key"],)).fetchone()
            if existing:
                if not hmac.compare_digest(existing["payload_hash"], digest):
                    return fail("Este envio já foi registrado com outras respostas. Recarregue para começar outro.", 409)
                return jsonify(id=existing["id"], duplicate=True)
            identifier = str(uuid.uuid4())
            conn.execute("INSERT INTO responses VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (
                identifier, data["key"], digest, utcnow(), VERSION, PRIVACY_VERSION,
                data["stage"], data["area"], data["format"],
                cipher.encrypt(json.dumps(data["private"], ensure_ascii=False).encode()).decode(),
                data["contact"], 1))
            conn.executemany("INSERT INTO response_gaps VALUES(?,?)", [(identifier, g) for g in data["gaps"]])
            audit(conn, "response_created", identifier)
        return jsonify(id=identifier, duplicate=False), 201

    @app.route("/login", methods=["GET", "POST"])
    def login():
        error = None
        if request.method == "POST":
            if not limit("login-ip", 5, 900):
                return render_template("login.html", error="Muitas tentativas. Aguarde 15 minutos para tentar novamente."), 429
            username = request.form.get("username", "").strip().lower()[:100]
            if not limit("login-account", 20, 900, username):
                return render_template("login.html", error="Muitas tentativas para esta conta. Aguarde 15 minutos."), 429
            password = request.form.get("password", "")[:256]
            code = request.form.get("code", "")[:6]
            with db() as conn, conn:
                user = conn.execute("SELECT * FROM administrators WHERE username=?", (username,)).fetchone()
                valid_password = check_password_hash(user["password_hash"], password) if user else check_password_hash(app.config.get("DUMMY_HASH", "scrypt:32768:8:1$invalid$" + "0"*128), password)
                step = int(time.time()) // 30
                valid_step = None
                if user and valid_password and re.fullmatch(r"\d{6}", code):
                    totp = pyotp.TOTP(cipher.decrypt(user["totp_encrypted"].encode()).decode())
                    for candidate in (step, step - 1, step + 1):
                        if candidate > user["last_totp_step"] and hmac.compare_digest(totp.at(candidate * 30), code):
                            valid_step = candidate
                            break
                if valid_step is not None:
                    updated = conn.execute("UPDATE administrators SET last_totp_step=? WHERE username=? AND last_totp_step<?",
                                           (valid_step, username, valid_step)).rowcount
                    if updated:
                        conn.execute("DELETE FROM admin_sessions WHERE expires_at<?", (int(time.time()),))
                        session.clear()
                        token = secrets.token_hex(32)
                        conn.execute("INSERT INTO admin_sessions VALUES(?,?,?)", (hashlib.sha256(token.encode()).hexdigest(), username, int(time.time()) + 8*3600))
                        session["admin_token"] = token
                        session.permanent = True
                        audit(conn, "admin_login", actor=username)
                        return redirect("/admin", code=303)
                audit(conn, "login_failed", actor="unknown")
            error = "Confira o usuário, a senha e o código atual do autenticador."
        return render_template("login.html", error=error), (401 if error else 200)

    @app.post("/logout")
    def logout():
        token = session.get("admin_token", "")
        with db() as conn, conn:
            conn.execute("DELETE FROM admin_sessions WHERE token_hash=?", (hashlib.sha256(token.encode()).hexdigest(),))
        session.clear()
        return redirect("/login", code=303)

    @app.get("/admin")
    def admin():
        if not admin_identity():
            return redirect("/login")
        return render_template("admin.html", questions=QUESTIONS, labels=LABELS)

    def filters():
        clauses, params = [], []
        for field in ("stage", "area", "format"):
            value = request.args.get(field)
            if value:
                if value not in LABELS[field]:
                    abort(400)
                clauses.append(f"r.{field}=?")
                params.append(value)
        dates = {}
        for field in ("from", "to"):
            value = request.args.get(field)
            if value:
                try:
                    parsed = datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=BRASILIA)
                except ValueError:
                    abort(400)
                dates[field] = parsed
                clauses.append("r.created_at>=?" if field == "from" else "r.created_at<?")
                params.append((parsed + (timedelta(days=1) if field == "to" else timedelta())).astimezone(timezone.utc).isoformat(timespec="microseconds"))
        if dates.get("from", datetime.min.replace(tzinfo=BRASILIA)) > dates.get("to", datetime.max.replace(tzinfo=BRASILIA)):
            abort(400)
        return " WHERE " + " AND ".join(clauses) if clauses else "", params

    def decode_row(row, conn):
        record = {key: row[key] for key in ("id", "created_at", "stage", "area", "format", "contact_consent", "survey_version", "privacy_version")}
        record.update(json.loads(cipher.decrypt(row["private_data"].encode()).decode()))
        record["gaps"] = [x[0] for x in conn.execute("SELECT gap FROM response_gaps WHERE response_id=? ORDER BY gap", (row["id"],))]
        return record

    @app.get("/api/admin/analytics")
    @admin_required
    def analytics():
        where, params = filters()
        with db() as conn:
            total_all = conn.execute("SELECT COUNT(*) FROM responses").fetchone()[0]
            total = conn.execute("SELECT COUNT(*) FROM responses r" + where, params).fetchone()[0]
            consent = conn.execute("SELECT COALESCE(SUM(contact_consent),0) FROM responses r" + where, params).fetchone()[0]
            groups = {}
            for field in ("stage", "area", "format", "gaps"):
                if field == "gaps":
                    rows = conn.execute("SELECT g.gap AS choice,COUNT(*) AS n FROM responses r JOIN response_gaps g ON g.response_id=r.id" + where + " GROUP BY g.gap", params).fetchall()
                else:
                    rows = conn.execute(f"SELECT r.{field} AS choice,COUNT(*) AS n FROM responses r" + where + f" GROUP BY r.{field}", params).fetchall()
                counts = {r["choice"]: r["n"] for r in rows}
                groups[field] = [{"code": code, "label": label, "count": counts.get(code, 0), "percent": round(100 * counts.get(code, 0)/total, 1) if total else 0} for code, label in LABELS[field].items()]
            days = [dict(r) for r in conn.execute("SELECT date(created_at,'-3 hours') AS day,COUNT(*) AS count FROM responses r" + where + " GROUP BY day ORDER BY day", params)]
            cumulative = 0
            for day in days:
                cumulative += day["count"]
                day["cumulative"] = cumulative
            cross = [dict(r) for r in conn.execute("SELECT stage,format,COUNT(*) AS count FROM responses r" + where + " GROUP BY stage,format", params)]
        insights = []
        for field, intro in (("gaps", "Preparação"), ("format", "Formato"), ("area", "Área de interesse")):
            best = sorted(groups[field], key=lambda x: -x["count"])
            if total and best[0]["count"]:
                tied = [x for x in best if x["count"] == best[0]["count"]]
                insights.append({"title": intro, "text": "; ".join(x["label"] for x in tied) + f" — {best[0]['count']} de {total} respostas ({best[0]['percent']}%)." + (" Há empate na liderança." if len(tied)>1 else "")})
        return jsonify(total=total, total_all=total_all, contact_consent=consent, groups=groups, days=days, cross=cross, insights=insights)

    @app.get("/api/admin/responses")
    @admin_required
    def records():
        where, params = filters()
        try:
            page = max(1, min(int(request.args.get("page", 1)), 1000000))
        except ValueError:
            abort(400)
        with db() as conn:
            count = conn.execute("SELECT COUNT(*) FROM responses r" + where, params).fetchone()[0]
            rows = conn.execute("SELECT r.* FROM responses r" + where + " ORDER BY created_at DESC,id DESC LIMIT 25 OFFSET ?", [*params, (page-1)*25]).fetchall()
            result = [decode_row(row, conn) for row in rows]
        return jsonify(rows=result, total=count, page=page, pages=max(1, (count+24)//25))

    @app.get("/api/admin/export.csv")
    @admin_required
    def export_csv():
        where, params = filters()
        with db() as conn, conn:
            audit(conn, "csv_export", actor=admin_identity())
        def safe_cell(value):
            value = str(value)
            if value.lstrip().startswith(("=", "+", "-", "@")) or value.startswith(("\t", "\r", "\n")):
                return "'" + value
            return value
        def stream():
            buffer = io.StringIO()
            writer = csv.writer(buffer, delimiter=";", quoting=csv.QUOTE_ALL)
            writer.writerow(["Protocolo", "Data (Brasília)", "Formação", "Área", "Dificuldades", "Formato", "Resposta aberta", "Nome", "E-mail", "WhatsApp", "Autorizou contato", "Versão da pesquisa", "Versão da privacidade"])
            yield "\ufeff" + buffer.getvalue()
            buffer.seek(0); buffer.truncate(0)
            with db() as conn:
                cursor = conn.execute("SELECT r.* FROM responses r" + where + " ORDER BY created_at,id", params)
                for row in cursor:
                    r = decode_row(row, conn)
                    values = [r["id"], datetime.fromisoformat(r["created_at"]).astimezone(BRASILIA).isoformat(), LABELS["stage"][r["stage"]], LABELS["area"][r["area"]], " | ".join(LABELS["gaps"][g] for g in r["gaps"]), LABELS["format"][r["format"]], r["wish"], r["name"], r["email"], r["phone"], "Sim" if r["contact_consent"] else "Não", r["survey_version"], r["privacy_version"]]
                    writer.writerow([safe_cell(x) for x in values])
                    yield buffer.getvalue()
                    buffer.seek(0); buffer.truncate(0)
        return Response(stream(), content_type="text/csv; charset=utf-8", headers={"Content-Disposition": 'attachment; filename="pesquisa-ifp.csv"'})

    return app
