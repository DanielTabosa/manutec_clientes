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


def consultar_cnpj(cnpj):
    cnpj = normalizar_cnpj(cnpj)
    request = Request(f"https://brasilapi.com.br/api/cnpj/v1/{cnpj}", headers={"Accept": "application/json", "User-Agent": "ManutecClientes/1.0"})
    try:
        with urlopen(request, timeout=10) as response:
            dados = json.loads(response.read(1_000_000))
    except HTTPError as exc:
        if exc.code == 404:
            raise ErroConsulta("CNPJ não encontrado na consulta. Confira o CNPJ ou preencha os dados manualmente.") from exc
        raise ErroConsulta("Consulta indisponível. Tente novamente ou preencha os dados manualmente.") from exc
    except (URLError, TimeoutError, OSError, ValueError) as exc:
        raise ErroConsulta("Consulta indisponível. Tente novamente ou preencha os dados manualmente.") from exc
    if not isinstance(dados, dict) or dados.get("cnpj") != cnpj:
        raise ErroConsulta("A consulta retornou dados inconsistentes. Confira os dados manualmente.")
    campos = {"razao_social": "razao_social", "nome_fantasia": "nome_fantasia",
              "logradouro": "logradouro", "numero": "numero", "complemento": "complemento",
              "bairro": "bairro", "cidade": "municipio", "estado": "uf", "cep": "cep",
              "telefone": "ddd_telefone_1", "email": "email"}
    resultado = {dest: str(dados.get(origem) or "").strip() for dest, origem in campos.items()}
    resultado["cep"] = resultado["cep"].replace("-", "").replace(".", "")
    tipo = str(dados.get("descricao_tipo_de_logradouro") or "").strip()
    if tipo:
        resultado["logradouro"] = f"{tipo} {resultado['logradouro']}".strip()
    return resultado
