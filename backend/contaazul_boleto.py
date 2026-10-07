"""Baixa um boleto existente por vencimento e valor; somente GET, sem Django ou banco."""
import argparse
import json
import os
import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, ProxyHandler, build_opener
from uuid import UUID

from dotenv import dotenv_values
from contaazul_auth import CONFIG, CONFIG_PRODUCAO, SemRedirecionamento

BASE = 'https://api-v2.contaazul.com'
LIMITE_JSON = 1048576
LIMITE_PDF = 10 * 1048576
ROTA = '/v1/financeiro/eventos-financeiros/contas-a-receber'


def salvar(destino, conteudo):
    """Publica o arquivo completo sem sobrescrever, inclusive se outro processo criar o destino."""
    destino.parent.mkdir(exist_ok=True)
    temporario = None
    try:
        with tempfile.NamedTemporaryFile(dir=destino.parent, prefix='.boleto-', suffix='.parcial',
                                         delete=False) as stream:
            temporario = Path(stream.name)
            stream.write(conteudo)
            stream.flush()
            os.fsync(stream.fileno())
        # Hard link e exclusivo: falha se destino existir. Mesmo volume (NTFS).
        os.link(temporario, destino)
    finally:
        if temporario is not None:
            temporario.unlink(missing_ok=True)


def executar(vencimento, valor, *, path=CONFIG):
    path = Path(path)
    etapa = 'configuracao'
    try:
        if not valor.is_finite() or valor <= 0 or valor != valor.quantize(Decimal('0.01')):
            raise ValueError()
        destino = path.parent / 'downloads' / f'boleto-{vencimento:%Y%m%d}.pdf'
        if destino.exists():
            print('FALHA: arquivo de destino ja existe; preservado, nenhuma consulta feita.')
            return 1
        if not path.is_file():
            raise ValueError()
        token = dotenv_values(path, interpolate=False).get('ACCESS_TOKEN')
        if not isinstance(token, str) or not token.strip():
            raise ValueError()
        opener = build_opener(ProxyHandler({}), SemRedirecionamento())

        def get(rota, params=None, *, pdf=False):
            url = BASE + rota + ('?' + urlencode(params) if params else '')
            limite = LIMITE_PDF if pdf else LIMITE_JSON
            req = Request(url, method='GET', headers={
                'Authorization': 'Bearer ' + token,
                'Accept': 'application/pdf' if pdf else 'application/json'})
            with opener.open(req, timeout=30) as response:
                raw = response.read(limite + 1)
                tipo = response.headers.get_content_type()
            if len(raw) > limite:
                raise ValueError()
            if pdf:
                if (tipo not in ('application/pdf', 'application/octet-stream')
                        or not raw.startswith(b'%PDF-') or not raw.rstrip().endswith(b'%%EOF')):
                    raise ValueError()
                return raw
            data = json.loads(raw, parse_float=Decimal)
            if not isinstance(data, dict):
                raise ValueError()
            return data

        etapa = 'selecao da conta'
        rows = get(ROTA + '/buscar', {
            'pagina': 1, 'tamanho_pagina': 10,
            'data_vencimento_de': vencimento.isoformat(),
            'data_vencimento_ate': vencimento.isoformat()}).get('itens')
        # Uma pagina cheia pode ocultar outra correspondencia: nao selecionar uma amostra parcial.
        if not isinstance(rows, list) or len(rows) >= 10 or not all(isinstance(r, dict) for r in rows):
            raise ValueError()
        matches = [r for r in rows if r.get('status') == 'PENDING'
                   and r.get('data_vencimento') == vencimento.isoformat()
                   and Decimal(str(r.get('total'))) == valor]
        print('Contas pendentes correspondentes: ' + str(len(matches)))
        if len(matches) != 1:
            raise ValueError()
        parcela = str(UUID(matches[0]['id']))
        etapa = 'selecao da cobranca'
        details = get('/v1/financeiro/eventos-financeiros/parcelas/' + parcela)
        charges = details.get('solicitacoes_cobrancas')
        if not isinstance(charges, list) or not 1 <= len(charges) <= 10:
            raise ValueError()
        ids = [str(UUID(c['id'])) for c in charges]
        if len(ids) != len(set(ids)):
            raise ValueError()
        ativas = []
        for cid in ids:
            charge = get(ROTA + '/cobranca/' + cid)
            if str(UUID(charge['id'])) != cid:
                raise ValueError()
            if charge.get('status') == 'REGISTRADO':
                ativas.append(cid)
        print('Cobrancas REGISTRADO correspondentes: ' + str(len(ativas)))
        if len(ativas) != 1:
            raise ValueError()
        etapa = 'download do PDF'
        conteudo = get(ROTA + '/cobranca/' + ativas[0] + '/imprimir', pdf=True)
        etapa = 'gravacao local'
        salvar(destino, conteudo)
        print('SUCESSO: PDF salvo em ' + str(destino.resolve()))
        print('Nenhuma cobranca criada, alterada ou enviada. Sem renovacao automatica.')
        return 0
    except HTTPError as error:
        print(f'FALHA HTTP {error.code} na etapa {etapa}; sem repeticao automatica.')
        if error.code == 401:
            print('Renove manualmente com contaazul_auth.py no mesmo ambiente e tente novamente.')
        error.close()
        return 1
    except Exception:
        print('FALHA na etapa ' + etapa + '; selecao, formato ou configuracao recusados. '
              'Detalhes sensiveis omitidos; sem repeticao automatica.')
        return 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vencimento', type=date.fromisoformat, required=True, help='YYYY-MM-DD')
    parser.add_argument('--valor', type=Decimal, required=True, help='Ex.: 1500.00, sem separador de milhar')
    parser.add_argument('--producao', action='store_true', help='Usar somente a configuracao de producao')
    args = parser.parse_args(argv)
    return executar(args.vencimento, args.valor, path=CONFIG_PRODUCAO if args.producao else CONFIG)


if __name__ == '__main__':
    raise SystemExit(main())
