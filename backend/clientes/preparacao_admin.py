from datetime import date

from django import forms
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse

from . import preparacao as servico
from .preparacao_models import PreparacaoEnvio, NOMES_CATEGORIAS


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
        if obj.status != 'confirmada':
            return '—'
        estados = list(obj.destinatarios.values_list('status_envio', flat=True))
        aceitos = estados.count('aceito')
        return f'{aceitos}/{len(estados)} aceitos' + (' · pendências' if aceitos < len(estados) else '')

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
        pode_editar = request.user.has_perm('clientes.add_preparacaoenvio')
        pode_confirmar = request.user.has_perm('clientes.confirmar_preparacaoenvio')
        erros = []
        if request.method == 'POST':
            acao = request.POST.get('acao')
            exigida = dict(confirmar=pode_confirmar, enviar=request.user.has_perm('clientes.enviar_preparacaoenvio')).get(acao, pode_editar)
            if not exigida:
                raise PermissionDenied
            try:
                resultado = self._executar(request, prep, acao)
            except ValidationError as exc:
                erros = exc.messages
            else:
                if isinstance(resultado, dict):
                    return self._pagina(request, prep, pode_editar, pode_confirmar, erros, boletos=resultado['boletos'])
                return redirect(request.path + {'salvar_texto': '#revisao', 'confirmar': '#revisao', 'enviar': '#envio'}.get(acao, '#documentos'))
        return self._pagina(request, prep, pode_editar, pode_confirmar, erros)

    def _pagina(self, request, prep, pode_editar, pode_confirmar, erros, boletos=None):
        prep.refresh_from_db()
        contexto = dict(self.admin_site.each_context(request), boletos=boletos, opts=self.model._meta, original=prep, prep=prep,
                        title=f'Preparação {prep.pk} — {prep.cliente}', erros=erros, categorias=NOMES_CATEGORIAS.items(),
                        pode_editar=pode_editar and prep.status == 'rascunho',
                        pode_confirmar=pode_confirmar and prep.status == 'rascunho',
                        destinatarios_url=reverse('admin:clientes_cliente_destinatarios', args=[prep.cliente_id]),
                        contaazul=bool(servico.contaazul_config()))
        if prep.status == 'rascunho':
            contexto['plano'] = servico.plano(prep)
            if request.method == 'POST' and request.POST.get('acao') in ('salvar_texto', 'confirmar'):
                contexto.update(assunto=request.POST.get('assunto', ''), mensagem=request.POST.get('mensagem', ''),
                                motivo_reenvio=request.POST.get('motivo_reenvio', ''))
        else:
            confirmados = list(prep.destinatarios.prefetch_related('itens__documento'))
            por_status = {s: sum(1 for d in confirmados if d.status_envio == s) for s in ('pendente', 'enviando', 'aceito', 'falha')}
            contexto.update(confirmados=confirmados, documentos=prep.documentos.all(), por_status=por_status,
                            envio_configurado=servico.envio_configurado(),
                            pode_enviar=(prep.status == 'confirmada' and request.user.has_perm('clientes.enviar_preparacaoenvio')
                                         and bool(por_status['pendente'] or por_status['falha'] or por_status['enviando'])))
        contexto.setdefault('assunto', prep.assunto)
        contexto.setdefault('mensagem', prep.mensagem)
        return TemplateResponse(request, 'admin/clientes/preparacao.html', contexto)

    def _executar(self, request, prep, acao):
        post = request.POST
        if acao == 'anexar':
            arquivos = request.FILES.getlist('arquivos')
            if not arquivos:
                raise ValidationError('Escolha ao menos um PDF.')
            falhas, anexados = [], 0
            for arquivo in arquivos:
                try:
                    servico.anexar(prep.pk, arquivo, post.get('categoria'), post.get('referencia'), request.user)
                    anexados += 1
                except ValidationError as exc:
                    falhas += exc.messages
            if anexados:
                messages.success(request, f'{anexados} documento(s) anexado(s).')
            if falhas:
                raise ValidationError(falhas)
        elif acao == 'listar_boletos':
            try:
                vencimento = date.fromisoformat(post.get('vencimento', ''))
            except ValueError:
                raise ValidationError('Informe a data de vencimento do boleto.')
            valor = servico.ler_valor(post['valor']) if post.get('valor', '').strip() else None
            return {'boletos': dict(vencimento=vencimento, valor=post.get('valor', '').strip(),
                                    contas=servico.listar_boletos(prep.pk, vencimento, valor))}
        elif acao == 'boleto_parcela':
            doc = servico.importar_boleto_parcela(prep.pk, post.get('parcela', ''), request.user)
            messages.success(request, f'Boleto do Conta Azul anexado ({doc.referencia}). Visualize e confira se é deste cliente.')
        elif acao == 'zip_nfse':
            arquivo = request.FILES.get('zip')
            if not arquivo:
                raise ValidationError('Escolha o ZIP de NFS-e baixado do Conta Azul.')
            try:
                ano, mes = (int(x) for x in post.get('competencia', '').split('-'))
                competencia = date(ano, mes, 1)
            except ValueError:
                raise ValidationError('Informe a competência (mês e ano) das notas.')
            r = servico.importar_nfse_zip(prep.pk, arquivo, competencia, request.user)
            if r['anexadas']:
                messages.success(request, f"{len(r['anexadas'])} NFS-e anexada(s): {', '.join(map(str, r['anexadas']))}. "
                                          f"{r['outros_tomadores']} nota(s) de outros tomadores ignorada(s). Visualize e confira.")
            if r['pendentes']:
                raise ValidationError([f'NFS-e {n}: {motivo} — não anexada.' for n, motivo in r['pendentes']])
            if not r['anexadas']:
                raise ValidationError('Nenhuma NFS-e anexada.')
        elif acao == 'remover':
            doc = servico.remover_documento(prep.pk, post.get('documento'))
            messages.success(request, f'{doc.nome_original} removido desta preparação.')
        elif acao == 'salvar_texto':
            servico.salvar_texto(prep.pk, post.get('assunto', ''), post.get('mensagem', ''))
            messages.success(request, 'Texto salvo.')
        elif acao == 'confirmar':
            if post.get('conferido') != 'sim':
                raise ValidationError('Marque a conferência dos destinatários e anexos antes de confirmar.')
            servico.confirmar(prep.pk, impressao=post.get('impressao', ''), assunto=post.get('assunto', ''),
                              mensagem=post.get('mensagem', ''), motivo_reenvio=post.get('motivo_reenvio', ''), autor=request.user)
            messages.success(request, 'Preparação confirmada. Nenhuma mensagem foi enviada ainda: confira e use Enviar e-mails.')
        elif acao == 'enviar':
            r = servico.enviar(prep.pk, request.user, incluir_indeterminados=post.get('incluir_indeterminados') == 'sim')
            if r['aceitos']:
                messages.success(request, f"{r['aceitos']} e-mail(s) aceito(s) pelo servidor. Aceitação não comprova entrega na caixa do destinatário.")
            if r['falhas']:
                raise ValidationError(f"{r['falhas']} envio(s) falharam; veja o motivo na tabela. Você pode tentar novamente.")
        elif acao == 'cancelar':
            servico.cancelar(prep.pk)
            messages.success(request, 'Preparação cancelada. Registros e arquivos preservados.')
        else:
            raise ValidationError('Ação inválida.')

    def documento_view(self, request, pk, doc_pk):
        if not self.has_view_permission(request):
            raise PermissionDenied
        prep = get_object_or_404(PreparacaoEnvio, pk=pk)
        doc = get_object_or_404(prep.documentos, pk=doc_pk)
        resposta = FileResponse(doc.arquivo.open('rb'), content_type='application/pdf', filename=doc.nome_original)
        resposta['Cache-Control'] = 'private, no-store'
        return resposta
