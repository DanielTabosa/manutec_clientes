from rest_framework import serializers
from .models import ContatoAdministradora, Responsabilidade
from .models import Cliente, HistoricoCNPJ, Contato, Administradora, ClienteAdministradora
from .cnpj import normalizar_cnpj
from .services import cadastrar_cliente, ENDERECO_OBRIGATORIO
from django.core.exceptions import ValidationError as DjangoValidationError


class CNPJField(serializers.CharField):
    def to_internal_value(self, data):
        try:
            return normalizar_cnpj(super().to_internal_value(data))
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc


class AdministradoraSerializer(serializers.ModelSerializer):
    cnpj = CNPJField(max_length=18, allow_blank=True, allow_null=True, required=False)

    class Meta:
        model = Administradora
        fields = ["id", "cnpj", "razao_social", "nome_fantasia", "telefone", "email", "criado_em", "atualizado_em"]
        read_only_fields = ["id", "criado_em", "atualizado_em"]

    def validate_cnpj(self, value):
        value = value or None
        if value and Administradora.objects.filter(cnpj=value).exclude(pk=getattr(self.instance, "pk", None)).exists():
            raise serializers.ValidationError("Este CNPJ já pertence a uma administradora cadastrada.")
        return value


class VinculoAdministradoraSerializer(serializers.ModelSerializer):
    razao_social = serializers.CharField(source="administradora.razao_social", read_only=True)

    class Meta:
        model = ClienteAdministradora
        fields = ["id", "administradora", "razao_social", "data_inicio", "data_fim"]
        read_only_fields = fields


class AlterarAdministradoraSerializer(serializers.Serializer):
    acao = serializers.ChoiceField(choices=["vincular", "encerrar"])
    administradora = serializers.PrimaryKeyRelatedField(queryset=Administradora.objects.all(), required=False, allow_null=True)
    data = serializers.DateField()


class ContatoSerializer(serializers.ModelSerializer):
    vigente = serializers.SerializerMethodField()

    class Meta:
        model = Contato
        fields = ["id", "cliente", "nome", "funcao", "telefone", "email", "data_inicio", "data_fim", "vigente"]
        read_only_fields = ["id", "vigente"]

    def get_vigente(self, obj):
        return obj.data_fim is None

    def validate(self, attrs):
        if self.instance and "cliente" in attrs and attrs["cliente"].pk != self.instance.cliente_id:
            raise serializers.ValidationError({"cliente": "O contato não pode ser transferido para outro cliente. Cadastre um novo vínculo."})
        inicio = attrs.get("data_inicio", getattr(self.instance, "data_inicio", None))
        fim = attrs.get("data_fim", getattr(self.instance, "data_fim", None))
        try:
            Contato(data_inicio=inicio, data_fim=fim).clean()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict) from exc
        return attrs


class HistoricoCNPJSerializer(serializers.ModelSerializer):
    class Meta:
        model = HistoricoCNPJ
        fields = ["id", "cnpj", "data_inicio", "data_fim"]
        read_only_fields = fields


class TrocaCNPJSerializer(serializers.Serializer):
    cnpj = CNPJField(max_length=18)
    data_inicio = serializers.DateField()


class ClienteSerializer(serializers.ModelSerializer):
    cnpj = CNPJField(write_only=True, required=True, max_length=18)
    data_inicio = serializers.DateField(write_only=True, required=False)

    def validate(self, attrs):
        if self.instance:
            if "cnpj" in attrs or "data_inicio" in attrs:
                raise serializers.ValidationError({"cnpj": "Use a operação de troca de CNPJ para preservar o histórico."})
        else:
            errors = {campo: "Este campo é obrigatório." for campo in ENDERECO_OBRIGATORIO if not attrs.get(campo)}
            if errors:
                raise serializers.ValidationError(errors)
        return attrs

    def get_fields(self):
        fields = super().get_fields()
        if self.instance:
            fields["cnpj"].required = False
        return fields

    def create(self, validated_data):
        try:
            return cadastrar_cliente(**validated_data)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict if hasattr(exc, "message_dict") else {"cnpj": exc.messages}) from exc

    class Meta:
        model = Cliente
        fields = [
            "cnpj", "id", "razao_social", "nome_fantasia", "logradouro", "numero",
            "complemento", "bairro", "cidade", "estado", "cep", "observacoes",
            "criado_em", "atualizado_em", "data_inicio",
        ]
        read_only_fields = ["id", "criado_em", "atualizado_em"]


class ContatoAdministradoraSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContatoAdministradora
        fields = ["id", "administradora", "nome", "telefone", "email", "criado_em", "encerrado_em"]
        read_only_fields = ["id", "criado_em", "encerrado_em"]

    def create(self, validated_data):
        try:
            return super().create(validated_data)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict) from exc

    def update(self, instance, validated_data):
        try:
            return super().update(instance, validated_data)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict) from exc


class ResponsabilidadeSerializer(serializers.ModelSerializer):
    vigente = serializers.SerializerMethodField()

    class Meta:
        model = Responsabilidade
        fields = ["id", "contato_administradora", "cliente", "funcao", "data_inicio", "data_fim", "vigente"]
        read_only_fields = ["id", "vigente"]

    def get_vigente(self, obj):
        return obj.data_fim is None

    def create(self, validated_data):
        try:
            return super().create(validated_data)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict) from exc

    def update(self, instance, validated_data):
        from django.db import transaction
        try:
            with transaction.atomic():
                Cliente.objects.select_for_update().get(pk=instance.cliente_id)
                instance.refresh_from_db()
                return super().update(instance, validated_data)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict) from exc
