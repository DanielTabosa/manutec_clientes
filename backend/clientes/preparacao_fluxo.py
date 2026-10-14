"""Ações e contexto da tela de preparação, compartilhados pelo admin e pela interface própria."""
from datetime import date

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.clickjacking import xframe_options_sameorigin

from . import preparacao as servico
from .preparacao_models import PreparacaoEnvio, NOMES_CATEGORIAS

ANCORAS = {'salvar_texto': '#revisao', 'confirmar': '#revisao', 'enviar': '#envio', 'reabrir': '#revisao', 'cancelar': ''}


def permissoes(user, prep):
    return dict(pode_editar=user.has_perm('clientes.add_preparacaoenvio') and prep.status == 'rascunho',
                pode_confirmar=user.has_perm('clientes.confirmar_preparacaoenvio') and prep.status == 'rascunho',
                pode_cancelar=user.has_perm('clientes.add_preparacaoenvio') and servico.pode_cancelar(prep),
                pode_reabrir=user.has_perm('clientes.confirmar_preparacaoenvio') and servico.pode_reabrir(prep))


def processar(request, prep):
    """Executa a ação do POST. Retorna (erros, boletos, ancora); `ancora` preenchida indica redirecionar."""
    acao = request.POST.get('acao')
    exigida = {'confirmar': 'confirmar_preparacaoenvio', 'reabrir': 'confirmar_preparacaoenvio', 'enviar': 'enviar_preparacaoenvio'}.get(acao, 'add_preparacaoenvio')
    if not request.user.has_perm('clientes.' + exigida):
        raise PermissionDenied
    try:
        resultado = executar(request, prep, acao)
    except ValidationError as exc:
        return exc.messages, None, None
    if isinstance(resultado, dict):
        return [], resultado['boletos'], None
    return [], None, ANCORAS.get(acao, '#documentos')


def executar(request, prep, acao):
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
        ja_enviados = prep.destinatarios.filter(status_envio='aceito').count()
        servico.cancelar(prep.pk)
        messages.success(request, 'Preparação cancelada. Registros e arquivos preservados.' + (
            f' {ja_enviados} e-mail(s) já aceito(s) não podem ser desfeitos e continuam no histórico.' if ja_enviados else ''))
    elif acao == 'reabrir':
        servico.reabrir(prep.pk)
        messages.success(request, 'Confirmação desfeita: a preparação voltou para rascunho. Corrija e confirme de novo.')
    else:
        raise ValidationError('Ação inválida.')


def contexto(request, prep, erros, boletos=None):
    prep.refresh_from_db()
    ctx = dict(prep=prep, erros=erros, boletos=boletos, categorias=NOMES_CATEGORIAS.items(),
               contaazul=bool(servico.contaazul_config()), **permissoes(request.user, prep))
    if prep.status == 'rascunho':
        ctx['plano'] = servico.plano(prep)
        if request.method == 'POST' and request.POST.get('acao') in ('salvar_texto', 'confirmar'):
            ctx.update(assunto=request.POST.get('assunto', ''), mensagem=request.POST.get('mensagem', ''),
                       motivo_reenvio=request.POST.get('motivo_reenvio', ''))
    else:
        confirmados = list(prep.destinatarios.prefetch_related('itens__documento'))
        por_status = {s: sum(1 for d in confirmados if d.status_envio == s) for s in ('pendente', 'enviando', 'aceito', 'falha')}
        ctx.update(confirmados=confirmados, documentos=prep.documentos.all(), por_status=por_status,
                   envio_configurado=servico.envio_configurado(),
                   pode_enviar=(prep.status == 'confirmada' and request.user.has_perm('clientes.enviar_preparacaoenvio')
                                and bool(por_status['pendente'] or por_status['falha'] or por_status['enviando'])))
    ctx.setdefault('assunto', prep.assunto)
    ctx.setdefault('mensagem', prep.mensagem)
    return ctx


@xframe_options_sameorigin  # permite o painel lateral de PDF do próprio sistema
def resposta_documento(prep_pk, doc_pk):
    prep = get_object_or_404(PreparacaoEnvio, pk=prep_pk)
    doc = get_object_or_404(prep.documentos, pk=doc_pk)
    resposta = FileResponse(doc.arquivo.open('rb'), content_type='application/pdf', filename=doc.nome_original)
    resposta['Cache-Control'] = 'private, no-store'
    return resposta


def situacao_envio(prep):
    if prep.status != 'confirmada':
        return ''
    estados = list(prep.destinatarios.values_list('status_envio', flat=True))
    aceitos = estados.count('aceito')
    return f'{aceitos}/{len(estados)} aceitos' + (' · pendências' if aceitos < len(estados) else '')
