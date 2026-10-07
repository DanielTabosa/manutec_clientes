"""Previa local de NFS-e por CNPJ atual; nao grava associacoes nem envia documentos."""
import argparse
import csv
import io
import os
from collections import Counter, defaultdict
from pathlib import Path
from urllib.error import HTTPError

import contaazul_nfse as nfse
from contaazul_auth import CONFIG, CONFIG_PRODUCAO
from contaazul_boleto import salvar

CAMPOS = ('item', 'numero_nfse', 'cliente_id', 'cliente_nome', 'situacao', 'motivo')


def ler_clientes(documentos, *, connection=None, atomic=None):
    """Somente os CNPJs necessarios, em transacao PostgreSQL protegida contra escrita."""
    documentos = sorted(set(d for d in documentos if len(d) == 14 and d.isdigit()))
    if not documentos:
        return []
    if connection is None:
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
        import django
        django.setup()
        from django.db import connection, transaction
        atomic = transaction.atomic
    if connection.vendor != 'postgresql' or connection.in_atomic_block is True or atomic is None:
        raise ValueError()
    with atomic():
        with connection.cursor() as cursor:
            cursor.execute('SET TRANSACTION READ ONLY')
            cursor.execute("SET LOCAL statement_timeout = '10s'")
            placeholders = ', '.join(['%s'] * len(documentos))
            cursor.execute('''SELECT h.cnpj, h.cliente_id, c.razao_social, h.data_fim
                              FROM historico_cnpj h JOIN clientes c ON c.id = h.cliente_id
                              WHERE h.cnpj IN (''' + placeholders + ')', documentos)
            return [dict(zip(('cnpj', 'cliente_id', 'razao_social', 'data_fim'), row))
                    for row in cursor.fetchall()]


def associar(pares, cadastros):
    """Sugestao conservadora, sem alterar a regra ou os vinculos persistidos do cadastro."""
    por_documento = defaultdict(list)
    for cadastro in cadastros:
        por_documento[cadastro['cnpj']].append(cadastro)
    resultado = []
    for par in pares:
        linha = {'item': par['item'], 'numero_nfse': par['numero_nfse'],
                 'cliente_id': '', 'cliente_nome': '', 'situacao': '', 'motivo': ''}
        encontrados = por_documento[par['documento']]
        if len(par['documento']) != 14:
            linha.update(situacao='cpf_sem_regra', motivo='Cadastro local usa CNPJ; revisar documento CPF.')
        elif not encontrados:
            linha.update(situacao='sem_cadastro', motivo='CNPJ nao localizado no historico de clientes.')
        elif len(encontrados) != 1:
            linha.update(situacao='ambiguo', motivo='Mais de um registro para o documento; revisao necessaria.')
        elif encontrados[0]['data_fim'] is not None:
            linha.update(situacao='cnpj_historico', motivo='CNPJ antigo; nenhuma associacao sugerida automaticamente.')
        else:
            cliente = encontrados[0]
            linha.update(cliente_id=cliente['cliente_id'], cliente_nome=cliente['razao_social'],
                         situacao='sugerida', motivo='Correspondencia unica com o CNPJ atual do cliente.')
        resultado.append(linha)
    return resultado


def salvar_relatorio(destino, linhas):
    def texto_seguro(value):
        text = str(value)
        return "'" + text if text.lstrip().startswith(('=', '+', '-', '@')) or text.startswith(('\t', '\r', '\n')) else text

    buffer = io.StringIO(newline='')
    writer = csv.DictWriter(buffer, fieldnames=CAMPOS, delimiter=';')
    writer.writeheader()
    for linha in linhas:
        writer.writerow({k: texto_seguro(linha.get(k, '')) for k in CAMPOS})
    salvar(Path(destino), buffer.getvalue().encode('utf-8-sig'))


def executar(caminho_zip, competencia, *, path=CONFIG):
    etapa = 'preparacao'
    try:
        destino = Path(path).parent / 'previas' / f'clientes-nfse-{competencia:%Y%m}.csv'
        if destino.exists():
            print('FALHA: previa ja existe; preservada, nenhuma consulta feita.')
            return 1
        etapa = 'conferencia dos documentos'
        pares, pendencias = nfse.ler_zip(caminho_zip)
        reconhecidas = []
        if pares:
            notas = nfse.consultar(competencia, path)
            reconhecidas, divergencias = nfse.conferir(pares, notas)
            pendencias.extend(divergencias)
        ids = set(reconhecidas)
        aptas = [par for par in pares if par['item'] in ids]
        etapa = 'consulta de clientes somente leitura'
        cadastros = ler_clientes([par['documento'] for par in aptas]) if aptas else []
        linhas = associar(aptas, cadastros)
        por_item = {par['item']: par for par in pares}
        for item, motivo in pendencias:
            linhas.append({'item': item, 'numero_nfse': por_item.get(item, {}).get('numero_nfse', ''),
                           'cliente_id': '', 'cliente_nome': '',
                           'situacao': 'documento_nao_conferido', 'motivo': motivo})
        if not linhas:
            print('Sem documentos para previa; nenhum relatorio criado.')
            return 2
        etapa = 'relatorio local'
        salvar_relatorio(destino, sorted(linhas, key=lambda r: r['item']))
        contagem = Counter(l['situacao'] for l in linhas)
        for situacao, quantidade in sorted(contagem.items()):
            print(situacao + ': ' + str(quantidade))
        print('Previa salva em ' + str(destino.resolve()))
        print('Nenhum vinculo ou cadastro gravado; nenhum documento enviado. ZIP preservado.')
        return 0 if set(contagem) == {'sugerida'} else 2
    except HTTPError as error:
        print(f'FALHA HTTP {error.code} na etapa {etapa}; sem repeticao automatica.')
        if error.code == 401:
            print('Renove manualmente com contaazul_auth.py no mesmo ambiente antes de repetir.')
        error.close()
        return 1
    except Exception:
        print('FALHA na etapa ' + etapa + '; detalhes sensiveis omitidos. Nenhuma associacao gravada.')
        return 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--zip', type=Path, required=True, dest='caminho_zip')
    parser.add_argument('--competencia', type=nfse.competencia_cli, required=True, help='YYYY-MM')
    parser.add_argument('--producao', action='store_true')
    args = parser.parse_args(argv)
    return executar(args.caminho_zip, args.competencia, path=CONFIG_PRODUCAO if args.producao else CONFIG)


if __name__ == '__main__':
    raise SystemExit(main())
