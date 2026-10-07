"""Selecao de ambiente sem rede nem credenciais reais."""
import contextlib
import io
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch
import contaazul_auth as auth
import contaazul_consulta as consulta


class AmbienteTests(unittest.TestCase):
    def test_cli_auth_seleciona_arquivo_para_autorizar_e_renovar(self):
        for production in (False, True):
            expected = auth.CONFIG.parent / 'producao/credenciais.env' if production else auth.CONFIG
            for authorize in (False, True):
                args = (['--producao'] if production else []) + (['--autorizar'] if authorize else [])
                with self.subTest(production=production, authorize=authorize), patch.object(auth, 'autorizar', return_value=0) as initial, patch.object(auth, 'executar', return_value=0) as renew, contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(auth.main(args), 0)
                    (initial if authorize else renew).assert_called_once_with(expected)
                    (renew if authorize else initial).assert_not_called()

    def test_cli_consulta_usa_mesmo_ambiente_e_periodo(self):
        for production in (False, True):
            expected = auth.CONFIG.parent / 'producao/credenciais.env' if production else auth.CONFIG
            args = ['--inicio', '2026-09-28', '--fim', '2026-09-28'] + (['--producao'] if production else [])
            with self.subTest(production=production), patch.object(consulta, 'executar', return_value=0) as run, contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(consulta.main(args), 0)
                run.assert_called_once_with(date(2026, 9, 28), date(2026, 9, 28), path=expected)

    def test_producao_ausente_nao_recua_para_desenvolvimento(self):
        with tempfile.TemporaryDirectory() as directory:
            dev = Path(directory) / 'credenciais.env'
            original = 'CLIENT_ID=ficticio\nCLIENT_SECRET=ficticio\nREFRESH_TOKEN=ficticio\n'
            dev.write_text(original)
            with patch.object(auth, 'CONFIG', dev), patch.object(auth, 'CONFIG_PRODUCAO', dev.parent / 'producao/credenciais.env'), patch.object(auth, 'build_opener') as network, contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(auth.main(['--producao']), 1)
                network.assert_not_called()
            self.assertEqual(dev.read_text(), original)
