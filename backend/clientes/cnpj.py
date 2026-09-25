import re
from django.core.exceptions import ValidationError


def normalizar_cnpj(valor):
    valor = re.sub(r"[.\s/-]", "", str(valor)).upper()
    if not re.fullmatch(r"[A-Z0-9]{12}[0-9]{2}", valor):
        raise ValidationError("Informe um CNPJ de 14 caracteres, com os dois últimos numéricos.")
    return valor
