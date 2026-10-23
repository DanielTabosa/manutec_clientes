import re
from django.core.exceptions import ValidationError


def normalizar_cnpj(valor):
    valor = re.sub(r"[.\s/-]", "", str(valor)).upper()
    if not re.fullmatch(r"[A-Z0-9]{12}[0-9]{2}", valor):
        raise ValidationError("Informe um CNPJ de 14 caracteres, com os dois últimos numéricos.")
    return valor


def cnpj_dv_valido(valor):
    """Dígitos verificadores do CNPJ (também o alfanumérico). Usado só para desambiguar documentos na importação."""
    if not re.fullmatch(r"[A-Z0-9]{12}[0-9]{2}", valor or ""):
        return False
    numeros = [ord(c) - 48 for c in valor]
    for tamanho in (12, 13):
        pesos = list(range(tamanho - 7, 1, -1)) + list(range(9, 1, -1))
        resto = sum(n * p for n, p in zip(numeros[:tamanho], pesos)) % 11
        if numeros[tamanho] != (0 if resto < 2 else 11 - resto):
            return False
    return True
