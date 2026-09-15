"""Servidor exclusivo dos testes locais, com banco fornecido pelo executor."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app
from werkzeug.serving import run_simple

if __name__ == "__main__":
    run_simple("127.0.0.1", 8791, create_app({"SESSION_COOKIE_SECURE": False, "MIN_FORM_SECONDS": 0}), threaded=True)
