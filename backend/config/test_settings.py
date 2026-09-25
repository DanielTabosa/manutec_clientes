"""Banco SQLite descartavel: nao valida particularidades do PostgreSQL."""
import os

os.environ.setdefault("DJANGO_SECRET_KEY", "somente-para-testes-isolados")
from .settings import *  # noqa: E402,F403

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
