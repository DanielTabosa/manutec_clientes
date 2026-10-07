"""Previa de associacao: dados ficticios, conexao simulada, sem banco instalado."""
import csv
import io
import contextlib
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import contaazul_previa_clientes as previa

DOC = '11111111000101'
PAIR = {'item': 1, 'numero_nfse': 101, 'documento': DOC}
ROW = {'cnpj': DOC, 'cliente_id': 7, 'razao_social': 'Cliente ficticio', 'data_fim': None}


class AssociacaoTests(unittest.TestCase):
    def test_cnpj_atual_unico_sugere_id_estavel(self):
        result = previa.associar([PAIR], [ROW])
        self.assertEqual(result[0]['situacao'], 'sugerida')
        self.assertEqual(result[0]['cliente_id'], 7)

    def test_historico_ausente_cpf_e_duplicidade_ficam_pendentes(self):
        cases = [([PAIR], [{**ROW, 'data_fim': date(2026, 1, 1)}], 'cnpj_historico'),
                 ([PAIR], [], 'sem_cadastro'),
                 ([{**PAIR, 'documento': '12345678901'}], [], 'cpf_sem_regra'),
                 ([PAIR], [ROW, {**ROW, 'cliente_id': 8}], 'ambiguo')]
        for pairs, rows, expected in cases:
            with self.subTest(expected=expected):
                result = previa.associar(pairs, rows)[0]
                self.assertEqual(result['situacao'], expected)
                self.assertEqual(result['cliente_id'], '')

    def test_nome_igual_nao_substitui_cnpj(self):
        result = previa.associar([PAIR], [{**ROW, 'cnpj': '22222222000102'}])[0]
        self.assertEqual(result['situacao'], 'sem_cadastro')

    def test_duas_notas_do_mesmo_cliente_nao_sao_ambiguidade(self):
        result = previa.associar([PAIR, {**PAIR, 'item': 2, 'numero_nfse': 102}], [ROW])
        self.assertEqual([r['cliente_id'] for r in result], [7, 7])


class LeituraTests(unittest.TestCase):
    def test_consulta_parametrizada_em_transacao_somente_leitura(self):
        connection = MagicMock(vendor='postgresql')
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchall.return_value = [(DOC, 7, 'Cliente ficticio', None)]
        atomic = Mock()
        atomic.return_value.__enter__ = Mock()
        atomic.return_value.__exit__ = Mock(return_value=False)
        rows = previa.ler_clientes([DOC], connection=connection, atomic=atomic)
        self.assertEqual(rows, [ROW])
        calls = cursor.execute.call_args_list
        self.assertEqual(calls[0].args[0], 'SET TRANSACTION READ ONLY')
        self.assertTrue(calls[-1].args[0].lstrip().startswith('SELECT'))
        self.assertNotIn(DOC, calls[-1].args[0])
        self.assertEqual(calls[-1].args[1], [DOC])

    def test_outro_banco_ou_sem_cnpj_nao_consulta(self):
        connection = Mock(vendor='sqlite')
        with self.assertRaises(ValueError):
            previa.ler_clientes([DOC], connection=connection, atomic=Mock())
        connection.cursor.assert_not_called()
        self.assertEqual(previa.ler_clientes([], connection=connection, atomic=Mock()), [])


class RelatorioTests(unittest.TestCase):
    def test_csv_sem_sobrescrita_e_sem_formula(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'previa.csv'
            rows = previa.associar([PAIR], [{**ROW, 'razao_social': '=COMANDO()'}])
            previa.salvar_relatorio(path, rows)
            with path.open(encoding='utf-8-sig', newline='') as f:
                saved = list(csv.DictReader(f, delimiter=';'))
            self.assertEqual(saved[0]['cliente_nome'], "'=COMANDO()")
            self.assertEqual(saved[0]['situacao'], 'sugerida')
            before = path.read_bytes()
            with self.assertRaises(FileExistsError):
                previa.salvar_relatorio(path, rows)
            self.assertEqual(path.read_bytes(), before)

    def test_integracao_so_consulta_cadastro_para_notas_conferidas(self):
        with tempfile.TemporaryDirectory() as d:
            config = Path(d) / 'credenciais.env'
            config.write_text('nao lido neste teste')
            second = {**PAIR, 'item': 2, 'numero_nfse': 102}
            with patch.object(previa.nfse, 'ler_zip', return_value=([PAIR, second], [])), \
                    patch.object(previa.nfse, 'consultar', return_value=[]), \
                    patch.object(previa.nfse, 'conferir', return_value=([1], [(2, 'status diferente de EMITIDA')])), \
                    patch.object(previa, 'ler_clientes', return_value=[ROW]) as read, \
                    contextlib.redirect_stdout(io.StringIO()) as out:
                result = previa.executar(Path(d)/'notas.zip', date(2026, 10, 1), path=config)
            self.assertEqual(result, 2)
            read.assert_called_once_with([DOC])
            self.assertNotIn('Cliente ficticio', out.getvalue())
            self.assertNotIn(DOC, out.getvalue())
            with (Path(d)/'previas'/'clientes-nfse-202610.csv').open(encoding='utf-8-sig', newline='') as f:
                rows = list(csv.DictReader(f, delimiter=';'))
            self.assertEqual([r['situacao'] for r in rows], ['sugerida', 'documento_nao_conferido'])
            self.assertEqual(rows[1]['cliente_id'], '')

    def test_relatorio_existente_bloqueia_antes_da_api_e_banco(self):
        with tempfile.TemporaryDirectory() as d:
            report = Path(d)/'previas'/'clientes-nfse-202610.csv'
            report.parent.mkdir()
            report.write_text('original')
            with patch.object(previa.nfse, 'ler_zip') as read_zip, \
                    patch.object(previa, 'ler_clientes') as read_db, \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(previa.executar('arquivo.zip', date(2026, 10, 1),
                                                 path=Path(d)/'credenciais.env'), 1)
            read_zip.assert_not_called()
            read_db.assert_not_called()
            self.assertEqual(report.read_text(), 'original')


if __name__ == '__main__':
    unittest.main()
