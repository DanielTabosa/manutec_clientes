import hashlib
import json

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import IntegrityError, transaction
from django.utils import timezone

from . import destinatarios
from .models import Cliente
from .preparacao_models import (PreparacaoEnvio, DocumentoPreparacao, DestinatarioPreparacao,
                                ItemPreparacao, NOMES_CATEGORIAS)

MAX_BYTES = 10 * 1024 * 1024
ORIGENS = dict(condominio='condomínio', padrao='padrão da administradora', especifico='específico do condomínio')


def texto_padrao(cliente):
    return (f'Documentos — {cliente}',
            f'Prezados,\n\nSeguem em anexo os documentos referentes aos serviços prestados ao {cliente}.\n\n'
            'Permanecemos à disposição.\n\nAtenciosamente,\nManutec Válvulas')


def criar(cliente_id, autor):
    cliente = Cliente.objects.get(pk=cliente_id)
    assunto, mensagem = texto_padrao(cliente)
    return PreparacaoEnvio.objects.create(cliente=cliente, criada_por=autor, assunto=assunto, mensagem=mensagem)


def _rascunho(preparacao_id):
    prep = PreparacaoEnvio.objects.select_for_update().get(pk=preparacao_id)
    if prep.status != 'rascunho':
        raise ValidationError('Esta preparação não é mais um rascunho.')
    return prep


def ler_pdf(upload):
    nome = upload.name or ''
    if not nome.lower().endswith('.pdf'):
        raise ValidationError(f'{nome}: somente arquivos PDF são aceitos.')
    if upload.size > MAX_BYTES:
        raise ValidationError(f'{nome}: o arquivo excede 10 MB.')
    dados = b''.join(upload.chunks())
    if len(dados) > MAX_BYTES:
        raise ValidationError(f'{nome}: o arquivo excede 10 MB.')
    if not dados.startswith(b'%PDF-') or b'%%EOF' not in dados[-1024:]:
        raise ValidationError(f'{nome}: o arquivo não parece ser um PDF completo.')
    return dados


@transaction.atomic
def anexar(preparacao_id, upload, categoria, referencia, autor):
    if categoria not in NOMES_CATEGORIAS:
        raise ValidationError('Escolha a categoria do documento.')
    dados = ler_pdf(upload)
    prep = _rascunho(preparacao_id)
    sha = hashlib.sha256(dados).hexdigest()
    if prep.documentos.filter(sha256=sha, removido_em__isnull=True).exists():
        raise ValidationError(f'{upload.name}: este mesmo arquivo já está anexado.')
    doc = DocumentoPreparacao(preparacao=prep, categoria=categoria, nome_original=upload.name[:200], tamanho=len(dados),
                              sha256=sha, referencia=(referencia or '').strip()[:120], anexado_por=autor)
    doc.arquivo.save('documento.pdf', ContentFile(dados), save=False)
    try:
        with transaction.atomic():
            doc.save()
    except IntegrityError:
        doc.arquivo.delete(save=False)
        raise ValidationError(f'{upload.name}: este mesmo arquivo já está anexado.')
    return doc


@transaction.atomic
def remover_documento(preparacao_id, documento_id):
    prep = _rascunho(preparacao_id)
    doc = prep.documentos.filter(pk=documento_id, removido_em__isnull=True).first()
    if not doc:
        raise ValidationError('Documento já removido ou inexistente.')
    doc.removido_em = timezone.now()
    doc.save(update_fields=['removido_em'])
    return doc


@transaction.atomic
def salvar_texto(preparacao_id, assunto, mensagem):
    prep = _rascunho(preparacao_id)
    prep.assunto, prep.mensagem = assunto.strip()[:200], mensagem
    prep.save(update_fields=['assunto', 'mensagem'])
    return prep


def plano(prep):
    """Destinatários atuais do cliente × documentos ativos, agrupados por e-mail."""
    docs = list(prep.documentos.filter(removido_em__isnull=True))
    por_email, sem_email, sem_anexo = {}, [], []
    for contato in destinatarios.efetivos(prep.cliente_id):
        aplicaveis = [d for d in docs if d.categoria in contato['categorias']]
        email = (contato['email'] or '').strip().lower()
        descricao = dict(nome=contato['nome'], origens=[ORIGENS[o] for o in contato['origens']],
                         categorias=[NOMES_CATEGORIAS[c] for c in contato['categorias']])
        if not email:
            sem_email.append(descricao)
            continue
        if not aplicaveis:
            sem_anexo.append(descricao)
            continue
        grupo = por_email.setdefault(email, dict(email=email, contatos=[], documentos=[]))
        grupo['contatos'].append(descricao)
        grupo['documentos'] += [d for d in aplicaveis if d not in grupo['documentos']]
    envios = sorted(por_email.values(), key=lambda g: g['email'])
    for g in envios:
        g['documentos'].sort(key=lambda d: d.pk)
        g['nomes'] = ', '.join(c['nome'] for c in g['contatos'])[:500]
    conflitos = []
    for g in envios:
        for d in g['documentos']:
            anterior = (ItemPreparacao.objects.filter(destinatario__email=g['email'], documento__sha256=d.sha256,
                                                       destinatario__preparacao__status='confirmada')
                        .exclude(destinatario__preparacao=prep)
                        .select_related('destinatario__preparacao').order_by('-destinatario__preparacao__confirmada_em').first())
            if anterior:
                conflitos.append(dict(email=g['email'], documento=d, preparacao=anterior.destinatario.preparacao))
    base = [[g['email'], [[d.pk, d.sha256] for d in g['documentos']]] for g in envios]
    impressao = hashlib.sha256(json.dumps(base).encode()).hexdigest()
    return dict(documentos=docs, envios=envios, sem_email=sem_email, sem_anexo=sem_anexo, conflitos=conflitos, impressao=impressao)


@transaction.atomic
def confirmar(preparacao_id, *, impressao, assunto, mensagem, autor, motivo_reenvio=''):
    cliente_id = PreparacaoEnvio.objects.values_list('cliente_id', flat=True).get(pk=preparacao_id)
    # Serializa confirmações do mesmo cliente para a checagem de reenvio.
    Cliente.objects.select_for_update().get(pk=cliente_id)
    prep = _rascunho(preparacao_id)
    assunto = assunto.strip()[:200]
    if not assunto or not mensagem.strip():
        raise ValidationError('Preencha o assunto e a mensagem.')
    atual = plano(prep)
    if not atual['documentos']:
        raise ValidationError('Anexe ao menos um documento.')
    if atual['impressao'] != impressao:
        raise ValidationError('Os documentos ou destinatários mudaram desde a conferência. Revise novamente antes de confirmar.')
    if not atual['envios']:
        raise ValidationError('Nenhum destinatário apto: confira os anexos e a configuração de destinatários.')
    motivo = (motivo_reenvio or '').strip()[:200]
    if atual['conflitos'] and not motivo:
        raise ValidationError('Há documentos já confirmados para os mesmos e-mails. Informe o motivo do reenvio ou remova-os.')
    reenvios = {(c['email'], c['documento'].pk) for c in atual['conflitos']}
    for g in atual['envios']:
        dest = DestinatarioPreparacao.objects.create(preparacao=prep, email=g['email'], nomes=g['nomes'])
        ItemPreparacao.objects.bulk_create([ItemPreparacao(destinatario=dest, documento=d, reenvio=(g['email'], d.pk) in reenvios)
                                            for d in g['documentos']])
    prep.assunto, prep.mensagem = assunto, mensagem
    prep.status, prep.confirmada_em, prep.confirmada_por = 'confirmada', timezone.now(), autor
    prep.motivo_reenvio = motivo if atual['conflitos'] else ''
    prep.save()
    return prep


@transaction.atomic
def cancelar(preparacao_id):
    prep = _rascunho(preparacao_id)
    prep.status, prep.cancelada_em = 'cancelada', timezone.now()
    prep.save(update_fields=['status', 'cancelada_em'])
    return prep


def envio_configurado():
    from django.conf import settings
    return bool(settings.EMAIL_HOST and settings.DEFAULT_FROM_EMAIL)


def enviar(preparacao_id, autor, incluir_indeterminados=False):
    """Envia aos destinatários pendentes ou com falha; cada um é marcado antes de sair para evitar duplicidade."""
    from django.conf import settings
    from django.core.mail import EmailMessage, get_connection
    from django.core.mail.message import make_msgid
    from django.db.models import F
    if not envio_configurado():
        raise ValidationError('Envio por e-mail não configurado. Informe os dados SMTP no .env do servidor.')
    estados = ['pendente', 'falha'] + (['enviando'] if incluir_indeterminados else [])
    agora = timezone.now()
    with transaction.atomic():
        prep = PreparacaoEnvio.objects.select_for_update().get(pk=preparacao_id)
        if prep.status != 'confirmada':
            raise ValidationError('Somente preparações confirmadas podem ser enviadas.')
        ids = list(prep.destinatarios.filter(status_envio__in=estados).values_list('pk', flat=True))
        if not ids:
            raise ValidationError('Nenhum destinatário pendente de envio.')
        DestinatarioPreparacao.objects.filter(pk__in=ids).update(status_envio='enviando', tentativas=F('tentativas') + 1,
                                                                 ultima_tentativa_em=agora, ultima_tentativa_por=autor, ultimo_erro='')
    resultado = dict(aceitos=0, falhas=0)

    def falhou(pks, exc):
        DestinatarioPreparacao.objects.filter(pk__in=pks).update(status_envio='falha', ultimo_erro=f'{type(exc).__name__}: {exc}'[:300])
        resultado['falhas'] += len(pks)

    conexao = get_connection(fail_silently=False)
    try:
        conexao.open()
    except Exception as exc:  # Falha de conexão/autenticação: nada saiu.
        falhou(ids, exc)
        return resultado
    try:
        dominio = settings.DEFAULT_FROM_EMAIL.rsplit('@', 1)[-1].strip('> ') or None
        for dest in DestinatarioPreparacao.objects.filter(pk__in=ids).prefetch_related('itens__documento'):
            message_id = make_msgid(domain=dominio)
            msg = EmailMessage(prep.assunto, prep.mensagem, settings.DEFAULT_FROM_EMAIL, [dest.email], connection=conexao,
                               reply_to=[settings.EMAIL_REPLY_TO] if settings.EMAIL_REPLY_TO else None,
                               headers={'Message-ID': message_id})
            try:
                for item in dest.itens.all():
                    with item.documento.arquivo.open('rb') as arquivo:
                        msg.attach(item.documento.nome_original, arquivo.read(), 'application/pdf')
                msg.send()
            except Exception as exc:
                falhou([dest.pk], exc)
                continue
            DestinatarioPreparacao.objects.filter(pk=dest.pk).update(status_envio='aceito', aceito_em=timezone.now(), message_id=message_id)
            resultado['aceitos'] += 1
    finally:
        try:
            conexao.close()
        except Exception:
            pass
    return resultado
