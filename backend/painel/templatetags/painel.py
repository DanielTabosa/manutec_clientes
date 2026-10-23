import re

from django import template

register = template.Library()


@register.filter
def cnpj(valor):
    digitos = re.sub(r'[^0-9A-Za-z]', '', valor or '')
    if len(digitos) != 14:
        return valor or ''
    return f'{digitos[:2]}.{digitos[2:5]}.{digitos[5:8]}/{digitos[8:12]}-{digitos[12:]}'


@register.filter
def documento(valor):
    """CPF (11 números) ou CNPJ (14 caracteres) com máscara."""
    digitos = re.sub(r'[^0-9A-Za-z]', '', valor or '')
    if len(digitos) == 11 and digitos.isdigit():
        return f'{digitos[:3]}.{digitos[3:6]}.{digitos[6:9]}-{digitos[9:]}'
    return cnpj(valor)


@register.filter
def iniciais(nome):
    partes = [p for p in (nome or '').split() if p[:1].isalnum()]
    return ''.join(p[0] for p in partes[:2]).upper() or '?'
