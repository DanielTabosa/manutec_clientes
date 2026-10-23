from rest_framework import serializers
from .models import ContatoAdministradora, Responsabilidade
from .models import Cliente, Endereco, HistoricoCNPJ, Contato, Administradora, ClienteAdministradora
from .cnpj import normalizar_cnpj
from .services import cadastrar_cliente, ENDERECO_CAMPOS, ENDERECO_OBRIGATORIO
from .cpf import normalizar_cpf
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


class EnderecoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Endereco
        fields = ["id", "cliente", "descricao", "principal", "ativo", "cep", "logradouro", "numero", "complemento",
                  "bairro", "cidade", "estado", "criado_em", "atualizado_em"]
        read_only_fields = ["id", "criado_em", "atualizado_em"]

    def validate(self, attrs):
        if self.instance and "cliente" in attrs and attrs["cliente"].pk != self.instance.cliente_id:
            raise serializers.ValidationError({"cliente": "O endereço não pode ser transferido para outro cliente."})
        if not self.instance:
            errors = {campo: "Este campo é obrigatório." for campo in ENDERECO_OBRIGATORIO if not attrs.get(campo)}
            if errors:
                raise serializers.ValidationError(errors)
        return attrs

    def _salvar(self, instance, validated_data):
        for campo, valor in validated_data.items():
            setattr(instance, campo, valor)
        try:
            instance.save()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict) from exc
        return instance

    def create(self, validated_data):
        return self._salvar(Endereco(), validated_data)

    def update(self, instance, validated_data):
        return self._salvar(instance, validated_data)


class ClienteSerializer(serializers.ModelSerializer):
    tipo_pessoa = serializers.ChoiceField(choices=Cliente.TIPOS_PESSOA, default=Cliente.PJ)
    cnpj = CNPJField(write_only=True, required=False, max_length=18)
    cpf = serializers.CharField(required=False, allow_null=True, allow_blank=True, max_length=14)
    data_inicio = serializers.DateField(write_only=True, required=False)
    enderecos = EnderecoSerializer(many=True, read_only=True)

    def get_fields(self):
        fields = super().get_fields()
        # Endereço informado no cadastro vira o endereço principal; depois, use /api/v1/enderecos/.
        do_endereco = EnderecoSerializer().get_fields()
        for campo in ENDERECO_CAMPOS:
            fields[campo] = do_endereco[campo]
            fields[campo].write_only, fields[campo].required = True, False
        return fields

    def validate_cpf(self, value):
        if not value:
            return None
        try:
            value = normalizar_cpf(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc
        if Cliente.objects.filter(cpf=value).exclude(pk=getattr(self.instance, "pk", None)).exists():
            raise serializers.ValidationError("Este CPF já pertence a um cliente cadastrado.")
        return value

    def validate(self, attrs):
        if self.instance:
            if "cnpj" in attrs or "data_inicio" in attrs:
                raise serializers.ValidationError({"cnpj": "Use a operação de troca de CNPJ para preservar o histórico."})
            if "tipo_pessoa" in self.initial_data and attrs.get("tipo_pessoa") != self.instance.tipo_pessoa:
                raise serializers.ValidationError({"tipo_pessoa": "O tipo de pessoa não muda depois do cadastro."})
            attrs.pop("tipo_pessoa", None)
            if any(campo in attrs for campo in ENDERECO_CAMPOS):
                raise serializers.ValidationError({"endereco": "Altere endereços em /api/v1/enderecos/."})
            if "cpf" in attrs and not self.instance.pessoa_fisica:
                if attrs["cpf"]:
                    raise serializers.ValidationError({"cpf": "Cliente pessoa jurídica não tem CPF."})
                attrs.pop("cpf")
            if self.instance.pessoa_fisica and "cpf" in attrs and not attrs["cpf"]:
                raise serializers.ValidationError({"cpf": "Informe o CPF da pessoa física."})
        else:
            errors = {campo: "Este campo é obrigatório." for campo in ENDERECO_OBRIGATORIO if not attrs.get(campo)}
            if attrs["tipo_pessoa"] == Cliente.PJ:
                if not attrs.get("cnpj"):
                    errors["cnpj"] = "Este campo é obrigatório."
                if attrs.get("cpf"):
                    errors["cpf"] = "Pessoa jurídica não tem CPF."
            else:
                if not attrs.get("cpf"):
                    errors["cpf"] = "Este campo é obrigatório."
                if attrs.get("cnpj"):
                    errors["cnpj"] = "Pessoa física não tem CNPJ."
            if errors:
                raise serializers.ValidationError(errors)
        return attrs

    def create(self, validated_data):
        try:
            return cadastrar_cliente(**validated_data)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict if hasattr(exc, "message_dict") else {"cnpj": exc.messages}) from exc

    def update(self, instance, validated_data):
        try:
            return super().update(instance, validated_data)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict) from exc

    class Meta:
        model = Cliente
        fields = [
            "id", "tipo_pessoa", "cnpj", "cpf", "razao_social", "nome_fantasia", "ativo", "observacoes",
            "enderecos", "criado_em", "atualizado_em", "data_inicio",
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
