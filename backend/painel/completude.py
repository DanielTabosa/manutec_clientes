"""Completude do cadastro em lote (consultas agregadas, sem laço por cliente).

Mesmos cinco itens da ficha do cliente. "Quem recebe documentos" é aproximado em lote: a revisão mais recente
do condomínio ou do padrão da administradora atual tem itens (a ficha usa o cálculo exato)."""
from django.db.models import BooleanField, Case, Exists, F, OuterRef, Q, Subquery, Value, When

from clientes.models import (Cliente, ClienteAdministradora, Contato, Endereco, HistoricoCNPJ, ItemDestinatario,
                             RevisaoDestinatarios)

PENDENCIAS = [
    ('cnpj', 'Sem CNPJ/CPF atual'),
    ('endereco', 'Endereço incompleto'),
    ('administradora', 'Sem administradora'),
    ('email', 'Sem contato com e-mail'),
    ('destinatarios', 'Sem quem receba documentos'),
]
CAMPOS_ENDERECO = ('logradouro', 'numero', 'bairro', 'cidade', 'estado', 'cep')


def _booleano(*condicoes):
    return Case(*[When(c, then=Value(True)) for c in condicoes], default=Value(False), output_field=BooleanField())


def anotar(qs):
    # Endereço completo = o endereço principal tem todos os campos obrigatórios.
    endereco = Endereco.objects.filter(cliente=OuterRef('pk'), principal=True)
    for campo in CAMPOS_ENDERECO:
        endereco = endereco.filter(**{campo + '__isnull': False}).exclude(**{campo: ''})
    ultima = RevisaoDestinatarios.objects.filter(configuracao=OuterRef('configuracao')).order_by('-numero').values('pk')[:1]
    ultimas = RevisaoDestinatarios.objects.annotate(ultima=Subquery(ultima)).filter(pk=F('ultima')).values('pk')
    itens = ItemDestinatario.objects.filter(revisao__in=ultimas, encerrado_local=False)
    return qs.annotate(
        ok_cnpj=_booleano(Q(tipo_pessoa=Cliente.PF),
                          Exists(HistoricoCNPJ.objects.filter(cliente=OuterRef('pk'), data_fim__isnull=True))),
        ok_endereco=_booleano(Exists(endereco)),
        ok_administradora=_booleano(Exists(ClienteAdministradora.objects.filter(cliente=OuterRef('pk'), data_fim__isnull=True))),
        ok_email=_booleano(Exists(Contato.objects.filter(cliente=OuterRef('pk'), data_fim__isnull=True, email__gt=''))),
        ok_destinatarios=_booleano(
            Exists(itens.filter(revisao__configuracao__cliente=OuterRef('pk'))),
            Exists(itens.filter(revisao__configuracao__administradora__vinculos__cliente=OuterRef('pk'),
                                revisao__configuracao__administradora__vinculos__data_fim__isnull=True))),
    )


def filtro_pendencia(chave):
    return Q(**{'ok_' + chave: False})


def resumo(qs):
    """Contagens por pendência e quantos estão completos."""
    qs = anotar(qs)
    total = qs.count()
    contagens = {chave: qs.filter(filtro_pendencia(chave)).count() for chave, _ in PENDENCIAS}
    completos = qs.filter(ok_cnpj=True, ok_endereco=True, ok_administradora=True, ok_email=True, ok_destinatarios=True).count()
    return dict(total=total, completos=completos,
                pendencias=[(chave, nome, contagens[chave]) for chave, nome in PENDENCIAS],
                percentual=round(100 * completos / total) if total else 0)


def pontos(obj):
    return sum(1 for chave, _ in PENDENCIAS if getattr(obj, 'ok_' + chave, False))
