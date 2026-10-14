from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html

from . import destinatarios_fluxo as fluxo


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
        salvou, contexto = fluxo.tela(request, escopo, pk)
        if salvou:
            return redirect(request.path)
        contexto = dict(self.admin_site.each_context(request), title=f"Destinatários — {contexto['obj']}",
                        opts=self.model._meta, **contexto)
        return TemplateResponse(request, 'admin/clientes/destinatarios.html', contexto)
