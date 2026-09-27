from django.conf import settings
from django.db import models

CATEGORIAS = ('boleto', 'nota_fiscal', 'laudo', 'comunicado', 'cobranca')


class ConfiguracaoDestinatarios(models.Model):
    cliente = models.OneToOneField('Cliente', null=True, blank=True, on_delete=models.PROTECT)
    administradora = models.OneToOneField('Administradora', null=True, blank=True, on_delete=models.PROTECT)

    class Meta:
        constraints = [models.CheckConstraint(condition=(models.Q(cliente__isnull=False, administradora__isnull=True) | models.Q(cliente__isnull=True, administradora__isnull=False)), name='dest_titular_exclusivo')]
        default_permissions = ('view', 'change')
        verbose_name = 'configuração de destinatários'


class RevisaoDestinatarios(models.Model):
    configuracao = models.ForeignKey(ConfiguracaoDestinatarios, on_delete=models.PROTECT, related_name='revisoes')
    numero = models.PositiveIntegerField()
    registrado_em = models.DateTimeField(auto_now_add=True)
    autor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    modo = models.CharField(max_length=12, choices=[('usar', 'Usar padrão'), ('complementar', 'Complementar padrão'), ('substituir', 'Substituir padrão')], default='usar')
    vinculo = models.ForeignKey('ClienteAdministradora', null=True, blank=True, on_delete=models.PROTECT)
    motivo = models.CharField(max_length=80, default='Configuração alterada')

    class Meta:
        ordering = ['-numero']
        default_permissions = ()
        constraints = [models.UniqueConstraint(fields=['configuracao', 'numero'], name='dest_revisao_unica'), models.CheckConstraint(condition=models.Q(modo__in=['usar', 'complementar', 'substituir']), name='dest_modo_valido')]


class ItemDestinatario(models.Model):
    revisao = models.ForeignKey(RevisaoDestinatarios, on_delete=models.PROTECT, related_name='itens')
    contato = models.ForeignKey('Contato', null=True, blank=True, on_delete=models.PROTECT)
    contato_administradora = models.ForeignKey('ContatoAdministradora', null=True, blank=True, on_delete=models.PROTECT)
    encerrado_local = models.BooleanField(default=False)
    boleto = models.BooleanField(default=False)
    nota_fiscal = models.BooleanField(default=False)
    laudo = models.BooleanField(default=False)
    comunicado = models.BooleanField(default=False)
    cobranca = models.BooleanField(default=False)

    class Meta:
        default_permissions = ()
        constraints = [
            models.CheckConstraint(condition=(models.Q(contato__isnull=False, contato_administradora__isnull=True) | models.Q(contato__isnull=True, contato_administradora__isnull=False)), name='dest_contato_exclusivo'),
            models.UniqueConstraint(fields=['revisao', 'contato'], name='dest_direto_unico'),
            models.UniqueConstraint(fields=['revisao', 'contato_administradora'], name='dest_empresa_unico'),
            models.CheckConstraint(condition=(models.Q(encerrado_local=False) & (models.Q(boleto=True) | models.Q(nota_fiscal=True) | models.Q(laudo=True) | models.Q(comunicado=True) | models.Q(cobranca=True))) | models.Q(encerrado_local=True, contato__isnull=True, boleto=False, nota_fiscal=False, laudo=False, comunicado=False, cobranca=False), name='dest_categorias_validas'),
        ]