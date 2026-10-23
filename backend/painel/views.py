from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.db.models import OuterRef, Q, Subquery
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from clientes import destinatarios, preparacao as servico, preparacao_fluxo as fluxo
from clientes.models import (Cliente, ClienteAdministradora, Contato, DestinatarioPreparacao, Endereco, HistoricoCNPJ,
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
    principal = Endereco.objects.filter(cliente=OuterRef('pk'), principal=True)
    return Cliente.objects.annotate(
        cnpj_atual=Subquery(cnpj), documento=Coalesce('cpf', Subquery(cnpj)), administradora_atual=Subquery(admin),
        cidade_principal=Subquery(principal.values('cidade')[:1]), uf_principal=Subquery(principal.values('estado')[:1]))


def _filtro_busca(termo):
    """Nome, fantasia, cidade de qualquer endereço e documento (CPF ou CNPJ atual/anterior)."""
    filtro = (Q(razao_social__icontains=termo) | Q(nome_fantasia__icontains=termo) |
              Q(enderecos__cidade__icontains=termo))
    digitos = ''.join(c for c in termo if c.isalnum()).upper()
    if len(digitos) >= 4 and any(c.isdigit() for c in digitos):
        filtro |= Q(historico_cnpj__cnpj__icontains=digitos) | Q(cpf__icontains=digitos)
    return filtro


@login_required
def inicio(request):
    from django.db.models import Count, Q as Qd
    from clientes.contratos_models import Contrato
    from clientes.models import Administradora, ContatoAdministradora
    from . import completude
    pode = request.user.has_perm
    ctx = dict(secao='inicio', ve_preparacoes=pode('clientes.view_preparacaoenvio'), ve_clientes=pode('clientes.view_cliente'),
               ve_administradoras=pode('clientes.view_administradora'), ve_contratos=pode('clientes.view_contrato'))
    if ctx['ve_contratos']:
        situacoes = dict(Contrato.objects.values_list('situacao').annotate(n=Count('id')))
        ativos = Contrato.objects.filter(situacao='ativo')
        ctx['ctr'] = dict(
            ativos=situacoes.get('ativo', 0), suspensos=situacoes.get('suspenso', 0), inativos=situacoes.get('inativo', 0),
            clientes=ativos.values('cliente_id').distinct().count(),
            por_tipo=ativos.values('tipo_id', 'tipo__nome').annotate(n=Count('id')).order_by('-n', 'tipo__nome')[:6],
        )
    if ctx['ve_clientes']:
        ctx['base'] = completude.resumo(Cliente.objects.all())
        ctx['clientes_recentes'] = completude.anotar(_clientes_anotados()).order_by('-criado_em')[:5]
        for c in ctx['clientes_recentes']:
            c.pontos = completude.pontos(c)
    if ctx['ve_administradoras']:
        adms = Administradora.objects.annotate(condominios=Count('vinculos', filter=Qd(vinculos__data_fim__isnull=True), distinct=True))
        ctx['adm'] = dict(
            total=adms.count(),
            vinculados=ClienteAdministradora.objects.filter(data_fim__isnull=True).count(),
            sem_email=adms.exclude(pk__in=ContatoAdministradora.objects.filter(encerrado_em__isnull=True, email__gt='')
                                   .values('administradora_id')).count(),
            principais=adms.filter(condominios__gt=0).order_by('-condominios', 'razao_social')[:5],
        )
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
            rascunhos=rascunhos[:5], total_rascunhos=rascunhos.count(),
            pendencias=pendencias[:5], total_pendencias=pendencias.count(),
            enviados_mes=DestinatarioPreparacao.objects.filter(status_envio='aceito', aceito_em__month=hoje.month,
                                                               aceito_em__year=hoje.year).count(),
        )
    return render(request, 'painel/inicio.html', ctx)


def _hoje():
    # USE_TZ=False: horários locais (America/Fortaleza), como no restante do projeto.
    from datetime import date
    return date.today()


@exige('clientes.view_cliente')
def clientes(request):
    from . import completude
    termo = request.GET.get('q', '').strip()
    pendencia = request.GET.get('pendencia', '')
    lista = completude.anotar(_clientes_anotados()).order_by('razao_social')
    if pendencia in dict(completude.PENDENCIAS):
        lista = lista.filter(completude.filtro_pendencia(pendencia))
    if termo:
        lista = lista.filter(_filtro_busca(termo)).distinct()
    pagina = Paginator(lista, 25).get_page(request.GET.get('pagina'))
    for c in pagina:
        c.pontos = completude.pontos(c)
    return render(request, 'painel/clientes.html', dict(secao='clientes', pagina=pagina, termo=termo, pendencia=pendencia,
                                                        pendencias=completude.PENDENCIAS, total_itens=len(completude.PENDENCIAS)))


@exige('clientes.view_cliente')
def cliente(request, pk):
    obj = get_object_or_404(_clientes_anotados(), pk=pk)
    vinculo = ClienteAdministradora.objects.select_related('administradora').filter(cliente=obj, data_fim__isnull=True).first()
    efetivos = []
    for item in destinatarios.efetivos(obj.pk):
        efetivos.append(dict(item, categorias=[NOMES_CATEGORIAS[c] for c in item['categorias']],
                             origens=[ORIGENS[o] for o in item['origens']]))
    from clientes.models import Responsabilidade
    contatos = list(Contato.objects.filter(cliente=obj, data_fim__isnull=True).order_by('nome'))
    enderecos = list(obj.enderecos.all())
    principal = next((e for e in enderecos if e.principal), None)
    # Completude do cadastro: o foco do sistema é uma base de clientes confiável.
    completude = [
        ('Documento atual', bool(obj.documento)),
        ('Endereço completo', bool(principal and principal.completo)),
        ('Administradora definida', bool(vinculo)),
        ('Contato com e-mail', any(c.email for c in contatos)),
        ('Quem recebe documentos', bool(efetivos)),
    ]
    ctx = dict(
        secao='clientes', cliente=obj, vinculo=vinculo, enderecos=[e for e in enderecos if e.ativo],
        enderecos_inativos=[e for e in enderecos if not e.ativo], efetivos=efetivos, contatos=contatos, completude=completude,
        completos=sum(1 for _, ok in completude if ok),
        contatos_encerrados=Contato.objects.filter(cliente=obj, data_fim__isnull=False).order_by('-data_fim'),
        administradoras_anteriores=ClienteAdministradora.objects.select_related('administradora')
        .filter(cliente=obj, data_fim__isnull=False).order_by('-data_fim'),
        responsabilidades=Responsabilidade.objects.select_related('contato_administradora')
        .filter(cliente=obj, data_fim__isnull=True).order_by('funcao'),
        contratos=obj.contratos.select_related('tipo').order_by('situacao', '-data_inicio')
        if request.user.has_perm('clientes.view_contrato') else None,
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


@login_required
def busca(request):
    from clientes.models import Administradora
    termo = request.GET.get('q', '').strip()
    resultados = dict(clientes=[], administradoras=[], preparacoes=[])
    if len(termo) >= 2:
        digitos = ''.join(c for c in termo if c.isalnum()).upper()
        tem_numero = len(digitos) >= 4 and any(c.isdigit() for c in digitos)
        if request.user.has_perm('clientes.view_cliente'):
            resultados['clientes'] = list(_clientes_anotados().filter(_filtro_busca(termo)).distinct().order_by('razao_social')[:8])
        if request.user.has_perm('clientes.view_administradora'):
            filtro = Q(razao_social__icontains=termo) | Q(nome_fantasia__icontains=termo)
            if tem_numero:
                filtro |= Q(cnpj__icontains=digitos)
            resultados['administradoras'] = list(Administradora.objects.filter(filtro).order_by('razao_social')[:8])
        if request.user.has_perm('clientes.view_preparacaoenvio'):
            filtro = Q(cliente__razao_social__icontains=termo) | Q(cliente__nome_fantasia__icontains=termo)
            if termo.lstrip('#').isdigit():
                filtro |= Q(pk=int(termo.lstrip('#')))
            resultados['preparacoes'] = [(p, fluxo.situacao_envio(p)) for p in
                                         PreparacaoEnvio.objects.select_related('cliente').filter(filtro)[:8]]
    total = sum(len(v) for v in resultados.values())
    return render(request, 'painel/busca.html', dict(secao='', termo_global=termo, termo=termo, total=total, **resultados))


def _resumo_contratos(forcar):
    """Conferência opcional: agrupa os contratos do Conta Azul por cliente (um cliente pode ter vários)."""
    from clientes import contratos as contratos_ca
    from clientes.contratos_models import Contrato
    dados = contratos_ca.carregar(forcar=forcar)
    com, sem = contratos_ca.cruzar(dados['itens']) if dados['ok'] else ([], [])
    por_cliente = {}
    for c in com:
        por_cliente[c['cliente_id']] = por_cliente.get(c['cliente_id'], 0) + 1
    com_ativo = set(Contrato.objects.filter(situacao='ativo').values_list('cliente_id', flat=True))
    nomes = dict(Cliente.objects.filter(pk__in=por_cliente).values_list('pk', 'razao_social'))
    sem_contrato = sorted((dict(cliente_id=pk, nome=nomes.get(pk, ''), qtd=n) for pk, n in por_cliente.items()
                           if pk not in com_ativo), key=lambda x: x['nome'])
    fora = {}
    for c in sem:
        chave = c['documento'] or contratos_ca._normalizar_nome(c['cliente'])
        fora.setdefault(chave, dict(c, qtd=0))['qtd'] += 1
    fora = sorted(fora.values(), key=lambda x: x['cliente'])
    return dict(dados, total=len(dados['itens']), clientes=len(por_cliente) + len(fora),
                sem_contrato=sem_contrato[:8], total_sem_contrato=len(sem_contrato), sem=fora[:8], total_sem=len(fora))


@exige('clientes.view_cliente')
def contratos_resumo(request):
    """Conferência com o Conta Azul, carregada sob demanda na tela de contratos (pode levar alguns segundos)."""
    if not servico.contaazul_config():
        return render(request, 'painel/_contratos.html', dict(contratos=None))
    return render(request, 'painel/_contratos.html', dict(contratos=_resumo_contratos(request.GET.get('atualizar') == '1')))

