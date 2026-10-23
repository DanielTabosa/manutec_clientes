import re
from django.core.exceptions import ValidationError


def cpf_valido(digitos):
    if not re.fullmatch(r"[0-9]{11}", digitos) or len(set(digitos)) == 1:
        return False
    for tamanho in (9, 10):
        soma = sum(int(d) * peso for d, peso in zip(digitos[:tamanho], range(tamanho + 1, 1, -1)))
        if int(digitos[tamanho]) != (soma * 10 % 11) % 10:
            return False
    return True


def normalizar_cpf(valor):
    valor = re.sub(r"[.\s-]", "", str(valor))
    if not re.fullmatch(r"[0-9]{11}", valor):
        raise ValidationError("Informe um CPF de 11 números.")
    if not cpf_valido(valor):
        raise ValidationError("CPF inválido: confira os dígitos verificadores.")
    return valor
