"""Download limitado: rede simulada, sem credenciais reais ou banco."""
import contextlib
import io
import json
import tempfile
import unittest
from datetime import date
from decimal import Decimal
from email.message import Message
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.error import HTTPError

import contaazul_boleto as boleto

PARCELA = '11111111-0000-4000-8000-000000000001'
CANCELADA = '22222222-0000-4000-8000-000000000001'
ATIVA = '33333333-0000-4000-8000-000000000001'
PDF = b'%PDF-1.4\nPDF ficticio para teste de transporte\n%%EOF\n'


class Resposta(io.BytesIO):
    def __init__(self, payload, tipo='application/json'):
        super().__init__(json.dumps(payload).encode() if isinstance(payload, dict) else payload)
        self.headers = Message()
        self.headers['Content-Type'] = tipo


class DownloadTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config = Path(self.tmp.name) / 'credenciais.env'
        self.config.write_text('ACCESS_TOKEN=token-ficticio\n')
        self.destino = self.config.parent / 'downloads' / 'boleto-20261013.pdf'
        self.row = {'id': PARCELA, 'data_vencimento': '2026-10-13', 'total': 1500,
                    'status': 'PENDING'}

    def respostas(self, *, rows=None, status='REGISTRADO', pdf=PDF, tipo='application/pdf'):
        return [Resposta({'itens': rows if rows is not None else [self.row]}),
                Resposta({'solicitacoes_cobrancas': [{'id': CANCELADA}, {'id': ATIVA}]}),
                Resposta({'id': CANCELADA, 'status': 'CANCELADO'}),
                Resposta({'id': ATIVA, 'status': status}), Resposta(pdf, tipo)]

    def executar(self, respostas, **kwargs):
        opener = Mock()
        opener.open.side_effect = respostas
        output = io.StringIO()
        with patch.object(boleto, 'build_opener', return_value=opener), contextlib.redirect_stdout(output):
            result = boleto.executar(date(2026, 10, 13), Decimal('1500.00'), path=self.config, **kwargs)
        return result, opener, output.getvalue()

    def test_baixa_somente_registrada_sem_vazar_token_e_sem_escrita_remota(self):
        result, opener, output = self.executar(self.respostas())
        self.assertEqual(result, 0)
        self.assertEqual(self.destino.read_bytes(), PDF)
        reqs = [c.args[0] for c in opener.open.call_args_list]
        self.assertEqual(len(reqs), 5)
        self.assertTrue(all(r.get_method() == 'GET' for r in reqs))
        self.assertTrue(all(r.full_url.startswith('https://api-v2.contaazul.com/') for r in reqs))
        self.assertTrue(reqs[-1].full_url.endswith('/' + ATIVA + '/imprimir'))
        self.assertNotIn('token-ficticio', output)
        self.assertNotIn(ATIVA, output)

    def test_arquivo_existente_preservado_sem_consulta(self):
        self.destino.parent.mkdir()
        self.destino.write_bytes(b'original')
        result, opener, _ = self.executar([])
        self.assertEqual(result, 1)
        opener.open.assert_not_called()
        self.assertEqual(self.destino.read_bytes(), b'original')

    def test_selecao_insegura_interrompe_antes_da_parcela(self):
        for rows in ([], [self.row, self.row], [self.row] * 10,
                     [{**self.row, 'status': 'PAID'}],
                     [{**self.row, 'data_vencimento': '2026-10-14'}]):
            with self.subTest(rows=len(rows)):
                result, opener, _ = self.executar(self.respostas(rows=rows))
                self.assertEqual(result, 1)
                self.assertEqual(opener.open.call_count, 1)
                self.assertFalse(self.destino.exists())

    def test_sem_cobranca_registrada_nao_baixa(self):
        result, opener, _ = self.executar(self.respostas(status='QUITADO'))
        self.assertEqual(result, 1)
        self.assertEqual(opener.open.call_count, 4)
        self.assertFalse(self.destino.exists())

    def test_duas_registradas_nao_baixa(self):
        replies = self.respostas()
        replies[2] = Resposta({'id': CANCELADA, 'status': 'REGISTRADO'})
        result, opener, _ = self.executar(replies)
        self.assertEqual(result, 1)
        self.assertEqual(opener.open.call_count, 4)

    def test_html_pdf_truncado_e_limite_nao_geram_arquivo(self):
        for data, tipo in ((b'<html>login</html>', 'text/html'),
                           (b'%PDF-1.4 incompleto', 'application/pdf'),
                           (PDF, 'text/html'),
                           (b'x' * (boleto.LIMITE_PDF + 1), 'application/pdf')):
            with self.subTest(tipo=tipo, tamanho=len(data)):
                result, _, _ = self.executar(self.respostas(pdf=data, tipo=tipo))
                self.assertEqual(result, 1)
                self.assertFalse(self.destino.exists())

    def test_http_nao_repete_nem_expoe_corpo(self):
        for code in (401, 302, 429, 500):
            with self.subTest(code=code):
                erro = HTTPError('https://api-v2.contaazul.com/privado', code, 'segredo', {}, None)
                result, opener, output = self.executar([erro])
                self.assertEqual(result, 1)
                self.assertEqual(opener.open.call_count, 1)
                self.assertNotIn('segredo', output)
                self.assertFalse(self.destino.exists())

    def test_ids_invalidos_ou_divergentes_interrompem(self):
        for variante in ('invalido', 'divergente'):
            replies = self.respostas()
            if variante == 'invalido':
                replies[1] = Resposta({'solicitacoes_cobrancas': [{'id': '../oauth/token'}]})
            else:
                replies[2] = Resposta({'id': ATIVA, 'status': 'REGISTRADO'})
            result, _, _ = self.executar(replies)
            self.assertEqual(result, 1)
            self.assertFalse(self.destino.exists())

    def test_config_ausente_nao_usa_outro_ambiente(self):
        self.config.unlink()
        result, opener, _ = self.executar([])
        self.assertEqual(result, 1)
        opener.open.assert_not_called()

    def test_publicacao_concorrente_preserva_destino_e_limpa_temporario(self):
        link_original = boleto.os.link

        def concorrente(origem, destino):
            destino.write_bytes(b'arquivo concorrente')
            link_original(origem, destino)

        with patch.object(boleto.os, 'link', side_effect=concorrente):
            result, _, _ = self.executar(self.respostas())
        self.assertEqual(result, 1)
        self.assertEqual(self.destino.read_bytes(), b'arquivo concorrente')
        self.assertEqual(list(self.destino.parent.iterdir()), [self.destino])

    def test_falha_de_gravacao_nao_deixa_pdf_ou_parcial(self):
        with patch.object(boleto.os, 'fsync', side_effect=OSError('disco')):
            result, _, _ = self.executar(self.respostas())
        self.assertEqual(result, 1)
        self.assertEqual(list(self.destino.parent.iterdir()), [])

    def test_cli_seleciona_ambiente_e_valor_decimal(self):
        for prod in (False, True):
            with patch.object(boleto, 'executar', return_value=0) as run:
                args = ['--vencimento', '2026-10-13', '--valor', '1500.00'] + (['--producao'] if prod else [])
                self.assertEqual(boleto.main(args), 0)
                run.assert_called_once_with(date(2026, 10, 13), Decimal('1500.00'),
                                            path=boleto.CONFIG_PRODUCAO if prod else boleto.CONFIG)


if __name__ == '__main__':
    unittest.main()
