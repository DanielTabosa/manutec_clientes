from rest_framework import filters, mixins, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, ValidationError
from django.core.exceptions import ValidationError as DjangoValidationError
from .services import trocar_cnpj
from .serializers import ContatoAdministradoraSerializer, ResponsabilidadeSerializer
from .serializers import HistoricoCNPJSerializer, TrocaCNPJSerializer
from .models import ContatoAdministradora, Responsabilidade
from .models import Cliente, Contato
from .serializers import ClienteSerializer, ContatoSerializer
from .models import Administradora
from .serializers import AdministradoraSerializer, VinculoAdministradoraSerializer, AlterarAdministradoraSerializer
from .services import alterar_administradora
from django.db import IntegrityError, transaction


class ClienteViewSet(mixins.CreateModelMixin, mixins.ListModelMixin,
                     mixins.RetrieveModelMixin, mixins.UpdateModelMixin,
                     viewsets.GenericViewSet):
    queryset = Cliente.objects.all()
    serializer_class = ClienteSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ["razao_social", "nome_fantasia", "cidade"]
    # Exclusao nao faz parte desta primeira API para preservar historicos.

    @action(detail=True, methods=["get", "post"])
    def administradora(self, request, pk=None):
        cliente = self.get_object()
        if request.method == "GET":
            registros = list(cliente.historico_administradoras.select_related("administradora"))
            atual = next((r for r in registros if r.data_fim is None), None)
            return Response({"atual": VinculoAdministradoraSerializer(atual).data if atual else None,
                             "historico": VinculoAdministradoraSerializer(registros, many=True).data})
        serializer = AlterarAdministradoraSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            vinculo = alterar_administradora(cliente.pk, **serializer.validated_data)
        except DjangoValidationError as exc:
            raise ValidationError(exc.message_dict) from exc
        return Response(VinculoAdministradoraSerializer(vinculo).data, status=201 if serializer.validated_data["acao"] == "vincular" else 200)

    @action(detail=True, methods=["get", "post"], url_path="cnpj")
    def cnpj(self, request, pk=None):
        cliente = self.get_object()
        if request.method == "GET":
            registros = list(cliente.historico_cnpj.all())
            atual = next((r for r in registros if r.data_fim is None), None)
            return Response({"atual": HistoricoCNPJSerializer(atual).data if atual else None,
                             "historico": HistoricoCNPJSerializer(registros, many=True).data})
        if not request.user.has_perm("clientes.change_cliente"):
            raise PermissionDenied()
        serializer = TrocaCNPJSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            registro = trocar_cnpj(cliente.pk, **serializer.validated_data)
        except DjangoValidationError as exc:
            raise ValidationError(exc.message_dict) from exc
        return Response(HistoricoCNPJSerializer(registro).data, status=201)


class ContatoViewSet(mixins.CreateModelMixin, mixins.ListModelMixin,
                     mixins.RetrieveModelMixin, mixins.UpdateModelMixin,
                     viewsets.GenericViewSet):
    queryset = Contato.objects.select_related("cliente").all()
    serializer_class = ContatoSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ["nome", "funcao", "cliente__razao_social"]

    def get_queryset(self):
        queryset = super().get_queryset()
        cliente = self.request.query_params.get("cliente")
        if cliente is not None:
            if not cliente.isascii() or not cliente.isdigit() or len(cliente) > 18:
                raise ValidationError({"cliente": "Informe o ID numérico do cliente."})
            queryset = queryset.filter(cliente_id=int(cliente))
        vigente = self.request.query_params.get("vigente")
        if vigente is not None:
            if vigente not in ("true", "false"):
                raise ValidationError({"vigente": "Use true para atuais ou false para encerrados."})
            queryset = queryset.filter(data_fim__isnull=vigente == "true")
        return queryset


class AdministradoraViewSet(mixins.CreateModelMixin, mixins.ListModelMixin,
                           mixins.RetrieveModelMixin, mixins.UpdateModelMixin,
                           viewsets.GenericViewSet):
    queryset = Administradora.objects.all()
    serializer_class = AdministradoraSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ["razao_social", "nome_fantasia", "cnpj"]

    def salvar(self, serializer):
        try:
            with transaction.atomic():
                serializer.save()
        except IntegrityError as exc:
            raise ValidationError({"cnpj": "CNPJ já cadastrado. Atualize a consulta."}) from exc

    perform_create = salvar
    perform_update = salvar


class ContatoAdministradoraViewSet(mixins.CreateModelMixin, mixins.ListModelMixin,
                                  mixins.RetrieveModelMixin, mixins.UpdateModelMixin,
                                  viewsets.GenericViewSet):
    queryset = ContatoAdministradora.objects.select_related("administradora")
    serializer_class = ContatoAdministradoraSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ["nome", "administradora__razao_social"]

    def get_queryset(self):
        qs = super().get_queryset()
        valor = self.request.query_params.get("administradora")
        if valor is not None:
            if not valor.isascii() or not valor.isdigit() or len(valor) > 18:
                raise ValidationError({"administradora": "Informe um ID numérico."})
            qs = qs.filter(administradora_id=int(valor))
        return qs


class ResponsabilidadeViewSet(mixins.CreateModelMixin, mixins.ListModelMixin,
                              mixins.RetrieveModelMixin, mixins.UpdateModelMixin,
                              viewsets.GenericViewSet):
    queryset = Responsabilidade.objects.select_related("cliente", "contato_administradora__administradora")
    serializer_class = ResponsabilidadeSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ["funcao", "contato_administradora__nome", "cliente__razao_social"]

    def get_queryset(self):
        qs = super().get_queryset()
        for campo in ("cliente", "contato_administradora"):
            valor = self.request.query_params.get(campo)
            if valor is not None:
                if not valor.isascii() or not valor.isdigit() or len(valor) > 18:
                    raise ValidationError({campo: "Informe um ID numérico."})
                qs = qs.filter(**{campo + "_id": int(valor)})
        vigente = self.request.query_params.get("vigente")
        if vigente is not None:
            if vigente not in ("true", "false"):
                raise ValidationError({"vigente": "Use true ou false."})
            qs = qs.filter(data_fim__isnull=vigente == "true")
        return qs
