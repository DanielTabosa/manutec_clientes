"""Contratos ativos do Conta Azul (somente leitura), cruzados com os clientes cadastrados.

Consulta GET /v1/contratos com cache curto: o painel não chama a API a cada página.
Falhas (ex.: autorização expirada) viram um aviso, sem travar a tela."""
import re
import unicodedata
from datetime import date

from django.core.cache import cache

CHAVE_CACHE = 'contaazul:contratos-ativos'
VALIDADE = 15 * 60
VALIDADE_ERRO = 2 * 60


def _normalizar_nome(texto):
    texto = unicodedata.normalize('NFKD', texto or '').encode('ascii', 'ignore').decode().upper()
    texto = re.sub(r'\b(CONDOMINIO|COND|DO|DA|DE|DOS|DAS|EDIFICIO|ED|RESIDENCIAL|RES)\b', ' ', texto)
    return ' '.join(re.sub(r'[^A-Z0-9 ]', ' ', texto).split())


def _documento(cliente):
    for chave in ('documento', 'cpf_cnpj', 'cnpj', 'cpf'):
        valor = re.sub(r'[^0-9A-Za-z]', '', str(cliente.get(chave) or '')).upper()
        if len(valor) in (11, 14):
            return valor
    return ''


def carregar(forcar=False):
    """Retorna dict(ok, erro, itens, atualizado). Itens: numero, cliente, documento, vencimento, valor."""
    if not forcar:
        guardado = cache.get(CHAVE_CACHE)
        if guardado is not None:
            return guardado
    from . import preparacao
    caminho = preparacao.contaazul_config()
    if not caminho:
        return dict(ok=False, erro='Integração com o Conta Azul não configurada.', itens=[], atualizado=None)
    from urllib.error import HTTPError
    import contaazul_boleto
    try:
        get = contaazul_boleto._cliente_http(caminho)
        itens = []
        for pagina in range(1, 11):
            dados = get('/v1/contratos', {'pagina': pagina, 'tamanho_pagina': 50,
                                          'data_inicio': '2000-01-01', 'data_fim': date.today().isoformat()})
            lote = dados.get('itens') if isinstance(dados.get('itens'), list) else dados.get('items')
            if not isinstance(lote, list):
                raise ValueError()
            itens += [c for c in lote if isinstance(c, dict)]
            if len(lote) < 50:
                break
        else:
            raise ValueError()
        # O contrato só traz id e nome do cliente; o CNPJ vem da lista de pessoas (GET /v1/pessoas).
        documentos = {}
        for pagina in range(1, 31):
            dados = get('/v1/pessoas', {'pagina': pagina, 'tamanho_pagina': 50})
            lote = dados.get('items') if isinstance(dados.get('items'), list) else dados.get('itens')
            if not isinstance(lote, list):
                raise ValueError()
            for pessoa in lote:
                if isinstance(pessoa, dict) and pessoa.get('id'):
                    documentos[str(pessoa['id'])] = _documento(pessoa)
            if len(lote) < 50:
                break
        else:
            raise ValueError()
        ativos = []
        for c in itens:
            if c.get('status') != 'ATIVO':
                continue
            cliente = c.get('cliente') if isinstance(c.get('cliente'), dict) else {}
            ativos.append(dict(numero=c.get('numero'), cliente=str(cliente.get('nome') or '').strip(),
                               documento=_documento(cliente) or documentos.get(str(cliente.get('id')), ''),
                               vencimento=c.get('proximo_vencimento') or '',
                               valor=c.get('total_proximo_vencimento', c.get('total'))))
        resultado = dict(ok=True, erro='', itens=ativos, atualizado=date.today())
        cache.set(CHAVE_CACHE, resultado, VALIDADE)
    except HTTPError as exc:
        exc.close()
        erro = ('Autorização do Conta Azul expirada. Renove com contaazul_auth.py para ver os contratos.'
                if exc.code == 401 else f'O Conta Azul respondeu HTTP {exc.code} ao listar contratos.')
        resultado = dict(ok=False, erro=erro, itens=[], atualizado=None)
        cache.set(CHAVE_CACHE, resultado, VALIDADE_ERRO)
    except Exception:
        resultado = dict(ok=False, erro='Não foi possível listar os contratos do Conta Azul agora.', itens=[], atualizado=None)
        cache.set(CHAVE_CACHE, resultado, VALIDADE_ERRO)
    return resultado


def cruzar(contratos):
    """Associa cada contrato a um cliente cadastrado: pelo documento (CNPJ atual) ou pelo nome normalizado."""
    from .models import Cliente, HistoricoCNPJ
    por_cnpj = dict(HistoricoCNPJ.objects.filter(data_fim__isnull=True).values_list('cnpj', 'cliente_id'))
    por_cnpj.update(Cliente.objects.filter(cpf__isnull=False).values_list('cpf', 'pk'))
    por_nome = {}
    for pk, razao, fantasia in Cliente.objects.values_list('pk', 'razao_social', 'nome_fantasia'):
        for nome in (razao, fantasia):
            chave = _normalizar_nome(nome)
            if chave:
                por_nome.setdefault(chave, set()).add(pk)
    com, sem = [], []
    for c in contratos:
        cliente_id = por_cnpj.get(c['documento']) if c['documento'] else None
        if cliente_id is None:
            candidatos = por_nome.get(_normalizar_nome(c['cliente']), set())
            cliente_id = next(iter(candidatos)) if len(candidatos) == 1 else None
        (com if cliente_id else sem).append(dict(c, cliente_id=cliente_id))
    return com, sem
