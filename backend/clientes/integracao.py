"""API de leitura para o Jiraya (contrato em docs/INTEGRACAO_JIRAYA.md).

Autenticação própria por token de serviço, sem sessão: o token só abre estas rotas e só para GET/HEAD.
As demais rotas (painel, admin, /api/v1/) não aceitam este token, porque usam outras autenticações."""
import hmac
import logging
import unicodedata
from datetime import datetime
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db.models import Prefetch, Q
from rest_framework import exceptions
from rest_framework.authentication import BaseAuthentication
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Cliente, Contato, Endereco, HistoricoCNPJ

logger = logging.getLogger(__name__)
TAMANHO_MINIMO_TOKEN = 32
FUSO = ZoneInfo("America/Fortaleza")


class ServicoJiraya:
    """Identidade do sistema chamador; não é um usuário do painel e não tem permissões de modelo."""
    is_authenticated = True
    is_anonymous = False
    is_staff = is_superuser = False

    def has_perm(self, *args, **kwargs):
        return False

    def __str__(self):
        return "integracao-jiraya"


class TokenIntegracao(BaseAuthentication):
    def authenticate(self, request):
        esperado = getattr(settings, "INTEGRACAO_JIRAYA_TOKEN", "") or ""
        partes = request.META.get("HTTP_AUTHORIZATION", "").split(" ", 1)
        fornecido = partes[1].strip() if len(partes) == 2 and partes[0].lower() == "bearer" else ""
        # Token curto ou ausente desliga a integração; a comparação é sempre em tempo constante.
        if len(esperado) < TAMANHO_MINIMO_TOKEN or not fornecido or not hmac.compare_digest(
                fornecido.encode(), esperado.encode()):
            raise exceptions.AuthenticationFailed("Token de integração ausente ou inválido.")
        return ServicoJiraya(), None

    def authenticate_header(self, request):
        return 'Bearer realm="integracao"'


class SomenteLeitura(BasePermission):
    def has_permission(self, request, view):
        return isinstance(request.user, ServicoJiraya)


class ParametroInvalido(exceptions.ValidationError):
    def __init__(self, campo, mensagem):
        super().__init__({campo: mensagem})
        self.campo, self.mensagem = campo, mensagem


CODIGOS = {400: "parametro_invalido", 401: "nao_autenticado", 403: "nao_autenticado", 404: "nao_encontrado",
           405: "metodo_nao_permitido"}


def erro(status, mensagem, campo=None):
    corpo = {"codigo": CODIGOS.get(status, "erro_interno"), "mensagem": mensagem}
    if campo:
        corpo["campo"] = campo
    return {"erro": corpo}


class BaseIntegracao(APIView):
    authentication_classes = [TokenIntegracao]
    permission_classes = [SomenteLeitura]
    http_method_names = ["get", "head", "post", "put", "patch", "delete", "options"]

    def handle_exception(self, exc):
        if isinstance(exc, (exceptions.NotAuthenticated, exceptions.AuthenticationFailed, exceptions.PermissionDenied)):
            resposta = Response(erro(401, "Token de integração ausente ou inválido."), status=401)
            resposta["WWW-Authenticate"] = TokenIntegracao().authenticate_header(self.request)
            return resposta
        if isinstance(exc, exceptions.MethodNotAllowed):
            return Response(erro(405, "Somente leitura: use GET."), status=405, headers={"Allow": "GET, HEAD"})
        if isinstance(exc, exceptions.NotFound):
            return Response(erro(404, str(exc.detail)), status=404)
        if isinstance(exc, ParametroInvalido):
            return Response(erro(400, exc.mensagem, exc.campo), status=400)
        logger.exception("Falha na API de integração do Jiraya")
        return Response(erro(500, "Falha inesperada; tente novamente mais tarde."), status=500)

    # Métodos de escrita existem só para responder 405 depois da autenticação (401 vem antes).
    def _negar(self, request, *args, **kwargs):
        raise exceptions.MethodNotAllowed(request.method)

    post = put = patch = delete = options = _negar


def _inteiro(request, nome, padrao, minimo, maximo):
    valor = request.query_params.get(nome)
    if valor in (None, ""):
        return padrao
    if not (valor.isascii() and valor.isdigit()) or not minimo <= int(valor) <= maximo:
        raise ParametroInvalido(nome, f"Use um número inteiro de {minimo} a {maximo}.")
    return int(valor)


def _sem_acento(texto):
    texto = unicodedata.normalize("NFKD", texto or "")
    return "".join(c for c in texto if not unicodedata.combining(c)).casefold()


def _alfanumerico(texto):
    return "".join(c for c in texto or "" if c.isalnum()).upper()


def data_hora(valor):
    # USE_TZ=False: horários locais de Fortaleza, expostos com o deslocamento.
    return valor.replace(tzinfo=FUSO).isoformat() if valor else None


def _ler_data_hora(request, nome):
    valor = request.query_params.get(nome)
    if not valor:
        raise ParametroInvalido(nome, "Informe a data e hora em ISO 8601, ex.: 2026-10-24T10:00:00-03:00.")
    try:
        momento = datetime.fromisoformat(valor)
    except ValueError:
        raise ParametroInvalido(nome, "Data e hora inválida; use ISO 8601, ex.: 2026-10-24T10:00:00-03:00.")
    if momento.tzinfo:
        momento = momento.astimezone(FUSO).replace(tzinfo=None)
    return momento


def _documentos(ids):
    """CNPJ atual de cada cliente PJ (o CPF da PF está no próprio cliente)."""
    return dict(HistoricoCNPJ.objects.filter(cliente_id__in=ids, data_fim__isnull=True).values_list("cliente_id", "cnpj"))


def _documento(cliente, cnpjs):
    if cliente.pessoa_fisica:
        return {"tipo": "CPF", "numero": cliente.cpf}
    numero = cnpjs.get(cliente.pk)
    return {"tipo": "CNPJ", "numero": numero} if numero else None


def resumo(clientes):
    """Itens da busca e das alterações, com cidade/UF do endereço principal para distinguir homônimos."""
    clientes = list(clientes)
    ids = [c.pk for c in clientes]
    cnpjs = _documentos(ids)
    principais = {e.cliente_id: e for e in Endereco.objects.filter(cliente_id__in=ids, principal=True)}
    itens = []
    for c in clientes:
        principal = principais.get(c.pk)
        itens.append({
            "id": c.pk, "tipo_pessoa": c.tipo_pessoa, "documento": _documento(c, cnpjs), "nome": c.razao_social,
            "nome_fantasia": c.nome_fantasia or None, "ativo": c.ativo,
            "cidade": principal.cidade if principal else None, "estado": principal.estado if principal else None,
            "atualizado_em": data_hora(c.atualizado_em),
        })
    return itens


def detalhe(cliente):
    enderecos = [{
        "id": e.pk, "descricao": e.descricao, "principal": e.principal, "ativo": e.ativo,
        **{campo: getattr(e, campo) or None for campo in
           ("logradouro", "numero", "complemento", "bairro", "cidade", "estado", "cep")},
    } for e in cliente.enderecos.all()]
    contatos = [{"id": c.pk, "nome": c.nome, "funcao": c.funcao or None, "telefone": c.telefone or None,
                 "email": c.email or None} for c in cliente.contatos.all()]
    return {
        "id": cliente.pk, "tipo_pessoa": cliente.tipo_pessoa, "documento": _documento(cliente, _documentos([cliente.pk])),
        "nome": cliente.razao_social, "nome_fantasia": cliente.nome_fantasia or None, "ativo": cliente.ativo,
        "enderecos": enderecos, "contatos": contatos,
        "criado_em": data_hora(cliente.criado_em), "atualizado_em": data_hora(cliente.atualizado_em),
    }


class BuscaClientes(BaseIntegracao):
    LIMITE_PADRAO, LIMITE_MAXIMO = 10, 20

    def get(self, request):
        texto = (request.query_params.get("busca") or "").strip()
        if len(texto) < 2:
            raise ParametroInvalido("busca", "Informe ao menos 2 caracteres em busca.")
        limite = _inteiro(request, "limite", self.LIMITE_PADRAO, 1, self.LIMITE_MAXIMO)
        pagina = _inteiro(request, "pagina", 1, 1, 10_000)
        situacao = request.query_params.get("situacao") or "ativo"
        if situacao not in ("ativo", "inativo", "todos"):
            raise ParametroInvalido("situacao", "Use ativo, inativo ou todos.")
        ids = self._encontrar(texto, situacao)
        pagina_ids = ids[(pagina - 1) * limite: pagina * limite]
        clientes = {c.pk: c for c in Cliente.objects.filter(pk__in=pagina_ids)}
        proxima = None
        if pagina * limite < len(ids):
            parametros = request.query_params.copy()
            parametros["pagina"] = str(pagina + 1)
            proxima = request.build_absolute_uri(request.path + "?" + parametros.urlencode())
        return Response({"resultados": resumo(clientes[i] for i in pagina_ids), "pagina": pagina, "limite": limite,
                         "total": len(ids), "proxima": proxima})

    @staticmethod
    def _encontrar(texto, situacao):
        """Compara sem acento nem caixa em Python: a base é pequena e o PostgreSQL instalado não tem unaccent."""
        alvo = _sem_acento(texto)
        documento = _alfanumerico(texto) if any(c.isdigit() for c in texto) else ""
        qs = Cliente.objects.all()
        if situacao != "todos":
            qs = qs.filter(ativo=situacao == "ativo")
        cnpjs = {}
        if documento:
            for cliente_id, cnpj in HistoricoCNPJ.objects.values_list("cliente_id", "cnpj"):
                cnpjs.setdefault(cliente_id, []).append(cnpj)
        achados = []
        for pk, nome, fantasia, cpf in qs.values_list("pk", "razao_social", "nome_fantasia", "cpf"):
            nomes = (_sem_acento(nome), _sem_acento(fantasia))
            por_nome = any(alvo in n for n in nomes)
            por_documento = bool(documento) and any(documento in d for d in [cpf or ""] + cnpjs.get(pk, []))
            if por_nome or por_documento:
                comeca = any(n.startswith(alvo) for n in nomes) or por_documento
                achados.append((not comeca, nomes[0], pk))
        return [pk for *_, pk in sorted(achados)]


class DetalheCliente(BaseIntegracao):
    def get(self, request, pk):
        contatos = Contato.objects.filter(data_fim__isnull=True).order_by("nome", "id")
        cliente = Cliente.objects.prefetch_related("enderecos", Prefetch("contatos", queryset=contatos)).filter(pk=pk).first()
        if cliente is None:
            raise exceptions.NotFound("Cliente não encontrado.")
        return Response(detalhe(cliente))


class AlteracoesClientes(BaseIntegracao):
    LIMITE_PADRAO, LIMITE_MAXIMO = 100, 200

    def get(self, request):
        desde = _ler_data_hora(request, "desde")
        limite = _inteiro(request, "limite", self.LIMITE_PADRAO, 1, self.LIMITE_MAXIMO)
        apos_id = _inteiro(request, "apos_id", 0, 0, 2 ** 62)
        # Cursor estável: (atualizado_em, id) depois do último item já lido.
        filtro = Q(atualizado_em__gt=desde) | Q(atualizado_em=desde, pk__gt=apos_id) if apos_id else Q(atualizado_em__gt=desde)
        clientes = list(Cliente.objects.filter(filtro).order_by("atualizado_em", "pk")[:limite + 1])
        proxima = None
        if len(clientes) > limite:
            clientes = clientes[:limite]
            ultimo = clientes[-1]
            parametros = request.query_params.copy()
            parametros.update({"desde": data_hora(ultimo.atualizado_em), "apos_id": str(ultimo.pk), "limite": str(limite)})
            proxima = request.build_absolute_uri(request.path + "?" + parametros.urlencode())
        return Response({"resultados": resumo(clientes), "limite": limite, "proxima": proxima})


class RotaInexistente(BaseIntegracao):
    def get(self, request, *args, **kwargs):
        raise exceptions.NotFound("Rota não encontrada nesta versão da integração.")
