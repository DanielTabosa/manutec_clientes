from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.functions import Lower

SITUACOES = [('ativo', 'Ativo'), ('suspenso', 'Suspenso'), ('inativo', 'Inativo')]


class TipoContrato(models.Model):
    """Lista de tipos mantida pelo usuário na tela; tipos em uso não são apagados, só desativados."""
    nome = models.CharField('nome', max_length=100)
    descricao = models.CharField('descrição', max_length=255, blank=True)
    ativo = models.BooleanField('disponível para novos contratos', default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['nome']
        default_permissions = ('view', 'add', 'change')
        verbose_name = 'tipo de contrato'
        verbose_name_plural = 'tipos de contrato'
        constraints = [models.UniqueConstraint(Lower('nome'), name='tipo_contrato_nome_unico')]

    def __str__(self):
        return self.nome


class Contrato(models.Model):
    """Contrato do cliente cadastrado na base. Um cliente pode ter vários contratos, de tipos diferentes."""
    cliente = models.ForeignKey('Cliente', on_delete=models.PROTECT, related_name='contratos')
    tipo = models.ForeignKey(TipoContrato, on_delete=models.PROTECT, related_name='contratos', verbose_name='tipo')
    situacao = models.CharField('situação', max_length=10, choices=SITUACOES, default='ativo')
    data_inicio = models.DateField('início')
    data_fim = models.DateField('fim', null=True, blank=True)
    identificador = models.CharField('número ou referência', max_length=60, blank=True,
                                     help_text='Opcional. Ex.: número do contrato no Conta Azul.')
    observacoes = models.TextField('observações', blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['cliente_id', '-data_inicio', '-id']
        default_permissions = ('view', 'add', 'change')
        verbose_name = 'contrato'
        verbose_name_plural = 'contratos'
        constraints = [
            models.CheckConstraint(condition=models.Q(situacao__in=['ativo', 'suspenso', 'inativo']), name='contrato_situacao_valida'),
            models.CheckConstraint(condition=models.Q(data_fim__isnull=True) | models.Q(data_fim__gte=models.F('data_inicio')),
                                   name='contrato_datas_validas'),
        ]

    def clean(self):
        super().clean()
        if self.data_inicio and self.data_fim and self.data_fim < self.data_inicio:
            raise ValidationError({'data_fim': 'O fim não pode ser anterior ao início.'})
        if self.tipo_id and not self.pk and not TipoContrato.objects.filter(pk=self.tipo_id, ativo=True).exists():
            raise ValidationError({'tipo': 'Este tipo de contrato não está mais disponível para novos contratos.'})

    def __str__(self):
        return f'{self.tipo} — {self.cliente}'
