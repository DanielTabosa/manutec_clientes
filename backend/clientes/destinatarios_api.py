from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.pagination import PageNumberPagination
from .models import Cliente, Administradora, ContatoAdministradora, RevisaoDestinatarios
from . import destinatarios as domain
from .destinatarios_models import CATEGORIAS


class ItemSerializer(serializers.Serializer):
    contato_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    contato_administradora_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    encerrado_local = serializers.BooleanField(default=False)
    boleto = serializers.BooleanField(default=False)
    nota_fiscal = serializers.BooleanField(default=False)
    laudo = serializers.BooleanField(default=False)
    comunicado = serializers.BooleanField(default=False)
    cobranca = serializers.BooleanField(default=False)


class ConfigSerializer(serializers.Serializer):
    numero = serializers.IntegerField(min_value=0)
    vinculo_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    modo = serializers.ChoiceField(choices=['usar', 'complementar', 'substituir'], default='usar')
    itens = ItemSerializer(many=True)


def exigir(user, escopo, escrita=False):
    perms = ['clientes.view_configuracaodestinatarios', 'clientes.view_' + escopo]
    perms += ['clientes.view_contatoadministradora']
    if escopo == 'cliente':
        perms += ['clientes.view_contato', 'clientes.view_administradora']
    if escrita:
        perms += ['clientes.change_configuracaodestinatarios']
    if not user.has_perms(perms):
        raise PermissionDenied()


def serializar_revisao(r):
    return dict(numero=r.numero, registrado_em=r.registrado_em, autor_id=r.autor_id, modo=r.modo,
                vinculo_id=r.vinculo_id, motivo=r.motivo, itens=domain.itens_da_revisao(r))


def estado(escopo, pk):
    r = domain.atual(**{escopo + '_id': pk})
    dados = serializar_revisao(r) if r else dict(numero=0, modo='usar', vinculo_id=None, itens=[])
    if escopo == 'cliente':
        v = domain.ClienteAdministradora.objects.filter(cliente_id=pk, data_fim__isnull=True).first()
        dados['vinculo_id'] = v.pk if v else None
        if not r or r.vinculo_id != dados['vinculo_id']:
            dados['modo'] = 'usar'
            dados['itens'] = [i for i in dados['itens'] if i['contato_id']]
        dados['efetivos'] = domain.efetivos(pk)
    return dados


class DestinatariosView(APIView):
    permission_classes = [IsAuthenticated]

    def titular(self, request, escopo, pk, escrita=False):
        exigir(request.user, escopo, escrita)
        return get_object_or_404(Cliente if escopo == 'cliente' else Administradora, pk=pk)

    def get(self, request, escopo, pk):
        self.titular(request, escopo, pk)
        return Response(estado(escopo, pk))

    def put(self, request, escopo, pk):
        self.titular(request, escopo, pk, True)
        s = ConfigSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        try:
            domain.salvar(**{escopo + '_id': pk}, autor=request.user, **s.validated_data)
        except DjangoValidationError as exc:
            raise ValidationError(exc.message_dict) from exc
        return Response(estado(escopo, pk))


class HistoricoDestinatariosView(DestinatariosView):
    http_method_names = ['get', 'head', 'options']

    def get(self, request, escopo, pk):
        self.titular(request, escopo, pk)
        qs = historico(escopo, pk)
        paginator = PageNumberPagination()
        paginator.page_size = 25
        page = paginator.paginate_queryset(qs, request, view=self)
        dados = [dict(serializar_revisao(r), administradora_id=r.configuracao.administradora_id) for r in page]
        resposta = paginator.get_paginated_response(dados)
        resposta.data['encerramentos_globais'] = list(encerramentos(escopo, pk).values('id', 'nome', 'encerrado_em')[:25])
        return resposta


class EncerrarContatoAdministradoraView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if not request.user.has_perms(['clientes.change_contatoadministradora', 'clientes.view_contatoadministradora', 'clientes.change_configuracaodestinatarios']):
            raise PermissionDenied()
        get_object_or_404(ContatoAdministradora, pk=pk)
        c = domain.encerrar_global(pk)
        return Response(dict(id=c.pk, encerrado_em=c.encerrado_em))

def historico(escopo, pk):
    from django.db.models import Q
    filtro = Q(**{'configuracao__' + escopo + '_id': pk})
    if escopo == 'cliente':
        empresas = domain.ClienteAdministradora.objects.filter(cliente_id=pk).values('administradora_id')
        filtro |= Q(configuracao__administradora_id__in=empresas)
    return RevisaoDestinatarios.objects.filter(filtro).select_related('configuracao').order_by('-registrado_em', '-pk')


def encerramentos(escopo, pk):
    ids = domain.ItemDestinatario.objects.filter(revisao__in=historico(escopo, pk)).values('contato_administradora_id')
    return ContatoAdministradora.objects.filter(pk__in=ids, encerrado_em__isnull=False).order_by('-encerrado_em', '-pk')
