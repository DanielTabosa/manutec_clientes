import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    raise ImproperlyConfigured("Configure DJANGO_SECRET_KEY no backend/.env.")
DEBUG = os.getenv("DJANGO_DEBUG", "False").lower() == "true"
ALLOWED_HOSTS = [host.strip() for host in os.getenv(
    "DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1"
).split(",") if host.strip()]
INSTALLED_APPS = [
    "django.contrib.admin", "django.contrib.auth", "django.contrib.contenttypes",
    "django.contrib.sessions", "django.contrib.messages", "django.contrib.staticfiles",
    "rest_framework", "clientes", "painel",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "config.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"], "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]
WSGI_APPLICATION = "config.wsgi.application"
DATABASES = {"default": {
    "ENGINE": "django.db.backends.postgresql",
    "NAME": os.getenv("POSTGRES_DB", "manutec_clientes"),
    "USER": os.getenv("POSTGRES_USER", "postgres"),
    "PASSWORD": os.getenv("POSTGRES_PASSWORD", ""),
    "HOST": os.getenv("POSTGRES_HOST", "localhost"),
    "PORT": os.getenv("POSTGRES_PORT", "5432"),
    "OPTIONS": {"connect_timeout": 5},
}}
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Fortaleza"
# O schema existente usa TIMESTAMP sem fuso. Manter horarios locais nesta etapa.
USE_TZ = False
USE_I18N = True
STATIC_URL = "static/"
LOGIN_URL = "painel:entrar"
LOGIN_REDIRECT_URL = "painel:inicio"
LOGOUT_REDIRECT_URL = "painel:entrar"
# PDFs de preparações: fora do Git e sem URL pública; servidos só pelo painel autenticado.
ARQUIVOS_PRIVADOS_DIR = Path(os.getenv("DJANGO_ARQUIVOS_PRIVADOS", BASE_DIR / "privado"))
# Envio de documentos: conta do domínio (cPanel). Sem host/remetente, o envio fica desabilitado no painel.
EMAIL_BACKEND = os.getenv("DJANGO_EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = os.getenv("DJANGO_EMAIL_HOST", "")
EMAIL_PORT = int(os.getenv("DJANGO_EMAIL_PORT", "465"))
EMAIL_USE_SSL = os.getenv("DJANGO_EMAIL_USE_SSL", "True").lower() == "true"
EMAIL_USE_TLS = os.getenv("DJANGO_EMAIL_USE_TLS", "False").lower() == "true"
if EMAIL_USE_SSL and EMAIL_USE_TLS:
    raise ImproperlyConfigured("Use DJANGO_EMAIL_USE_SSL (porta 465) ou DJANGO_EMAIL_USE_TLS (porta 587), não ambos.")
EMAIL_HOST_USER = os.getenv("DJANGO_EMAIL_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("DJANGO_EMAIL_PASSWORD", "")
EMAIL_TIMEOUT = 30
DEFAULT_FROM_EMAIL = os.getenv("DJANGO_EMAIL_FROM", "")
EMAIL_REPLY_TO = os.getenv("DJANGO_EMAIL_REPLY_TO", "")
# Busca de boleto/NFS-e no painel: "producao" ou "desenvolvimento"; vazio desabilita. Somente consultas GET.
CONTAAZUL_AMBIENTE = os.getenv("DJANGO_CONTAAZUL_AMBIENTE", "")
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["clientes.permissions.PermissoesCliente"],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 25,
}
