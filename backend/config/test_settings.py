"""Banco SQLite descartavel: nao valida particularidades do PostgreSQL."""
import os

os.environ.setdefault("DJANGO_SECRET_KEY", "somente-para-testes-isolados")
from .settings import *  # noqa: E402,F403

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
# Testes nunca usam integrações reais configuradas no .env local.
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
EMAIL_HOST = ""
DEFAULT_FROM_EMAIL = ""
CONTAAZUL_AMBIENTE = ""
