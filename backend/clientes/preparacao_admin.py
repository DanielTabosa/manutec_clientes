from django import forms
from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse

from . import preparacao as servico
from . import preparacao_fluxo as fluxo
from .preparacao_models import PreparacaoEnvio


class NovaPreparacaoForm(forms.ModelForm):
    class Meta:
        model = PreparacaoEnvio
        fields = ['cliente']


@admin.register(PreparacaoEnvio)
class PreparacaoEnvioAdmin(admin.ModelAdmin):
    form = NovaPreparacaoForm
    autocomplete_fields = ['cliente']
    list_display = ['id', 'cliente', 'status', 'situacao_envio', 'criada_em', 'criada_por', 'confirmada_em']
    list_filter = ['status']
    search_fields = ['cliente__razao_social', 'cliente__nome_fantasia']
    list_select_related = ['cliente', 'criada_por']

    @admin.display(description='Envio')
    def situacao_envio(self, obj):
        return fluxo.situacao_envio(obj) or '—'

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_urls(self):
        return [path('<int:pk>/documento/<int:doc_pk>/', self.admin_site.admin_view(self.documento_view),
                     name='clientes_preparacaoenvio_documento')] + super().get_urls()

    def add_view(self, request, form_url='', extra_context=None):
        extra = dict(extra_context or {}, show_save_and_add_another=False, show_save_and_continue=False,
                     title='Nova preparação de envio')
        return super().add_view(request, form_url, extra)

    def save_model(self, request, obj, form, change):
        obj.criada_por = request.user
        obj.assunto, obj.mensagem = servico.texto_padrao(obj.cliente)
        super().save_model(request, obj, form, change)

    def response_add(self, request, obj, post_url_continue=None):
        return redirect('admin:clientes_preparacaoenvio_change', obj.pk)

    def change_view(self, request, object_id, form_url='', extra_context=None):
        if not self.has_view_permission(request):
            raise PermissionDenied
        try:
            pk = int(object_id)
        except ValueError:
            raise Http404
        prep = get_object_or_404(PreparacaoEnvio.objects.select_related('cliente'), pk=pk)
        erros, boletos = [], None
        if request.method == 'POST':
            erros, boletos, ancora = fluxo.processar(request, prep)
            if ancora:
                return redirect(request.path + ancora)
        contexto = dict(self.admin_site.each_context(request), opts=self.model._meta, original=prep,
                        title=f'Preparação {prep.pk} — {prep.cliente}',
                        destinatarios_url=reverse('admin:clientes_cliente_destinatarios', args=[prep.cliente_id]),
                        **fluxo.contexto(request, prep, erros, boletos))
        return TemplateResponse(request, 'admin/clientes/preparacao.html', contexto)

    def documento_view(self, request, pk, doc_pk):
        if not self.has_view_permission(request):
            raise PermissionDenied
        return fluxo.resposta_documento(pk, doc_pk)
