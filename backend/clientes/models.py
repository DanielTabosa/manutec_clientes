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

    def save(self, *args, **kwargs):
        from django.db import transaction
        with transaction.atomic():
            Cliente.objects.select_for_update().get(pk=self.cliente_id)
            anterior = type(self).objects.filter(pk=self.pk).first() if self.pk else None
            resultado = super().save(*args, **kwargs)
            if anterior and anterior.data_fim is None and self.data_fim is not None:
                from .destinatarios import registrar_encerramento_direto
                registrar_encerramento_direto(self)
            return resultado

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


class ContatoAdministradora(models.Model):
    encerrado_em = models.DateTimeField(null=True, blank=True, editable=False)
    id = models.BigAutoField(primary_key=True)
    administradora = models.ForeignKey(Administradora, on_delete=models.PROTECT, related_name="contatos")
    nome = models.CharField(max_length=150)
    telefone = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(max_length=150, blank=True, null=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = "contatos_administradora"
        ordering = ["nome", "id"]
        verbose_name = "contato de administradora"
        verbose_name_plural = "contatos de administradoras"

    def clean(self):
        super().clean()
        self.nome = (self.nome or "").strip()
        if not self.nome:
            raise ValidationError({"nome": "Informe o nome."})
        anterior = type(self).objects.filter(pk=self.pk).first() if self.pk else None
        if anterior and anterior.administradora_id != self.administradora_id:
            raise ValidationError({"administradora": "Não transfira o contato. Cadastre outro na nova empresa."})

    def save(self, *args, **kwargs):
        from django.db import transaction
        with transaction.atomic():
            Administradora.objects.select_for_update().get(pk=self.administradora_id)
            anterior = type(self).objects.filter(pk=self.pk).first() if self.pk else None
            if anterior and 'encerrado_em' not in (kwargs.get('update_fields') or ()):
                self.encerrado_em = anterior.encerrado_em
            self.full_clean()
            return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.nome} — {self.administradora}"


class Responsabilidade(models.Model):
    id = models.BigAutoField(primary_key=True)
    contato_administradora = models.ForeignKey(ContatoAdministradora, on_delete=models.PROTECT, related_name="responsabilidades")
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name="responsabilidades")
    funcao = models.CharField("função", max_length=100)
    data_inicio = models.DateField("data de início")
    data_fim = models.DateField("data de encerramento", blank=True, null=True)

    class Meta:
        managed = False
        db_table = "responsabilidades"
        ordering = ["-data_inicio", "-id"]
        verbose_name = "responsabilidade"
        verbose_name_plural = "responsabilidades"
        constraints = [models.CheckConstraint(
            condition=models.Q(data_fim__isnull=True) | models.Q(data_fim__gte=models.F("data_inicio")),
            name="chk_responsabilidade_datas")]

    def clean(self):
        from django.db import connection
        from django.utils import timezone
        super().clean()
        # O admin valida dentro de uma transação: mantém o bloqueio até salvar.
        if self.cliente_id and connection.in_atomic_block:
            Cliente.objects.select_for_update().filter(pk=self.cliente_id).first()
        self.funcao = (self.funcao or "").strip()
        if not self.funcao:
            raise ValidationError({"funcao": "Informe a função."})
        anterior = type(self).objects.filter(pk=self.pk).first() if self.pk else None
        if anterior:
            for campo in ("cliente", "contato_administradora"):
                if getattr(anterior, campo + "_id") != getattr(self, campo + "_id"):
                    raise ValidationError({campo: "Não substitua o vínculo salvo. Encerre e cadastre outro."})
        hoje = timezone.now().date()
        for campo in ("data_inicio", "data_fim"):
            valor = getattr(self, campo)
            if valor and valor > hoje:
                raise ValidationError({campo: "A data não pode estar no futuro."})
        if not self.data_inicio or not self.cliente_id or not self.contato_administradora_id:
            return
        if self.data_fim and self.data_fim < self.data_inicio:
            raise ValidationError({"data_fim": "O encerramento não pode ser anterior ao início."})
        contato = ContatoAdministradora.objects.filter(pk=self.contato_administradora_id).first()
        if not contato:
            return  # clean_fields informa FK inválida.
        vinculos = ClienteAdministradora.objects.filter(
            cliente_id=self.cliente_id, administradora_id=contato.administradora_id,
            data_inicio__lte=self.data_inicio)
        if self.data_fim is None:
            vinculos = vinculos.filter(data_fim__isnull=True)
        else:
            vinculos = vinculos.filter(models.Q(data_fim__isnull=True) | models.Q(data_fim__gte=self.data_fim))
        if not vinculos.exists():
            raise ValidationError({"data_inicio": "O período deve estar contido em um vínculo do cliente com a administradora do contato."})
        sobrepostos = type(self).objects.filter(
            cliente_id=self.cliente_id, contato_administradora_id=self.contato_administradora_id,
        ).exclude(pk=self.pk).filter(models.Q(data_fim__isnull=True) | models.Q(data_fim__gte=self.data_inicio))
        if self.data_fim:
            sobrepostos = sobrepostos.filter(data_inicio__lte=self.data_fim)
        if any(f.strip().casefold() == self.funcao.casefold() for f in sobrepostos.values_list("funcao", flat=True)):
            raise ValidationError({"funcao": "Já existe responsabilidade desta pessoa, cliente e função em período sobreposto."})

    def save(self, *args, **kwargs):
        from django.db import transaction
        with transaction.atomic():
            if self.cliente_id:
                Cliente.objects.select_for_update().get(pk=self.cliente_id)
            self.full_clean()
            return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.contato_administradora.nome} — {self.cliente} — {self.funcao}"


from .destinatarios_models import ConfiguracaoDestinatarios, RevisaoDestinatarios, ItemDestinatario  # noqa: E402,F401
