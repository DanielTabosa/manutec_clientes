import os
import uuid

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.db import models

from .destinatarios_models import CATEGORIAS

STATUS = [('rascunho', 'Rascunho'), ('confirmada', 'Confirmada'), ('cancelada', 'Cancelada')]
NOMES_CATEGORIAS = dict(boleto='Boleto', nota_fiscal='Nota fiscal', laudo='Laudo', comunicado='Comunicado', cobranca='Cobrança')


class ArmazenamentoPrivado(FileSystemStorage):
    """PDFs fora de MEDIA/STATIC: servidos apenas pela view autenticada do painel."""
    @property
    def base_location(self):
        return str(settings.ARQUIVOS_PRIVADOS_DIR)

    @property
    def location(self):
        return os.path.abspath(self.base_location)


_armazenamento = ArmazenamentoPrivado()


def armazenamento_privado():
    return _armazenamento


def caminho_documento(instance, filename):
    return f'preparacoes/{instance.preparacao_id}/{uuid.uuid4().hex}.pdf'


class PreparacaoEnvio(models.Model):
    cliente = models.ForeignKey('Cliente', on_delete=models.PROTECT, related_name='preparacoes_envio')
    status = models.CharField(max_length=12, choices=STATUS, default='rascunho')
    assunto = models.CharField(max_length=200, blank=True)
    mensagem = models.TextField(blank=True)
    criada_em = models.DateTimeField(auto_now_add=True)
    criada_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='+')
    confirmada_em = models.DateTimeField(null=True, blank=True)
    confirmada_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    cancelada_em = models.DateTimeField(null=True, blank=True)
    motivo_reenvio = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ['-criada_em', '-id']
        default_permissions = ('view', 'add')
        permissions = [('confirmar_preparacaoenvio', 'Pode confirmar preparação de envio')]
        verbose_name = 'preparação de envio'
        verbose_name_plural = 'preparações de envio'
        constraints = [
            models.CheckConstraint(condition=models.Q(status__in=['rascunho', 'confirmada', 'cancelada']), name='prep_status_valido'),
            models.CheckConstraint(condition=~models.Q(status='confirmada') | models.Q(confirmada_em__isnull=False), name='prep_confirmacao_datada'),
        ]

    def __str__(self):
        return f'Preparação {self.pk} — {self.cliente}'


class DocumentoPreparacao(models.Model):
    preparacao = models.ForeignKey(PreparacaoEnvio, on_delete=models.PROTECT, related_name='documentos')
    categoria = models.CharField(max_length=12, choices=[(c, NOMES_CATEGORIAS[c]) for c in CATEGORIAS])
    arquivo = models.FileField(storage=armazenamento_privado, upload_to=caminho_documento, max_length=200)
    nome_original = models.CharField(max_length=200)
    tamanho = models.PositiveIntegerField()
    sha256 = models.CharField(max_length=64)
    referencia = models.CharField(max_length=120, blank=True)
    anexado_em = models.DateTimeField(auto_now_add=True)
    anexado_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='+')
    # Remoção no rascunho preserva arquivo e registro.
    removido_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['id']
        default_permissions = ()
        constraints = [
            models.UniqueConstraint(fields=['preparacao', 'sha256'], condition=models.Q(removido_em__isnull=True), name='prep_documento_unico'),
            models.CheckConstraint(condition=models.Q(categoria__in=list(CATEGORIAS)), name='prep_categoria_valida'),
        ]


class DestinatarioPreparacao(models.Model):
    """Retrato no momento da confirmação; não acompanha mudanças posteriores do cadastro."""
    preparacao = models.ForeignKey(PreparacaoEnvio, on_delete=models.PROTECT, related_name='destinatarios')
    email = models.CharField(max_length=254)
    nomes = models.CharField(max_length=500)

    class Meta:
        ordering = ['email']
        default_permissions = ()
        constraints = [models.UniqueConstraint(fields=['preparacao', 'email'], name='prep_email_unico')]


class ItemPreparacao(models.Model):
    destinatario = models.ForeignKey(DestinatarioPreparacao, on_delete=models.PROTECT, related_name='itens')
    documento = models.ForeignKey(DocumentoPreparacao, on_delete=models.PROTECT, related_name='itens')
    reenvio = models.BooleanField(default=False)

    class Meta:
        ordering = ['id']
        default_permissions = ()
        constraints = [models.UniqueConstraint(fields=['destinatario', 'documento'], name='prep_item_unico')]
