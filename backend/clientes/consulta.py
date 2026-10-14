import json
import re
from django.core.exceptions import ValidationError
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .cnpj import normalizar_cnpj


class ErroConsulta(Exception):
    pass


def normalizar_cep(cep):
    cep = str(cep).strip().replace("-", "")
    if not re.fullmatch(r"[0-9]{8}", cep):
        raise ValidationError("Informe um CEP com 8 números.")
    return cep


def consultar_cep(cep):
    cep = normalizar_cep(cep)
    try:
        with urlopen(Request(f"https://viacep.com.br/ws/{cep}/json/", headers={"Accept": "application/json"}), timeout=10) as response:
            dados = json.loads(response.read(100_000))
    except (URLError, TimeoutError, OSError, ValueError) as exc:
        raise ErroConsulta("Consulta de CEP indisponível. Tente novamente ou preencha o endereço manualmente.") from exc
    if not isinstance(dados, dict) or dados.get("erro"):
        raise ErroConsulta("CEP não encontrado. Confira o CEP ou preencha o endereço manualmente.")
    if str(dados.get("cep", "")).replace("-", "") != cep:
        raise ErroConsulta("A consulta retornou um CEP diferente. Confira o endereço manualmente.")
    return {dest: str(dados.get(origem) or "").strip() for dest, origem in
            {"logradouro": "logradouro", "bairro": "bairro", "cidade": "localidade", "estado": "uf"}.items()}


def _formato_brasilapi(dados):
    # BrasilAPI e Minha Receita usam o mesmo formato.
    campos = {"razao_social": "razao_social", "nome_fantasia": "nome_fantasia",
              "logradouro": "logradouro", "numero": "numero", "complemento": "complemento",
              "bairro": "bairro", "cidade": "municipio", "estado": "uf", "cep": "cep",
              "telefone": "ddd_telefone_1", "email": "email"}
    resultado = {dest: str(dados.get(origem) or "").strip() for dest, origem in campos.items()}
    tipo = str(dados.get("descricao_tipo_de_logradouro") or "").strip()
    return dados.get("cnpj"), resultado, tipo


def _formato_cnpjws(dados):
    est = dados.get("estabelecimento") if isinstance(dados.get("estabelecimento"), dict) else {}
    cidade = est.get("cidade") if isinstance(est.get("cidade"), dict) else {}
    estado = est.get("estado") if isinstance(est.get("estado"), dict) else {}
    texto = lambda v: str(v or "").strip()  # noqa: E731
    resultado = {"razao_social": texto(dados.get("razao_social")), "nome_fantasia": texto(est.get("nome_fantasia")),
                 "logradouro": texto(est.get("logradouro")), "numero": texto(est.get("numero")),
                 "complemento": texto(est.get("complemento")), "bairro": texto(est.get("bairro")),
                 "cidade": texto(cidade.get("nome")), "estado": texto(estado.get("sigla")), "cep": texto(est.get("cep")),
                 "telefone": texto(est.get("ddd1")) + texto(est.get("telefone1")), "email": texto(est.get("email"))}
    return est.get("cnpj"), resultado, texto(est.get("tipo_logradouro"))


# Ordem de tentativa: falha ou demora de uma fonte não impede o cadastro se outra responder.
FONTES_CNPJ = [
    ("https://brasilapi.com.br/api/cnpj/v1/{cnpj}", _formato_brasilapi, 8),
    ("https://minhareceita.org/{cnpj}", _formato_brasilapi, 8),
    ("https://publica.cnpj.ws/cnpj/{cnpj}", _formato_cnpjws, 10),
]


def consultar_cnpj(cnpj):
    cnpj = normalizar_cnpj(cnpj)
    nao_encontrado = 0
    for modelo, formato, timeout in FONTES_CNPJ:
        request = Request(modelo.format(cnpj=cnpj), headers={"Accept": "application/json", "User-Agent": "ManutecClientes/1.0"})
        try:
            with urlopen(request, timeout=timeout) as response:
                dados = json.loads(response.read(1_000_000))
            if not isinstance(dados, dict):
                continue
            retornado, resultado, tipo = formato(dados)
        except HTTPError as exc:
            nao_encontrado += exc.code == 404
            continue
        except (URLError, TimeoutError, OSError, ValueError, AttributeError):
            continue
        if retornado != cnpj or not resultado["razao_social"]:
            continue
        resultado["cep"] = resultado["cep"].replace("-", "").replace(".", "")
        if tipo and not resultado["logradouro"].upper().startswith(tipo.upper()):
            resultado["logradouro"] = f"{tipo} {resultado['logradouro']}".strip()
        return resultado
    if nao_encontrado == len(FONTES_CNPJ):
        raise ErroConsulta("CNPJ não encontrado na consulta. Confira o CNPJ ou preencha os dados manualmente.")
    raise ErroConsulta("Consulta indisponível no momento. Tente novamente em instantes ou preencha os dados manualmente.")
