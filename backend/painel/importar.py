"""Telas da importação em lote: escolher tipo e arquivo → prévia com colunas reconhecidas → confirmar → resultado."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse

from . import importacao

SESSAO = 'importacao'


def _tipos_permitidos(user):
    return [(chave, t) for chave, t in importacao.TIPOS.items() if user.has_perm(t['permissao'])]


def _exigir(user, tipo):
    if tipo not in importacao.TIPOS:
        raise PermissionDenied
    if not user.has_perm(importacao.TIPOS[tipo]['permissao']):
        raise PermissionDenied


@login_required
def inicio(request):
    tipos = _tipos_permitidos(request.user)
    if not tipos:
        raise PermissionDenied
    erro = None
    if request.method == 'POST':
        tipo = request.POST.get('tipo', '')
        _exigir(request.user, tipo)
        arquivo = request.FILES.get('arquivo')
        try:
            if not arquivo:
                raise ValidationError('Escolha o arquivo CSV.')
            cabecalhos, linhas, texto = importacao.ler(arquivo.read(importacao.LIMITE_BYTES + 1))
            request.session[SESSAO] = dict(tipo=tipo, texto=texto, arquivo=arquivo.name[:120],
                                           mapa=importacao.mapear(tipo, cabecalhos))
            return redirect('painel:importar_previa')
        except ValidationError as exc:
            erro = ' '.join(exc.messages)
    return render(request, 'painel/importar.html', dict(secao='importar', tipos=tipos, erro=erro,
                                                        selecionado=request.POST.get('tipo') or request.GET.get('tipo', '')))


@login_required
def modelo(request, tipo):
    _exigir(request.user, tipo)
    resposta = HttpResponse(importacao.modelo_csv(tipo), content_type='text/csv; charset=utf-8')
    resposta['Content-Disposition'] = f'attachment; filename="modelo-{tipo}.csv"'
    return resposta


@login_required
def previa(request):
    estado = request.session.get(SESSAO)
    if not estado:
        messages.warning(request, 'Envie um arquivo CSV para começar.')
        return redirect('painel:importar')
    tipo = estado['tipo']
    _exigir(request.user, tipo)
    cabecalhos, linhas, _ = importacao.ler(estado['texto'].encode('utf-8'))
    mapa = {campo: int(i) for campo, i in estado['mapa'].items()}
    if request.method == 'POST' and request.POST.get('acao') in ('remapear', 'confirmar'):
        novo = {}
        for campo, *_ in importacao.TIPOS[tipo]['campos']:
            valor = request.POST.get('col_' + campo, '')
            if valor.isdigit() and int(valor) < len(cabecalhos):
                novo[campo] = int(valor)
        mapa = novo
        estado['mapa'] = mapa
        request.session[SESSAO] = estado
    erro = None
    try:
        analise = importacao.analisar(tipo, linhas, mapa)
    except ValidationError as exc:
        analise, erro = [], ' '.join(exc.messages)
    if request.method == 'POST' and request.POST.get('acao') == 'confirmar' and not erro:
        resultado = importacao.importar(tipo, analise)
        request.session.pop(SESSAO, None)
        request.session['importacao_resultado'] = dict(
            tipo=tipo, criados=resultado['criados'], falhas=resultado['falhas'], arquivo=estado['arquivo'],
            existentes=sum(1 for a in analise if a['status'] == 'existente'),
            erros=[(a['linha'], a['titulo'], '; '.join(a['notas'])) for a in analise if a['status'] == 'erro'])
        return redirect('painel:importar_resultado')
    if request.method == 'POST' and request.POST.get('acao') == 'descartar':
        request.session.pop(SESSAO, None)
        messages.success(request, 'Importação descartada. Nada foi gravado.')
        return redirect('painel:importar')
    contagem = {s: sum(1 for a in analise if a['status'] == s) for s in ('novo', 'existente', 'erro')}
    com_pendencia = sum(1 for a in analise if a['status'] == 'novo' and a['notas'])
    campos = [dict(campo=c, rotulo=r, obrigatorio=o, coluna=mapa.get(c)) for c, r, o, _ in importacao.TIPOS[tipo]['campos']]
    return render(request, 'painel/importar_previa.html', dict(
        secao='importar', tipo=tipo, nome_tipo=importacao.TIPOS[tipo]['nome'], arquivo=estado['arquivo'],
        cabecalhos=list(enumerate(cabecalhos)), campos=campos, analise=analise[:300], total=len(analise),
        contagem=contagem, com_pendencia=com_pendencia, erro=erro))


@login_required
def resultado(request):
    dados = request.session.get('importacao_resultado')
    if not dados:
        return redirect('painel:importar')
    destino = {'clientes': 'painel:clientes', 'contatos': 'painel:clientes', 'administradoras': 'painel:administradoras',
               'contatos_administradora': 'painel:administradoras', 'contratos': 'painel:contratos'}[dados['tipo']]
    return render(request, 'painel/importar_resultado.html', dict(
        secao='importar', r=dados, nome_tipo=importacao.TIPOS[dados['tipo']]['nome'], destino=reverse(destino)))
