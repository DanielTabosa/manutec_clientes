"""Cadastros na interface própria: reaproveitam formulários, serviços e regras do app `clientes`."""
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, OuterRef, Q, Subquery
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from clientes import destinatarios as domain
from clientes import destinatarios_fluxo
from clientes.consulta import ErroConsulta, consultar_cep, consultar_cnpj
from clientes.forms import (AdministradoraForm, CadastroClienteForm, ClienteEnderecoForm, TrocaCNPJForm,
                            VinculoAdministradoraForm)
from clientes.models import (Administradora, Cliente, ClienteAdministradora, Contato, ContatoAdministradora,
                             HistoricoCNPJ)
from clientes.services import alterar_administradora, cadastrar_cliente, trocar_cnpj

from .views import exige


class ContatoForm(forms.ModelForm):
    class Meta:
        model = Contato
        fields = ['nome', 'funcao', 'telefone', 'email', 'data_inicio', 'data_fim']
        widgets = {'data_inicio': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
                   'data_fim': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d')}


class ContatoAdministradoraForm(forms.ModelForm):
    class Meta:
        model = ContatoAdministradora
        fields = ['nome', 'telefone', 'email']


ROTULOS = dict(razao_social='Razão social', nome_fantasia='Nome fantasia', logradouro='Logradouro', numero='Número',
               complemento='Complemento', bairro='Bairro', cidade='Cidade', estado='Estado (UF)', observacoes='Observações',
               telefone='Telefone', email='E-mail', nome='Nome', funcao='Função')


def estilizar(form):
    for nome, campo in form.fields.items():
        if nome in ROTULOS:
            campo.label = ROTULOS[nome]
        w = campo.widget
        if isinstance(w, (forms.CheckboxInput, forms.HiddenInput)):
            continue
        classe = 'select' if isinstance(w, forms.Select) else 'textarea' if isinstance(w, forms.Textarea) else 'input'
        w.attrs['class'] = (w.attrs.get('class', '') + ' ' + classe).strip()
    return form


def aplicar_erros(form, exc):
    if hasattr(exc, 'message_dict'):
        for campo, erros in exc.message_dict.items():
            for erro in erros:
                form.add_error(campo if campo in form.fields else None, erro)
    else:
        form.add_error(None, exc)


def formulario(request, form, *, titulo, secao, voltar, rotulo='Salvar', crumbs=(), descricao='', consultas=False, aviso=''):
    estilizar(form)
    form._bound_fields_cache.clear()  # rótulos/classes valem também quando o formulário volta com erros
    return render(request, 'painel/formulario.html', dict(
        form=form, titulo=titulo, secao=secao, voltar=voltar, rotulo=rotulo, crumbs=crumbs,
        descricao=descricao, consultas=consultas, aviso=aviso))


# Consultas externas (CNPJ/CEP) para os formulários.

def _pode_consultar(user):
    return any(user.has_perm('clientes.' + p) for p in ('add_cliente', 'change_cliente', 'add_administradora', 'change_administradora'))


@login_required
def consulta_cnpj(request):
    if not _pode_consultar(request.user):
        raise PermissionDenied
    try:
        return JsonResponse(consultar_cnpj(request.GET.get('cnpj', '')))
    except ValidationError as exc:
        return JsonResponse({'erro': ' '.join(exc.messages)}, status=400)
    except ErroConsulta as exc:
        return JsonResponse({'erro': str(exc)}, status=503)


@login_required
def consulta_cep(request):
    if not _pode_consultar(request.user):
        raise PermissionDenied
    try:
        return JsonResponse(consultar_cep(request.GET.get('cep', '')))
    except ValidationError as exc:
        return JsonResponse({'erro': ' '.join(exc.messages)}, status=400)
    except ErroConsulta as exc:
        return JsonResponse({'erro': str(exc)}, status=503)


# Clientes

@exige('clientes.add_cliente')
def cliente_novo(request):
    form = CadastroClienteForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            obj = cadastrar_cliente(**form.cleaned_data)
        except ValidationError as exc:
            aplicar_erros(form, exc)
        else:
            messages.success(request, 'Cliente cadastrado com CNPJ e endereço.')
            return redirect('painel:cliente', obj.pk)
    return formulario(request, form, titulo='Novo cliente', secao='clientes', voltar=reverse('painel:clientes'),
                      rotulo='Cadastrar cliente', crumbs=[('Clientes', reverse('painel:clientes'))], consultas=True,
                      descricao='Ao completar o CNPJ, os dados são consultados automaticamente. Confira antes de salvar.')


@exige('clientes.change_cliente')
def cliente_editar(request, pk):
    obj = get_object_or_404(Cliente, pk=pk)
    form = ClienteEnderecoForm(request.POST or None, instance=obj)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Cadastro atualizado.')
        return redirect('painel:cliente', obj.pk)
    voltar = reverse('painel:cliente', args=[obj.pk])
    return formulario(request, form, titulo='Editar cadastro', secao='clientes', voltar=voltar, consultas=True,
                      crumbs=[('Clientes', reverse('painel:clientes')), (obj.razao_social, voltar)],
                      descricao='O CNPJ e a administradora têm histórico próprio e são alterados nas ações da ficha do cliente.')


@exige('clientes.change_cliente')
def cliente_cnpj(request, pk):
    obj = get_object_or_404(Cliente, pk=pk)
    form = TrocaCNPJForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            trocar_cnpj(obj.pk, **form.cleaned_data)
        except ValidationError as exc:
            aplicar_erros(form, exc)
        else:
            messages.success(request, 'CNPJ registrado. O histórico anterior foi preservado.')
            return redirect('painel:cliente', obj.pk)
    voltar = reverse('painel:cliente', args=[obj.pk])
    return formulario(request, form, titulo='Trocar CNPJ', secao='clientes', voltar=voltar, rotulo='Registrar CNPJ',
                      crumbs=[('Clientes', reverse('painel:clientes')), (obj.razao_social, voltar)],
                      descricao='O CNPJ atual é encerrado na véspera da data de início do novo. Nada é apagado do histórico.')


@exige('clientes.change_cliente')
def cliente_administradora(request, pk):
    if not request.user.has_perm('clientes.view_administradora'):
        raise PermissionDenied
    obj = get_object_or_404(Cliente, pk=pk)
    form = VinculoAdministradoraForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            alterar_administradora(obj.pk, **form.cleaned_data)
        except ValidationError as exc:
            aplicar_erros(form, exc)
        else:
            messages.success(request, 'Vínculo atualizado. O histórico foi preservado.')
            return redirect('painel:cliente', obj.pk)
    voltar = reverse('painel:cliente', args=[obj.pk])
    atual = ClienteAdministradora.objects.select_related('administradora').filter(cliente=obj, data_fim__isnull=True).first()
    return formulario(request, form, titulo='Administradora do condomínio', secao='clientes', voltar=voltar,
                      rotulo='Registrar', crumbs=[('Clientes', reverse('painel:clientes')), (obj.razao_social, voltar)],
                      descricao=f"Atual: {atual.administradora} desde {atual.data_inicio:%d/%m/%Y}." if atual else 'Sem administradora atual.',
                      aviso='Trocar ou encerrar a administradora retira do condomínio os destinatários da empresa anterior e encerra responsabilidades vigentes.')


@exige('clientes.add_contato')
def contato_novo(request, cliente_pk):
    cliente = get_object_or_404(Cliente, pk=cliente_pk)
    form = ContatoForm(request.POST or None, instance=Contato(cliente=cliente))
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Contato cadastrado. Para que receba documentos, selecione-o em “Quem recebe documentos”.')
        return redirect('painel:cliente', cliente.pk)
    voltar = reverse('painel:cliente', args=[cliente.pk])
    return formulario(request, form, titulo='Novo contato do condomínio', secao='clientes', voltar=voltar,
                      rotulo='Cadastrar contato', crumbs=[('Clientes', reverse('painel:clientes')), (cliente.razao_social, voltar)])


@exige('clientes.change_contato')
def contato_editar(request, pk):
    obj = get_object_or_404(Contato.objects.select_related('cliente'), pk=pk)
    form = ContatoForm(request.POST or None, instance=obj)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Contato atualizado.' + (' Encerrado: deixa de receber documentos; histórico preservado.' if obj.data_fim else ''))
        return redirect('painel:cliente', obj.cliente_id)
    voltar = reverse('painel:cliente', args=[obj.cliente_id])
    return formulario(request, form, titulo=f'Editar contato — {obj.nome}', secao='clientes', voltar=voltar,
                      crumbs=[('Clientes', reverse('painel:clientes')), (obj.cliente.razao_social, voltar)],
                      descricao='Para encerrar o contato, informe a data de encerramento. Ele deixa de receber documentos, e o histórico é preservado.')


def _destinatarios(request, escopo, pk, secao, voltar, crumbs):
    salvou, ctx = destinatarios_fluxo.tela(request, escopo, pk)
    if salvou:
        return redirect(request.path)
    for f in [ctx['form']]:
        estilizar(f)
    return render(request, 'painel/destinatarios.html', dict(ctx, secao=secao, voltar=voltar, crumbs=crumbs))


@login_required
def cliente_destinatarios(request, pk):
    voltar = reverse('painel:cliente', args=[pk])
    nome = get_object_or_404(Cliente, pk=pk).razao_social
    return _destinatarios(request, 'cliente', pk, 'clientes', voltar,
                          [('Clientes', reverse('painel:clientes')), (nome, voltar)])


# Administradoras

@exige('clientes.view_administradora')
def administradoras(request):
    termo = request.GET.get('q', '').strip()
    lista = Administradora.objects.annotate(
        condominios=Count('vinculos', filter=Q(vinculos__data_fim__isnull=True), distinct=True),
        contatos_ativos=Count('contatos', filter=Q(contatos__encerrado_em__isnull=True), distinct=True)).order_by('razao_social')
    if termo:
        digitos = ''.join(c for c in termo if c.isalnum())
        filtro = Q(razao_social__icontains=termo) | Q(nome_fantasia__icontains=termo)
        if len(digitos) >= 4 and any(c.isdigit() for c in digitos):
            filtro |= Q(cnpj__icontains=digitos.upper())
        lista = lista.filter(filtro)
    pagina = Paginator(lista, 25).get_page(request.GET.get('pagina'))
    return render(request, 'painel/administradoras.html', dict(secao='administradoras', pagina=pagina, termo=termo))


@exige('clientes.view_administradora')
def administradora(request, pk):
    obj = get_object_or_404(Administradora, pk=pk)
    cnpj = HistoricoCNPJ.objects.filter(cliente=OuterRef('cliente_id'), data_fim__isnull=True).values('cnpj')[:1]
    vinculos = (ClienteAdministradora.objects.filter(administradora=obj, data_fim__isnull=True)
                .select_related('cliente').annotate(cnpj_atual=Subquery(cnpj)).order_by('cliente__razao_social'))
    padrao = domain.atual(administradora_id=obj.pk)
    categorias_padrao = {}
    if padrao:
        for item in padrao.itens.all():
            categorias_padrao[item.contato_administradora_id] = [n for c, n in destinatarios_fluxo.NOMES_CATEGORIAS.items() if getattr(item, c)]
    contatos = list(obj.contatos.order_by('encerrado_em', 'nome'))
    for c in contatos:
        c.categorias_padrao = categorias_padrao.get(c.pk, [])
    return render(request, 'painel/administradora.html', dict(secao='administradoras', adm=obj, vinculos=vinculos, contatos=contatos))


@exige('clientes.add_administradora')
def administradora_nova(request):
    form = AdministradoraForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        obj = form.save()
        messages.success(request, 'Administradora cadastrada.')
        return redirect('painel:administradora', obj.pk)
    return formulario(request, form, titulo='Nova administradora', secao='administradoras', voltar=reverse('painel:administradoras'),
                      rotulo='Cadastrar administradora', crumbs=[('Administradoras', reverse('painel:administradoras'))], consultas=True)


@exige('clientes.change_administradora')
def administradora_editar(request, pk):
    obj = get_object_or_404(Administradora, pk=pk)
    form = AdministradoraForm(request.POST or None, instance=obj)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Administradora atualizada.')
        return redirect('painel:administradora', obj.pk)
    voltar = reverse('painel:administradora', args=[obj.pk])
    return formulario(request, form, titulo='Editar administradora', secao='administradoras', voltar=voltar, consultas=True,
                      crumbs=[('Administradoras', reverse('painel:administradoras')), (obj.razao_social, voltar)])


@exige('clientes.add_contatoadministradora')
def contato_adm_novo(request, adm_pk):
    adm = get_object_or_404(Administradora, pk=adm_pk)
    form = ContatoAdministradoraForm(request.POST or None, instance=ContatoAdministradora(administradora=adm))
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Contato cadastrado. Para que receba documentos, inclua-o nos destinatários padrão ou do condomínio.')
        return redirect('painel:administradora', adm.pk)
    voltar = reverse('painel:administradora', args=[adm.pk])
    return formulario(request, form, titulo='Novo contato da administradora', secao='administradoras', voltar=voltar,
                      rotulo='Cadastrar contato', crumbs=[('Administradoras', reverse('painel:administradoras')), (adm.razao_social, voltar)])


@exige('clientes.change_contatoadministradora')
def contato_adm_editar(request, pk):
    obj = get_object_or_404(ContatoAdministradora.objects.select_related('administradora'), pk=pk)
    form = ContatoAdministradoraForm(request.POST or None, instance=obj)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Contato atualizado.')
        return redirect('painel:administradora', obj.administradora_id)
    voltar = reverse('painel:administradora', args=[obj.administradora_id])
    return formulario(request, form, titulo=f'Editar contato — {obj.nome}', secao='administradoras', voltar=voltar,
                      crumbs=[('Administradoras', reverse('painel:administradoras')), (obj.administradora.razao_social, voltar)])


@require_POST
@login_required
def contato_adm_encerrar(request, pk):
    if not request.user.has_perms(['clientes.change_contatoadministradora', 'clientes.view_contatoadministradora',
                                   'clientes.change_configuracaodestinatarios']):
        raise PermissionDenied
    obj = get_object_or_404(ContatoAdministradora, pk=pk)
    domain.encerrar_global(obj.pk)
    messages.success(request, f'{obj.nome} encerrado na empresa inteira: deixa de receber documentos de todos os condomínios. Histórico preservado.')
    return redirect('painel:administradora', obj.administradora_id)


@login_required
def administradora_destinatarios(request, pk):
    voltar = reverse('painel:administradora', args=[pk])
    nome = get_object_or_404(Administradora, pk=pk).razao_social
    return _destinatarios(request, 'administradora', pk, 'administradoras', voltar,
                          [('Administradoras', reverse('painel:administradoras')), (nome, voltar)])
