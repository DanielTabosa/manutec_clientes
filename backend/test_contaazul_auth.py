"""Testes sem rede ou credenciais reais."""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
from urllib.error import HTTPError
from contaazul_auth import executar, SemRedirecionamento, preparar_autorizacao, extrair_codigo

class AuthTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'credenciais.env'
        self.original = 'CLIENT_ID=id-ficticio\nCLIENT_SECRET=segredo-ficticio\nREFRESH_TOKEN=refresh-ficticio\n'
        self.path.write_text(self.original)

    def run_auth(self, payload=None, error=None, **kwargs):
        opener = MagicMock()
        if error:
            opener.open.side_effect = error
        else:
            opener.open.return_value.__enter__.return_value.read.return_value = json.dumps(payload).encode()
        out = io.StringIO()
        with patch('contaazul_auth.build_opener', return_value=opener), contextlib.redirect_stdout(out):
            result = executar(self.path, **kwargs)
        self.assertNotIn('segredo-ficticio', out.getvalue())
        self.assertNotIn('refresh-ficticio', out.getvalue())
        self.assertNotIn('access-novo', out.getvalue())
        return result, opener

    def test_rotacao_salva_antes_de_sucesso(self):
        result, opener = self.run_auth({'access_token':'access-novo','refresh_token':'refresh-novo','token_type':'Bearer','expires_in':3600})
        self.assertEqual(result, 0)
        self.assertIn('refresh-novo', self.path.read_text())
        self.assertIn('access-novo', self.path.read_text())
        opener.open.assert_called_once()
        req = opener.open.call_args.args[0]
        self.assertEqual(req.full_url, 'https://api-v2.contaazul.com/oauth/token')
        self.assertEqual(req.method, 'POST')
        self.assertIn(b'grant_type=refresh_token', req.data)

    def test_falha_http_nao_repete_nem_sobrescreve(self):
        result, opener = self.run_auth(error=HTTPError('url',400,'segredo-ficticio',{},None))
        self.assertEqual(result, 1)
        opener.open.assert_called_once()
        self.assertEqual(self.path.read_text(),self.original)

    def test_resposta_incompleta_preserva_arquivo(self):
        result, _ = self.run_auth({'access_token':'access-novo'})
        self.assertEqual(result,1)
        self.assertEqual(self.path.read_text(),self.original)

    def test_config_incompleta_nao_faz_rede(self):
        self.path.write_text('CLIENT_ID=\n')
        result, opener = self.run_auth({})
        self.assertEqual(result,1)
        opener.open.assert_not_called()

    def test_redirecionamento_recusado(self):
        self.assertIsNone(SemRedirecionamento().redirect_request(None,None,302,'',{},'https://outro.invalid'))

    def test_falha_gravacao_nao_declara_sucesso(self):
        with patch('contaazul_auth.os.replace', side_effect=OSError('segredo-ficticio')):
            result, _ = self.run_auth({'access_token':'access-novo','refresh_token':'refresh-novo','token_type':'Bearer','expires_in':3600})
        self.assertEqual(result,1)
        self.assertEqual(self.path.read_text(),self.original)

    def test_primeira_troca_sem_refresh(self):
        self.path.write_text('CLIENT_ID=id-ficticio\nCLIENT_SECRET=segredo-ficticio\n')
        result, opener = self.run_auth({'access_token':'access-novo','refresh_token':'refresh-novo'}, code='codigo-ficticio', redirect_uri='https://contaazul.com')
        self.assertEqual(result,0)
        body=opener.open.call_args.args[0].data
        self.assertIn(b'grant_type=authorization_code',body)
        self.assertIn(b'code=codigo-ficticio',body)
        self.assertNotIn('codigo-ficticio',self.path.read_text())

    def test_autorizacao_valida_cliente_e_state(self):
        url, redirect, state = preparar_autorizacao('https://login.contaazul.com/#/oauth/authorize?client_id=id-ficticio&redirect_uri=https%3A%2F%2Fcontaazul.com&state=antigo', 'id-ficticio')
        self.assertNotEqual(state,'antigo')
        self.assertIn(state,url)
        self.assertEqual(extrair_codigo('https://contaazul.com?code=abc&state='+state,redirect,state),'abc')
        with self.assertRaises(ValueError):
            extrair_codigo('https://contaazul.com?code=abc&state=outro',redirect,state)
        with self.assertRaises(ValueError):
            extrair_codigo('https://outro.invalid?code=abc&state='+state,redirect,state)
        with self.assertRaises(ValueError):
            preparar_autorizacao('https://login.contaazul.com/#/oauth/authorize?client_id=outro&redirect_uri=https%3A%2F%2Fcontaazul.com','id-ficticio')

if __name__ == '__main__':
    unittest.main()
