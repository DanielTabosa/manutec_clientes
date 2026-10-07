"""Conferencia de NFS-e com ZIPs ficticios, sem rede real ou banco."""
import contextlib
import hashlib
import io
import json
import tempfile
import unittest
import warnings
import zipfile
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit

import contaazul_nfse as nfse

PDF = b'%PDF-1.4\nconteudo ficticio\n%%EOF\n'
DOC = '11111111000101'


def xml(numero=101, rps=501, valor='1500.00', doc=DOC):
    return (f'<NFSe xmlns="http://www.sped.fazenda.gov.br/nfse"><infNFSe><nNFSe>{numero}</nNFSe>'
            f'<DPS><infDPS><nDPS>{rps}</nDPS><toma><CNPJ>{doc}</CNPJ></toma>'
            f'<valores><vServPrest><vServ>{valor}</vServ></vServPrest></valores>'
            '</infDPS></DPS></infNFSe></NFSe>').encode()


def nota(**kwargs):
    return {'numero_nfse': 101, 'numero_rps': 501, 'documento_cliente': DOC,
            'valor_total_nfse': 1500, 'status': 'EMITIDA', **kwargs}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.zip = self.root / 'notas.zip'
        self.config = self.root / 'credenciais.env'
        self.config.write_text('ACCESS_TOKEN=segredo-ficticio\n')

    def montar(self, entries=None):
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', UserWarning)
            with zipfile.ZipFile(self.zip, 'w') as z:
                for name, data in (entries or [('PDF/nota.pdf', PDF), ('XML/nota.xml', xml())]):
                    z.writestr(name, data)


class ArquivoTests(Base):
    def test_par_valido_sem_extrair_ou_alterar_zip(self):
        self.montar()
        antes = hashlib.sha256(self.zip.read_bytes()).digest()
        pairs, issues = nfse.ler_zip(self.zip)
        self.assertEqual(issues, [])
        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0]['valor'], Decimal('1500.00'))
        self.assertEqual(pairs[0]['documento'], DOC)
        self.assertNotIn('pdf', pairs[0])
        self.assertEqual(hashlib.sha256(self.zip.read_bytes()).digest(), antes)
        self.assertEqual(len(list(self.root.iterdir())), 2)

    def test_ausencias_duplicatas_e_pdf_invalido_ficam_pendentes(self):
        cases = [[('nota.pdf', PDF)], [('nota.xml', xml())],
                 [('a/nota.pdf', PDF), ('b/nota.pdf', PDF), ('nota.xml', xml())],
                 [('nota.pdf', b'HTML'), ('nota.xml', xml())],
                 [('nota.pdf', PDF), ('nota.xml', xml()), ('nota.xml', xml())]]
        for entries in cases:
            with self.subTest(entries=len(entries)):
                self.montar(entries)
                pairs, issues = nfse.ler_zip(self.zip)
                self.assertEqual(pairs, [])
                self.assertTrue(issues)

    def test_xml_ausente_malformado_dtd_e_valores_invalidos(self):
        cases = [b'<NFSe>', b'<outra/>', xml().replace(b'<nDPS>501</nDPS>', b''),
                 xml().replace(b'<nNFSe>101</nNFSe>', b'<nNFSe>101</nNFSe><nNFSe>102</nNFSe>'),
                 xml(valor='NaN'), xml(valor='1.001'), xml(doc=''),
                 b'<!DOCTYPE NFSe [<!ENTITY x "1">]>' + xml(),
                 xml().decode().encode('utf-16')]
        for content in cases:
            with self.subTest(content=len(content)):
                self.montar([('nota.pdf', PDF), ('nota.xml', content)])
                pairs, issues = nfse.ler_zip(self.zip)
                self.assertEqual(pairs, [])
                self.assertTrue(issues)

    def test_limites_do_zip_e_das_entradas(self):
        self.montar()
        for limit in ('MAX_ENTRADAS', 'LIMITE_TOTAL', 'LIMITE_ZIP'):
            with self.subTest(limit=limit), patch.object(nfse, limit, 1):
                with self.assertRaises(ValueError):
                    nfse.ler_zip(self.zip)
        with patch.object(nfse, 'LIMITE_XML', 10):
            pairs, issues = nfse.ler_zip(self.zip)
            self.assertEqual(pairs, [])
            self.assertTrue(issues)

    def test_mes_com_31_dias_e_fevereiro_sem_lacunas(self):
        for year, month, days in ((2026, 10, 31), (2024, 2, 29), (2026, 2, 28)):
            windows = nfse.janelas(date(year, month, 1))
            self.assertTrue(all(0 <= (b-a).days <= 14 for a, b in windows))
            self.assertEqual(sum((b-a).days+1 for a, b in windows), days)
            self.assertEqual(windows[-1][1], date(year, month, days))

    def test_estrutura_abrasf_observada_no_zip_real(self):
        content = xml().replace(b'http://www.sped.fazenda.gov.br/nfse', b'http://www.abrasf.org.br/nfse.xsd')
        content = content.replace(b'<NFSe ', b'<Nfse ').replace(b'</NFSe>', b'</Nfse>')
        self.montar([('nota.pdf', PDF), ('nota.xml', content)])
        pairs, issues = nfse.ler_zip(self.zip)
        self.assertEqual(issues, [])
        self.assertEqual(pairs[0]['numero_nfse'], 101)

    def test_caminhos_no_zip_nunca_sao_usados_para_extracao(self):
        self.montar([('../fora/nota.pdf', PDF), ('../fora/nota.xml', xml())])
        pairs, issues = nfse.ler_zip(self.zip)
        self.assertEqual(len(pairs), 1)
        self.assertFalse((self.root / 'fora').exists())
        self.assertEqual(issues, [])


class ComparacaoTests(Base):
    def setUp(self):
        super().setUp()
        self.montar()
        self.pairs, _ = nfse.ler_zip(self.zip)

    def test_xml_api_conferem_sem_exigir_contrato(self):
        ok, issues = nfse.conferir(self.pairs, [nota()])
        self.assertEqual(ok, [1])
        self.assertEqual(issues, [])

    def test_divergencias_e_dados_ausentes_nao_sao_aceitos(self):
        cases = [[], [nota(), nota()], [nota(status='CANCELADA')],
                 [nota(numero_rps=None)], [nota(documento_cliente='')],
                 [nota(valor_total_nfse=None)], [nota(valor_total_nfse='1500.01')],
                 [nota(numero_rps=999)], [nota(documento_cliente='22222222000102')]]
        for rows in cases:
            with self.subTest(rows=rows):
                ok, issues = nfse.conferir(self.pairs, rows)
                self.assertEqual(ok, [])
                self.assertEqual(len(issues), 1)

    def test_mesma_nota_em_dois_pares_bloqueia_ambos(self):
        ok, issues = nfse.conferir(self.pairs + [{**self.pairs[0], 'item': 2}], [nota()])
        self.assertEqual(ok, [])
        self.assertEqual(len(issues), 2)


class ApiTests(Base):
    def run_script(self, responses):
        opener = Mock()
        opener.open.side_effect = [io.BytesIO(json.dumps(r).encode()) if isinstance(r, dict) else r
                                   for r in responses]
        output = io.StringIO()
        with patch.object(nfse, 'build_opener', return_value=opener), contextlib.redirect_stdout(output):
            result = nfse.executar(self.zip, date(2026, 10, 1), path=self.config)
        return result, opener, output.getvalue()

    def test_fluxo_somente_get_sem_gravar_ou_expor_dados(self):
        self.montar()
        before = {p.name: p.read_bytes() for p in self.root.iterdir()}
        result, opener, output = self.run_script([{'itens': [nota()]}, {'itens': []}, {'itens': []}])
        self.assertEqual(result, 0)
        self.assertIn('Reconhecidas: 1', output)
        self.assertNotIn(DOC, output)
        self.assertNotIn('segredo-ficticio', output)
        self.assertEqual({p.name: p.read_bytes() for p in self.root.iterdir()}, before)
        self.assertEqual(opener.open.call_count, 3)
        for call in opener.open.call_args_list:
            req = call.args[0]
            self.assertEqual(req.get_method(), 'GET')
            self.assertEqual(urlsplit(req.full_url).hostname, 'api-v2.contaazul.com')
            q = parse_qs(urlsplit(req.full_url).query)
            self.assertLessEqual((date.fromisoformat(q['data_competencia_ate'][0]) -
                                 date.fromisoformat(q['data_competencia_de'][0])).days, 14)

    def test_paginacao_completa_e_limite_nao_dao_falso_sucesso(self):
        self.montar()
        full = [nota(numero_nfse=i) for i in range(50)]
        result, opener, _ = self.run_script([{'itens': full}, {'itens': [nota()]},
                                             {'itens': []}, {'itens': []}])
        self.assertEqual(result, 0)
        self.assertEqual(opener.open.call_count, 4)
        with patch.object(nfse, 'MAX_PAGINAS', 1):
            result, opener, output = self.run_script([{'itens': full}])
        self.assertEqual(result, 1)
        self.assertNotIn('Reconhecidas:', output)

    def test_erro_http_interrompe_sem_repetir_ou_exibir_corpo(self):
        self.montar()
        for code in (401, 302, 429, 500):
            result, opener, output = self.run_script([HTTPError('https://api-v2.contaazul.com/', code,
                                                               'segredo', {}, None)])
            self.assertEqual(result, 1)
            self.assertEqual(opener.open.call_count, 1)
            self.assertNotIn('segredo', output)

    def test_config_ausente_e_zip_sem_pares_nao_consultam(self):
        self.montar([('apenas.pdf', PDF)])
        result, opener, _ = self.run_script([])
        self.assertEqual(result, 2)
        opener.open.assert_not_called()
        self.montar()
        self.config.unlink()
        result, opener, _ = self.run_script([])
        self.assertEqual(result, 1)
        opener.open.assert_not_called()

    def test_resposta_malformada_ou_excessiva_interrompe(self):
        self.montar()
        for payload in ({'itens': 'errado'}, {'itens': [None]}, {'itens': [nota()] * 51}):
            result, opener, output = self.run_script([payload])
            self.assertEqual(result, 1)
            self.assertEqual(opener.open.call_count, 1)
            self.assertNotIn('Reconhecidas:', output)
        with patch.object(nfse, 'LIMITE_JSON', 10):
            result, _, _ = self.run_script([{'itens': [nota()]}])
        self.assertEqual(result, 1)

    def test_cli_ambiente_e_competencia(self):
        for prod in (False, True):
            with patch.object(nfse, 'executar', return_value=0) as run:
                self.assertEqual(nfse.main(['--zip', str(self.zip), '--competencia', '2026-10'] +
                                           (['--producao'] if prod else [])), 0)
                run.assert_called_once_with(self.zip, date(2026, 10, 1),
                                             path=nfse.CONFIG_PRODUCAO if prod else nfse.CONFIG)


if __name__ == '__main__':
    unittest.main()
