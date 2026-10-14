from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.db.models import OuterRef, Q, Subquery
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from clientes import destinatarios, preparacao as servico, preparacao_fluxo as fluxo
from clientes.models import (Cliente, ClienteAdministradora, Contato, DestinatarioPreparacao, HistoricoCNPJ,
                             PreparacaoEnvio)
from clientes.preparacao_models import NOMES_CATEGORIAS

def exige(perm):
    """Anônimo vai para o login; autenticado sem permissão recebe 403."""
    def decorador(view):
        return login_required(permission_required(perm, raise_exception=True)(view))
    return decorador


ORIGENS = dict(condominio='Condomínio', padrao='Padrão da administradora', especifico='Específico do condomínio')


class Entrar(auth_views.LoginView):
    template_name = 'painel/entrar.html'
    redirect_authenticated_user = True


def _clientes_anotados():
    cnpj = HistoricoCNPJ.objects.filter(cliente=OuterRef('pk'), data_fim__isnull=True).values('cnpj')[:1]
    admin = ClienteAdministradora.objects.filter(cliente=OuterRef('pk'), data_fim__isnull=True).values('administradora__razao_social')[:1]
    return Cliente.objects.annotate(cnpj_atual=Subquery(cnpj), administradora_atual=Subquery(admin))


@login_required
def inicio(request):
    from django.db.models import Count, Q as Qd
    ctx = dict(secao='inicio', ve_preparacoes=request.user.has_perm('clientes.view_preparacaoenvio'))
    if ctx['ve_preparacoes']:
        base = PreparacaoEnvio.objects.select_related('cliente', 'criada_por')
        rascunhos = base.filter(status='rascunho').annotate(
            docs=Count('documentos', filter=Qd(documentos__removido_em__isnull=True)))
        pendencias = base.filter(status='confirmada').annotate(
            falhas=Count('destinatarios', filter=Qd(destinatarios__status_envio='falha')),
            pendentes=Count('destinatarios', filter=Qd(destinatarios__status_envio__in=['pendente', 'enviando']))
        ).filter(Qd(falhas__gt=0) | Qd(pendentes__gt=0)).order_by('-falhas', '-confirmada_em')
        hoje = _hoje()
        ctx.update(
            rascunhos=rascunhos[:6], total_rascunhos=rascunhos.count(),
            pendencias=pendencias[:6], total_pendencias=pendencias.count(),
            enviados_mes=DestinatarioPreparacao.objects.filter(status_envio='aceito', aceito_em__month=hoje.month,
                                                               aceito_em__year=hoje.year).count(),
            recentes=[(p, fluxo.situacao_envio(p)) for p in base.exclude(status='rascunho')[:6]],
        )
    return render(request, 'painel/inicio.html', ctx)


def _hoje():
    # USE_TZ=False: horários locais (America/Fortaleza), como no restante do projeto.
    from datetime import date
    return date.today()


@exige('clientes.view_cliente')
def clientes(request):
    termo = request.GET.get('q', '').strip()
    lista = _clientes_anotados().order_by('razao_social')
    if termo:
        digitos = ''.join(c for c in termo if c.isalnum())
        filtro = Q(razao_social__icontains=termo) | Q(nome_fantasia__icontains=termo) | Q(cidade__icontains=termo)
        if len(digitos) >= 4 and any(c.isdigit() for c in digitos):
            filtro |= Q(historico_cnpj__cnpj__icontains=digitos.upper())
        lista = lista.filter(filtro).distinct()
    pagina = Paginator(lista, 25).get_page(request.GET.get('pagina'))
    return render(request, 'painel/clientes.html', dict(secao='clientes', pagina=pagina, termo=termo))


@exige('clientes.view_cliente')
def cliente(request, pk):
    obj = get_object_or_404(_clientes_anotados(), pk=pk)
    vinculo = ClienteAdministradora.objects.select_related('administradora').filter(cliente=obj, data_fim__isnull=True).first()
    efetivos = []
    for item in destinatarios.efetivos(obj.pk):
        efetivos.append(dict(item, categorias=[NOMES_CATEGORIAS[c] for c in item['categorias']],
                             origens=[ORIGENS[o] for o in item['origens']]))
    ctx = dict(
        secao='clientes', cliente=obj, vinculo=vinculo, efetivos=efetivos,
        contatos=Contato.objects.filter(cliente=obj, data_fim__isnull=True).order_by('nome'),
        cnpjs_anteriores=HistoricoCNPJ.objects.filter(cliente=obj, data_fim__isnull=False).order_by('-data_fim'),
        preparacoes=[(p, fluxo.situacao_envio(p)) for p in obj.preparacoes_envio.select_related('criada_por')[:10]]
        if request.user.has_perm('clientes.view_preparacaoenvio') else None,
    )
    return render(request, 'painel/cliente.html', ctx)


@exige('clientes.view_preparacaoenvio')
def preparacoes(request):
    status = request.GET.get('status', '')
    termo = request.GET.get('q', '').strip()
    lista = PreparacaoEnvio.objects.select_related('cliente', 'criada_por')
    if status in ('rascunho', 'confirmada', 'cancelada'):
        lista = lista.filter(status=status)
    if termo:
        lista = lista.filter(Q(cliente__razao_social__icontains=termo) | Q(cliente__nome_fantasia__icontains=termo))
    pagina = Paginator(lista, 25).get_page(request.GET.get('pagina'))
    linhas = [(p, fluxo.situacao_envio(p)) for p in pagina]
    filtros = [('', 'Todas'), ('rascunho', 'Rascunhos'), ('confirmada', 'Confirmadas'), ('cancelada', 'Canceladas')]
    return render(request, 'painel/preparacoes.html', dict(secao='preparacoes', pagina=pagina, linhas=linhas,
                                                           status=status, termo=termo, filtros=filtros))


@require_POST
@exige('clientes.add_preparacaoenvio')
def nova_preparacao(request):
    obj = get_object_or_404(Cliente, pk=request.POST.get('cliente'))
    prep = servico.criar(obj.pk, request.user)
    return redirect('painel:preparacao', prep.pk)


@exige('clientes.view_preparacaoenvio')
def preparacao(request, pk):
    prep = get_object_or_404(PreparacaoEnvio.objects.select_related('cliente'), pk=pk)
    erros, boletos = [], None
    if request.method == 'POST':
        erros, boletos, ancora = fluxo.processar(request, prep)
        if ancora:
            return redirect(request.path + ancora)
    ctx = dict(secao='preparacoes', **fluxo.contexto(request, prep, erros, boletos))
    return render(request, 'painel/preparacao.html', ctx)


@exige('clientes.view_preparacaoenvio')
def documento(request, pk, doc_pk):
    return fluxo.resposta_documento(pk, doc_pk)
