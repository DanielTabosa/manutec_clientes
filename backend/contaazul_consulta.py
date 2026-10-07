"""Consulta manual limitada ao Conta Azul; sem Django, banco ou envio de documentos."""
import argparse
import json
from datetime import date, timedelta
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, ProxyHandler, build_opener
from uuid import UUID
from dotenv import dotenv_values
from contaazul_auth import CONFIG, CONFIG_PRODUCAO, SemRedirecionamento

BASE = 'https://api-v2.contaazul.com'
LIMITE = 1048576


def executar(inicio, fim, *, path=CONFIG):
    try:
        if not 0 <= (fim - inicio).days <= 14:
            raise ValueError('Periodo invalido')
        token = dotenv_values(path, interpolate=False).get('ACCESS_TOKEN')
        if not isinstance(token, str) or not token.strip():
            print('FALHA: ACCESS_TOKEN ausente na configuracao local.')
            return 1
        opener = build_opener(ProxyHandler({}), SemRedirecionamento())

        def get(route, params=None):
            url = BASE + route + ('?' + urlencode(params) if params else '')
            req = Request(url, method='GET', headers={'Authorization': 'Bearer ' + token,
                                                     'Accept': 'application/json'})
            with opener.open(req, timeout=20) as response:
                raw = response.read(LIMITE + 1)
            if len(raw) > LIMITE:
                raise ValueError('Resposta excede limite')
            payload = json.loads(raw)
            if not isinstance(payload, dict):
                raise ValueError('Formato inesperado')
            return payload

        def itens(payload):
            rows = payload.get('itens')
            if not isinstance(rows, list) or len(rows) > 10 or not all(isinstance(r, dict) for r in rows):
                raise ValueError('Formato inesperado')
            return rows

        print(f'Periodo: {inicio.isoformat()} a {fim.isoformat()}. Primeira pagina, ate 10 registros por lista.')
        notes = itens(get('/v1/notas-fiscais-servico', {
            'pagina': 1, 'tamanho_pagina': 10,
            'data_competencia_de': inicio.isoformat(), 'data_competencia_ate': fim.isoformat()}))
        print(f'NFS-e na pagina: {len(notes)}. Consulta por competencia.')
        print('PDF/XML de NFS-e: disponibilidade nao comprovada por esta consulta.')
        receivables = itens(get('/v1/financeiro/eventos-financeiros/contas-a-receber/buscar', {
            'pagina': 1, 'tamanho_pagina': 10,
            'data_vencimento_de': inicio.isoformat(), 'data_vencimento_ate': fim.isoformat()}))
        print(f'Contas a receber na pagina: {len(receivables)}. Consulta por vencimento.')
        if receivables:
            installment_id = str(UUID(receivables[0]['id']))
            detail = get('/v1/financeiro/eventos-financeiros/parcelas/' + installment_id)
            charges = detail.get('solicitacoes_cobrancas', [])
            if not isinstance(charges, list) or not all(isinstance(c, dict) for c in charges):
                raise ValueError('Formato inesperado')
            if charges:
                charge_id = str(UUID(charges[0]['id']))
                charge = get('/v1/financeiro/eventos-financeiros/contas-a-receber/cobranca/' + charge_id)
                if str(UUID(charge['id'])) != charge_id:
                    raise ValueError('Cobranca divergente')
                present = isinstance(charge.get('url'), str) and bool(charge['url'].strip())
                print('Link de cobranca presente: ' + ('sim' if present else 'nao') + '. Link nao aberto; PDF nao comprovado.')
            else:
                print('Sem amostra de cobranca na primeira parcela; resultado inconclusivo para boletos.')
        else:
            print('Sem amostra de conta a receber neste periodo; resultado inconclusivo para boletos.')
        if not notes:
            print('Sem amostra de NFS-e neste periodo; resultado inconclusivo para notas.')
        print('SUCESSO: consulta limitada concluida. Nenhum documento baixado, alterado ou enviado.')
        return 0
    except HTTPError as error:
        if error.code == 401:
            print('FALHA HTTP 401: acesso recusado. Renove com contaazul_auth.py no mesmo ambiente (--producao quando selecionado) e tente manualmente.')
        else:
            print(f'FALHA HTTP {error.code}: consulta interrompida; sem repeticao automatica.')
        return 1
    except Exception:
        print('FALHA: confira periodo, configuracao ou formato da resposta. Nenhum dado sensivel exibido; sem repeticao automatica.')
        return 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inicio', type=date.fromisoformat, help='YYYY-MM-DD; padrao: hoje menos 14 dias')
    parser.add_argument('--fim', type=date.fromisoformat, help='YYYY-MM-DD; padrao: hoje')
    parser.add_argument('--producao', action='store_true', help='Usar somente a configuracao separada de producao.')
    args = parser.parse_args(argv)
    path = CONFIG_PRODUCAO if args.producao else CONFIG
    print('Configuracao selecionada: ' + ('PRODUCAO' if args.producao else 'DESENVOLVIMENTO'))
    fim = args.fim or date.today()
    return executar(args.inicio or fim - timedelta(days=14), fim, path=path)


if __name__ == '__main__':
    raise SystemExit(main())
