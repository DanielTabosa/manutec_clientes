"""Contratos dos clientes, cadastrados na própria base (o Conta Azul fica só como conferência opcional)."""
from django import forms
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from clientes.contratos_models import SITUACOES, Contrato, TipoContrato
from clientes.models import Cliente

from .cadastros import formulario
from .views import exige

DATA = dict(attrs={'type': 'date'}, format='%Y-%m-%d')


class ContratoForm(forms.ModelForm):
    class Meta:
        model = Contrato
        fields = ['tipo', 'situacao', 'data_inicio', 'data_fim', 'identificador', 'observacoes']
        widgets = {'data_inicio': forms.DateInput(**DATA), 'data_fim': forms.DateInput(**DATA),
                   'observacoes': forms.Textarea(attrs={'rows': 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Novos contratos só usam tipos disponíveis; na edição, o tipo atual continua na lista.
        tipos = Q(ativo=True)
        if self.instance.tipo_id:
            tipos |= Q(pk=self.instance.tipo_id)
        self.fields['tipo'].queryset = TipoContrato.objects.filter(tipos)
        self.fields['tipo'].empty_label = 'Selecione o tipo'
        self.fields['situacao'].label = 'Situação'
        self.fields['data_fim'].help_text = 'Deixe em branco se o contrato não tem data de término.'


class TipoContratoForm(forms.ModelForm):
    class Meta:
        model = TipoContrato
        fields = ['nome', 'descricao', 'ativo']

    def clean_nome(self):
        nome = ' '.join(self.cleaned_data['nome'].split())
        if TipoContrato.objects.filter(nome__iexact=nome).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('Já existe um tipo com este nome.')
        return nome


@exige('clientes.view_contrato')
def contratos(request):
    situacao = request.GET.get('situacao', '')
    tipo = request.GET.get('tipo', '')
    termo = request.GET.get('q', '').strip()
    lista = Contrato.objects.select_related('cliente', 'tipo').order_by('cliente__razao_social', '-data_inicio')
    if situacao in dict(SITUACOES):
        lista = lista.filter(situacao=situacao)
    if tipo.isdigit():
        lista = lista.filter(tipo_id=int(tipo))
    if termo:
        lista = lista.filter(Q(cliente__razao_social__icontains=termo) | Q(cliente__nome_fantasia__icontains=termo)
                             | Q(identificador__icontains=termo))
    pagina = Paginator(lista, 25).get_page(request.GET.get('pagina'))
    contagem = dict(Contrato.objects.values_list('situacao').annotate(n=Count('id')))
    filtros = [('', 'Todos', sum(contagem.values()))] + [(v, n, contagem.get(v, 0)) for v, n in SITUACOES]
    return render(request, 'painel/contratos.html', dict(
        secao='contratos', pagina=pagina, situacao=situacao, tipo=tipo, termo=termo, filtros=filtros,
        tipos=TipoContrato.objects.annotate(n=Count('contratos')).order_by('nome'),
        conferir=request.user.has_perm('clientes.view_cliente')))


def _crumbs(cliente):
    voltar = reverse('painel:cliente', args=[cliente.pk])
    return voltar, [('Clientes', reverse('painel:clientes')), (cliente.razao_social, voltar)]


@exige('clientes.add_contrato')
def contrato_novo(request, cliente_pk):
    cliente = get_object_or_404(Cliente, pk=cliente_pk)
    form = ContratoForm(request.POST or None, instance=Contrato(cliente=cliente))
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Contrato cadastrado.')
        return redirect('painel:cliente', cliente.pk)
    voltar, crumbs = _crumbs(cliente)
    sem_tipos = not TipoContrato.objects.filter(ativo=True).exists()
    return formulario(request, form, titulo='Novo contrato', secao='clientes', voltar=voltar, rotulo='Cadastrar contrato',
                      crumbs=crumbs, descricao='Um condomínio pode ter vários contratos, de tipos diferentes.',
                      aviso='Nenhum tipo de contrato disponível. Cadastre os tipos em Contratos › Tipos de contrato.' if sem_tipos else '')


@exige('clientes.change_contrato')
def contrato_editar(request, pk):
    obj = get_object_or_404(Contrato.objects.select_related('cliente', 'tipo'), pk=pk)
    form = ContratoForm(request.POST or None, instance=obj)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Contrato atualizado.')
        return redirect('painel:cliente', obj.cliente_id)
    voltar, crumbs = _crumbs(obj.cliente)
    return formulario(request, form, titulo=f'Editar contrato — {obj.tipo}', secao='clientes', voltar=voltar, crumbs=crumbs,
                      descricao='Contratos não são apagados: para encerrar, mude a situação para inativo e informe o fim.')


@exige('clientes.view_tipocontrato')
def tipos(request):
    pode_incluir = request.user.has_perm('clientes.add_tipocontrato')
    form = TipoContratoForm(request.POST or None) if pode_incluir else None
    if form is not None:
        form.fields.pop('ativo')  # tipo novo já nasce disponível
    if request.method == 'POST' and form is not None and form.is_valid():
        obj = form.save()
        messages.success(request, f'Tipo “{obj.nome}” cadastrado.')
        return redirect('painel:tipos_contrato')
    if form is not None:
        from .cadastros import estilizar
        estilizar(form)
        form.fields['nome'].label, form.fields['descricao'].label = 'Nome do tipo', 'Descrição'
    lista = TipoContrato.objects.annotate(
        total=Count('contratos'), ativos=Count('contratos', filter=Q(contratos__situacao='ativo'))).order_by('-ativo', 'nome')
    return render(request, 'painel/tipos_contrato.html', dict(secao='contratos', form=form, lista=lista))


@exige('clientes.change_tipocontrato')
def tipo_editar(request, pk):
    obj = get_object_or_404(TipoContrato, pk=pk)
    form = TipoContratoForm(request.POST or None, instance=obj)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Tipo de contrato atualizado.')
        return redirect('painel:tipos_contrato')
    voltar = reverse('painel:tipos_contrato')
    return formulario(request, form, titulo=f'Editar tipo — {obj.nome}', secao='contratos', voltar=voltar,
                      crumbs=[('Contratos', reverse('painel:contratos')), ('Tipos de contrato', voltar)],
                      descricao='Tipos em uso não são apagados. Desmarque “disponível” para tirá-lo da lista de novos contratos.')
