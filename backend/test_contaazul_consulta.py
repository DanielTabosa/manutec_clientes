import contextlib
import io
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch, MagicMock
from urllib.error import HTTPError
import contaazul_consulta as probe

ID = 'c6a28b6e-efe4-11ee-8ef8-8b86c5251537'

class ConsultaTests(unittest.TestCase):
    def run_probe(self, payloads, **kwargs):
        with tempfile.TemporaryDirectory() as folder:
            config = Path(folder) / 'credenciais.env'
            config.write_text('ACCESS_TOKEN=segredo-ficticio\n')
            original = config.read_bytes()
            opener = MagicMock()
            replies = []
            for payload in payloads:
                if isinstance(payload, Exception):
                    replies.append(payload)
                else:
                    reply = MagicMock()
                    reply.__enter__.return_value.read.return_value = json.dumps(payload).encode()
                    replies.append(reply)
            opener.open.side_effect = replies
            out = io.StringIO()
            with patch.object(probe, 'build_opener', return_value=opener), contextlib.redirect_stdout(out):
                result = probe.executar(date(2026,9,15), date(2026,9,28), path=config, **kwargs)
            self.assertEqual(original, config.read_bytes())
            self.assertNotIn('segredo-ficticio', out.getvalue())
            return result, out.getvalue(), opener

    def test_bounded_gets_and_no_personal_data_or_link_following(self):
        result, output, opener = self.run_probe([
            {'itens':[{'nome':'PRIVADO', 'url':'https://private.invalid'}]},
            {'itens':[{'id':ID}]},
            {'solicitacoes_cobrancas':[{'id':ID}]},
            {'id':ID,'url':'https://private.invalid','status':'REGISTRADO'},
        ])
        self.assertEqual(result, 0)
        self.assertEqual(opener.open.call_count, 4)
        for call in opener.open.call_args_list:
            req = call.args[0]
            self.assertEqual(req.get_method(), 'GET')
            self.assertTrue(req.full_url.startswith('https://api-v2.contaazul.com/'))
        self.assertNotIn('PRIVADO', output)
        self.assertNotIn('private.invalid', output)
        self.assertNotIn(ID, output)
        self.assertIn('Link de cobranca presente: sim', output)

    def test_empty_samples_are_inconclusive(self):
        result, output, opener = self.run_probe([{'itens':[]}, {'itens':[]}])
        self.assertEqual(result, 0)
        self.assertEqual(opener.open.call_count, 2)
        self.assertIn('Sem amostra', output)

    def test_unauthorized_no_retry_or_error_body(self):
        result, output, opener = self.run_probe([HTTPError('secret',401,'PRIVATE',{},None)])
        self.assertEqual(result, 1)
        self.assertEqual(opener.open.call_count, 1)
        self.assertIn('401',output)
        self.assertNotIn('PRIVATE',output)

    def test_invalid_schema_is_failure(self):
        result, _, opener = self.run_probe([{'unexpected':[]}])
        self.assertEqual(result, 1)
        self.assertEqual(opener.open.call_count, 1)

    def test_invalid_id_never_becomes_url(self):
        result, _, opener = self.run_probe([{'itens':[]},{'itens':[{'id':'../../secret'}]}])
        self.assertEqual(result, 1)
        self.assertEqual(opener.open.call_count, 2)

    def test_period_rejected_before_network(self):
        with patch.object(probe,'build_opener') as network, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(probe.executar(date(2026,9,1),date(2026,9,28)),1)
        network.assert_not_called()

if __name__ == '__main__':
    unittest.main()
