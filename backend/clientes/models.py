from django.core.validators import RegexValidator
from django.db import models
from django.core.exceptions import ValidationError


class Cliente(models.Model):
    id = models.BigAutoField(primary_key=True)
    razao_social = models.CharField(max_length=150)
    nome_fantasia = models.CharField(max_length=150, blank=True, null=True)
    logradouro = models.CharField(max_length=150, blank=True, null=True)
    numero = models.CharField(max_length=20, blank=True, null=True)
    complemento = models.CharField(max_length=100, blank=True, null=True)
    bairro = models.CharField(max_length=100, blank=True, null=True)
    cidade = models.CharField(max_length=100, blank=True, null=True)
    estado = models.CharField(max_length=2, blank=True, null=True, choices=[
        (uf, uf) for uf in "AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO".split()
    ])
    cep = models.CharField(max_length=8, blank=True, null=True, validators=[
        RegexValidator(r"\A[0-9]{8}\Z", "Informe o CEP com exatamente 8 numeros.")
    ])
    observacoes = models.TextField(blank=True, null=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        # Tabela criada por database/schema.sql: Django nao deve recria-la.
        managed = False
        db_table = "clientes"
        ordering = ["razao_social", "id"]
        verbose_name = "cliente"
        verbose_name_plural = "clientes"

    def __str__(self):
        return self.razao_social


class HistoricoCNPJ(models.Model):
    id = models.BigAutoField(primary_key=True)
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name="historico_cnpj")
    cnpj = models.CharField(max_length=14, unique=True, validators=[
        RegexValidator(r"\A[A-Z0-9]{12}[0-9]{2}\Z", "Informe um CNPJ de 14 caracteres sem máscara.")
    ])
    data_inicio = models.DateField()
    data_fim = models.DateField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "historico_cnpj"
        ordering = ["-data_inicio", "-id"]
        verbose_name = "histórico de CNPJ"
        verbose_name_plural = "históricos de CNPJ"
        constraints = [
            models.UniqueConstraint(fields=["cliente"], condition=models.Q(data_fim__isnull=True), name="uq_historico_cnpj_atual"),
            models.CheckConstraint(condition=models.Q(data_fim__isnull=True) | models.Q(data_fim__gte=models.F("data_inicio")), name="chk_historico_cnpj_datas"),
        ]


class Contato(models.Model):
    id = models.BigAutoField(primary_key=True)
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name="contatos")
    nome = models.CharField("nome", max_length=150)
    funcao = models.CharField("função", max_length=100, blank=True, null=True)
    telefone = models.CharField("telefone", max_length=20, blank=True, null=True)
    email = models.EmailField("e-mail", max_length=150, blank=True, null=True)
    data_inicio = models.DateField("data de início")
    data_fim = models.DateField("data de encerramento", blank=True, null=True,
                                help_text="Deixe em branco enquanto o contato estiver vigente.")

    class Meta:
        managed = False
        db_table = "contatos"
        ordering = ["-data_inicio", "-id"]
        verbose_name = "contato do condomínio"
        verbose_name_plural = "contatos dos condomínios"
        constraints = [models.CheckConstraint(
            condition=models.Q(data_fim__isnull=True) | models.Q(data_fim__gte=models.F("data_inicio")),
            name="chk_contato_datas",
        )]

    def clean(self):
        super().clean()
        if self.data_inicio and self.data_fim and self.data_fim < self.data_inicio:
            raise ValidationError({"data_fim": "O encerramento não pode ser anterior ao início."})

    def __str__(self):
        return self.nome


class Administradora(models.Model):
    id = models.BigAutoField(primary_key=True)
    cnpj = models.CharField("CNPJ", max_length=14, unique=True, blank=True, null=True)
    razao_social = models.CharField("razão social", max_length=150)
    nome_fantasia = models.CharField("nome fantasia", max_length=150, blank=True, null=True)
    telefone = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField("e-mail", max_length=150, blank=True, null=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = "administradoras"
        ordering = ["razao_social", "id"]
        verbose_name = "administradora"
        verbose_name_plural = "administradoras"

    def clean(self):
        super().clean()
        from .cnpj import normalizar_cnpj
        if self.cnpj:
            try:
                self.cnpj = normalizar_cnpj(self.cnpj)
            except ValidationError as exc:
                raise ValidationError({"cnpj": exc.messages}) from exc
        else:
            self.cnpj = None

    def __str__(self):
        return self.razao_social


class ClienteAdministradora(models.Model):
    id = models.BigAutoField(primary_key=True)
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name="historico_administradoras")
    administradora = models.ForeignKey(Administradora, on_delete=models.PROTECT, related_name="vinculos")
    data_inicio = models.DateField("data de início")
    data_fim = models.DateField("data de encerramento", blank=True, null=True)

    class Meta:
        managed = False
        db_table = "cliente_administradora"
        ordering = ["-data_inicio", "-id"]
        verbose_name = "vínculo de administradora"
        verbose_name_plural = "histórico de administradoras"
        constraints = [
            models.UniqueConstraint(fields=["cliente"], condition=models.Q(data_fim__isnull=True), name="uq_cliente_administradora_atual"),
            models.CheckConstraint(condition=models.Q(data_fim__isnull=True) | models.Q(data_fim__gte=models.F("data_inicio")), name="chk_cliente_administradora_datas"),
        ]

    def __str__(self):
        return str(self.administradora)
