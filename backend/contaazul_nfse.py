"""Confere PDF/XML de um ZIP de NFS-e com a API; somente leitura, sem extrair ou enviar."""
import argparse
import calendar
import json
import re
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, ProxyHandler, build_opener

from dotenv import dotenv_values
from contaazul_auth import CONFIG, CONFIG_PRODUCAO, SemRedirecionamento

LIMITE_ZIP = 100 * 1048576
LIMITE_TOTAL = 100 * 1048576
LIMITE_PDF = 10 * 1048576
LIMITE_XML = 2 * 1048576
LIMITE_JSON = 2 * 1048576
MAX_ENTRADAS = 2000
MAX_PAGINAS = 10
TAMANHO_PAGINA = 50
BASE = 'https://api-v2.contaazul.com/v1/notas-fiscais-servico'
FORMATOS = {'{http://www.sped.fazenda.gov.br/nfse}NFSe',
            '{http://www.abrasf.org.br/nfse.xsd}Nfse'}


def numero(value):
    text = str(value).strip()
    if not re.fullmatch(r'[0-9]{1,20}', text) or int(text) <= 0:
        raise ValueError()
    return int(text)


def documento(value):
    text = str(value or '').strip()
    if not re.fullmatch(r'[0-9./ -]+', text):
        raise ValueError()
    digits = re.sub(r'[^0-9]', '', text)
    if len(digits) not in (11, 14):
        raise ValueError()
    return digits


def dinheiro(value):
    text = str(value).strip()
    if not re.fullmatch(r'[0-9]{1,15}(\.[0-9]{1,2})?', text):
        raise ValueError()
    return Decimal(text)


def ler_xml(raw):
    text = raw.decode('utf-8-sig')
    if '\x00' in text or '<!DOCTYPE' in text.upper() or '<!ENTITY' in text.upper():
        raise ValueError()
    root = ET.fromstring(text)
    if root.tag not in FORMATOS or sum(1 for _ in root.iter()) > 10000:
        raise ValueError()
    namespace = root.tag.split('}')[0] + '}'

    def unico(parent, path):
        current = parent
        for name in path.split('/'):
            children = current.findall(namespace + name)
            if len(children) != 1:
                raise ValueError()
            current = children[0]
        return current

    info = unico(root, 'infNFSe')
    dps = unico(info, 'DPS/infDPS')
    toma = unico(dps, 'toma')
    docs = toma.findall(namespace + 'CNPJ') + toma.findall(namespace + 'CPF')
    if len(docs) != 1:
        raise ValueError()
    return {'numero_nfse': numero(unico(info, 'nNFSe').text),
            'numero_rps': numero(unico(dps, 'nDPS').text),
            'documento': documento(docs[0].text),
            'valor': dinheiro(unico(dps, 'valores/vServPrest/vServ').text)}


def ler_zip(caminho):
    """Le pares sem extrair; resultados so carregam campos de conferencia e indice anonimo."""
    caminho = Path(caminho)
    if not caminho.is_file() or caminho.stat().st_size > LIMITE_ZIP:
        raise ValueError()
    pairs, issues = [], []
    with zipfile.ZipFile(caminho) as z:
        entries = z.infolist()
        if len(entries) > MAX_ENTRADAS or sum(i.file_size for i in entries) > LIMITE_TOTAL:
            raise ValueError()
        groups = defaultdict(lambda: defaultdict(list))
        for info in entries:
            if info.is_dir():
                continue
            base = info.filename.replace('\\', '/').rsplit('/', 1)[-1]
            stem, sep, ext = base.rpartition('.')
            if sep and ext.lower() in ('pdf', 'xml'):
                groups[stem.casefold()][ext.lower()].append(info)
        for item, files in enumerate(groups.values(), 1):
            if set(files) != {'pdf', 'xml'} or any(len(v) != 1 for v in files.values()):
                issues.append((item, 'par PDF/XML ausente ou duplicado'))
                continue
            try:
                contents = {}
                for ext, limit in (('xml', LIMITE_XML), ('pdf', LIMITE_PDF)):
                    info = files[ext][0]
                    if info.flag_bits & 1 or info.file_size > limit:
                        raise ValueError()
                    with z.open(info) as stream:
                        contents[ext] = stream.read(limit + 1)
                    if len(contents[ext]) > limit:
                        raise ValueError()
                dados = ler_xml(contents['xml'])
                pdf = contents['pdf']
                if not pdf.startswith(b'%PDF-') or not pdf.rstrip().endswith(b'%%EOF'):
                    raise ValueError()
                pairs.append({'item': item, **dados})
            except (ValueError, ET.ParseError, zipfile.BadZipFile, RuntimeError, NotImplementedError):
                issues.append((item, 'XML/PDF invalido, incompleto, protegido ou fora dos limites'))
    return pairs, issues


def janelas(competencia):
    inicio = competencia.replace(day=1)
    fim = date(inicio.year, inicio.month, calendar.monthrange(inicio.year, inicio.month)[1])
    result = []
    while inicio <= fim:
        final = min(inicio + timedelta(days=14), fim)
        result.append((inicio, final))
        if final == fim:
            break
        inicio = final + timedelta(days=1)
    return result


def consultar(competencia, path):
    if not Path(path).is_file():
        raise ValueError()
    token = dotenv_values(path, interpolate=False).get('ACCESS_TOKEN')
    if not isinstance(token, str) or not token.strip():
        raise ValueError()
    opener = build_opener(ProxyHandler({}), SemRedirecionamento())
    notes = []
    for inicio, fim in janelas(competencia):
        for page in range(1, MAX_PAGINAS + 1):
            params = {'pagina': page, 'tamanho_pagina': TAMANHO_PAGINA,
                      'data_competencia_de': inicio.isoformat(), 'data_competencia_ate': fim.isoformat()}
            req = Request(BASE + '?' + urlencode(params), method='GET',
                          headers={'Authorization': 'Bearer ' + token, 'Accept': 'application/json'})
            with opener.open(req, timeout=30) as response:
                raw = response.read(LIMITE_JSON + 1)
            if len(raw) > LIMITE_JSON:
                raise ValueError()
            payload = json.loads(raw, parse_float=Decimal)
            rows = payload.get('itens') if isinstance(payload, dict) else None
            if (not isinstance(rows, list) or len(rows) > TAMANHO_PAGINA
                    or not all(isinstance(row, dict) for row in rows)):
                raise ValueError()
            notes.extend(rows)
            if len(rows) < TAMANHO_PAGINA:
                break
        else:
            # Lista truncada nunca e tratada como conferencia concluida.
            raise ValueError()
    return notes


def conferir(pairs, notes):
    by_number = defaultdict(list)
    for note in notes:
        try:
            by_number[numero(note.get('numero_nfse'))].append(note)
        except ValueError:
            continue
    repetitions = Counter(p['numero_nfse'] for p in pairs)
    recognized, issues = [], []
    for pair in pairs:
        candidates = by_number[pair['numero_nfse']]
        reason = None
        if repetitions[pair['numero_nfse']] != 1:
            reason = 'numero de nota repetido no ZIP'
        elif len(candidates) != 1:
            reason = 'nota ausente ou ambigua na API no periodo'
        else:
            note = candidates[0]
            try:
                rps = numero(note.get('numero_rps'))
                doc = documento(note.get('documento_cliente'))
                value = dinheiro(note.get('valor_total_nfse'))
                if note.get('status') != 'EMITIDA':
                    reason = 'status diferente de EMITIDA'
                elif rps != pair['numero_rps']:
                    reason = 'RPS divergente'
                elif doc != pair['documento']:
                    reason = 'documento do tomador divergente'
                elif value != pair['valor']:
                    reason = 'valor divergente'
            except ValueError:
                reason = 'dados obrigatorios ausentes ou invalidos na API'
        if reason:
            issues.append((pair['item'], reason))
        else:
            recognized.append(pair['item'])
    return recognized, issues


def executar(caminho_zip, competencia, *, path=CONFIG):
    etapa = 'leitura do ZIP'
    try:
        pairs, issues = ler_zip(caminho_zip)
        print(f'Pares aptos para conferencia: {len(pairs)}; pendencias locais: {len(issues)}.')
        recognized = []
        if pairs:
            etapa = 'consulta da API'
            notes = consultar(competencia, path)
            etapa = 'comparacao'
            recognized, differences = conferir(pairs, notes)
            issues.extend(differences)
        print(f'Reconhecidas: {len(recognized)} | Pendencias: {len(issues)}')
        for item in recognized:
            print(f'Item {item}: XML confere com a API; PDF pareado pelo nome.')
        for item, reason in sorted(issues):
            print(f'Item {item}: {reason}.')
        print('Conferencia somente de leitura. Nenhum arquivo extraido, cadastro alterado ou documento enviado.')
        print('PDF verificado por assinatura/fim e nome do par; conteudo e autenticidade fiscal nao validados.')
        return 0 if recognized and not issues else 2
    except HTTPError as error:
        print(f'FALHA HTTP {error.code} na etapa {etapa}; sem repeticao automatica.')
        if error.code == 401:
            print('Renove manualmente com contaazul_auth.py no mesmo ambiente antes de repetir.')
        error.close()
        return 1
    except Exception:
        print(f'FALHA na etapa {etapa}; formato, limites ou configuracao recusados. Dados sensiveis omitidos.')
        return 1


def competencia_cli(value):
    try:
        if not re.fullmatch(r'[0-9]{4}-[0-9]{2}', value):
            raise ValueError()
        return date.fromisoformat(value + '-01')
    except ValueError:
        raise argparse.ArgumentTypeError('Use competencia no formato YYYY-MM.') from None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--zip', type=Path, required=True, dest='caminho_zip', help='ZIP existente de PDF e XML')
    parser.add_argument('--competencia', type=competencia_cli, required=True, help='YYYY-MM')
    parser.add_argument('--producao', action='store_true', help='Usar somente a configuracao de producao')
    args = parser.parse_args(argv)
    return executar(args.caminho_zip, args.competencia, path=CONFIG_PRODUCAO if args.producao else CONFIG)


if __name__ == '__main__':
    raise SystemExit(main())
