from django import forms
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.forms import formset_factory
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html
from rest_framework.exceptions import PermissionDenied as APIPermissionDenied
from . import destinatarios as domain
from .destinatarios_api import exigir, estado, historico, encerramentos
from .destinatarios_models import CATEGORIAS


class ConfigForm(forms.Form):
    numero = forms.IntegerField(widget=forms.HiddenInput, min_value=0)
    vinculo_id = forms.IntegerField(widget=forms.HiddenInput, required=False)
    modo = forms.ChoiceField(label='Contatos da administradora', choices=[('usar', 'Usar padrão'), ('complementar', 'Complementar padrão'), ('substituir', 'Substituir padrão')])


class ItemForm(forms.Form):
    contato_id = forms.IntegerField(required=False, widget=forms.HiddenInput)
    contato_administradora_id = forms.IntegerField(required=False, widget=forms.HiddenInput)
    boleto = forms.BooleanField(required=False)
    nota_fiscal = forms.BooleanField(required=False)
    laudo = forms.BooleanField(required=False)
    comunicado = forms.BooleanField(required=False)
    cobranca = forms.BooleanField(required=False)
    encerrado_local = forms.BooleanField(required=False, label='Encerrar neste condomínio')


class DestinatariosAdminMixin:
    def get_urls(self):
        escopo = self.model._meta.model_name
        return [path('<int:pk>/destinatarios/', self.admin_site.admin_view(self.destinatarios_view), name=f'clientes_{escopo}_destinatarios')] + super().get_urls()

    def gerenciar_destinatarios(self, obj):
        if not obj or not obj.pk:
            return 'Salve o cadastro primeiro.'
        return format_html('<a href="{}">Destinatários e histórico</a>', reverse(f'admin:clientes_{self.model._meta.model_name}_destinatarios', args=[obj.pk]))
    gerenciar_destinatarios.short_description = 'Documentos e comunicações'

    def destinatarios_view(self, request, pk):
        escopo = self.model._meta.model_name
        try:
            exigir(request.user, escopo, request.method == 'POST')
        except APIPermissionDenied as exc:
            raise PermissionDenied from exc
        obj = get_object_or_404(self.model, pk=pk)
        dados = estado(escopo, pk)
        contatos = []
        vinculo = None
        if escopo == 'cliente':
            contatos += [(c, 'contato_id') for c in domain.Contato.objects.filter(cliente_id=pk, data_fim__isnull=True)]
            vinculo = domain.ClienteAdministradora.objects.filter(cliente_id=pk, data_fim__isnull=True).first()
            empresa_id = vinculo.administradora_id if vinculo else None
        else:
            empresa_id = pk
        if empresa_id:
            contatos += [(c, 'contato_administradora_id') for c in domain.ContatoAdministradora.objects.filter(administradora_id=empresa_id, encerrado_em__isnull=True)]
        selecionados = {(i['contato_id'], i['contato_administradora_id']): i for i in dados['itens']}
        iniciais = []
        for contato, campo in contatos:
            chave = (contato.pk, None) if campo == 'contato_id' else (None, contato.pk)
            iniciais.append(selecionados.get(chave, {campo: contato.pk}))
        Forms = formset_factory(ItemForm, extra=0, max_num=1000, validate_max=True)
        form = ConfigForm(request.POST or None, initial=dados)
        if escopo == 'administradora':
            form.fields['modo'].widget = forms.HiddenInput()
        formset = Forms(request.POST or None, initial=iniciais)
        erro = None
        if request.method == 'POST' and form.is_valid() and formset.is_valid():
            itens = [f.cleaned_data for f in formset if any(f.cleaned_data.get(c) for c in (*CATEGORIAS, 'encerrado_local'))]
            try:
                domain.salvar(**{escopo + '_id': pk}, autor=request.user, itens=itens, **form.cleaned_data)
            except ValidationError as exc:
                erro = '; '.join(exc.messages)
            else:
                messages.success(request, 'Destinatários atualizados. Alteração imediata; histórico preservado.')
                return redirect(request.path)
        # Labels use the submitted ID, never its position, on validation errors.
        labels = {(campo, c.pk): c for c, campo in contatos}
        linhas = []
        for f in formset:
            campo = 'contato_id' if f['contato_id'].value() else 'contato_administradora_id'
            try:
                contato = labels.get((campo, int(f[campo].value())))
            except (ValueError, TypeError):
                contato = None
            linhas.append((f, contato, campo == 'contato_administradora_id'))
        from django.core.paginator import Paginator
        revisoes = Paginator(historico(escopo, pk).prefetch_related('itens__contato', 'itens__contato_administradora'), 25).get_page(request.GET.get('pagina'))
        padrao = domain.atual(administradora_id=empresa_id) if empresa_id else None
        herdados = list(padrao.itens.select_related('contato_administradora')) if padrao and escopo == 'cliente' else []
        alcance = None
        if escopo == 'administradora':
            alcance = 0
            for v in domain.ClienteAdministradora.objects.filter(administradora_id=pk, data_fim__isnull=True):
                r = domain.atual(cliente_id=v.cliente_id)
                if not r or r.vinculo_id != v.pk or r.modo != 'substituir':
                    alcance += 1
        nomes_categorias = dict(boleto='boleto', nota_fiscal='nota fiscal', laudo='laudo', comunicado='comunicado', cobranca='cobrança')
        nomes_origens = dict(condominio='condomínio', padrao='padrão da administradora', especifico='específico do condomínio')
        for item in dados.get('efetivos', []):
            item['categorias'] = [nomes_categorias[c] for c in item['categorias']]
            item['origens'] = [nomes_origens[o] for o in item['origens']]
        contexto = dict(self.admin_site.each_context(request), title=f'Destinatários — {obj}', opts=self.model._meta, original=obj,
                        form=form, formset=formset, linhas=linhas, erro=erro, escopo=escopo, herdados=herdados,
                        revisoes=revisoes, encerramentos=encerramentos(escopo, pk)[:25], efetivos=dados.get('efetivos', []), alcance=alcance,
                        pode_editar=request.user.has_perm('clientes.change_configuracaodestinatarios'))
        return TemplateResponse(request, 'admin/clientes/destinatarios.html', contexto)