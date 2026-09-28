"""Sonda manual de autenticação Conta Azul. Não importa Django nem consulta o banco."""
import base64
import json
import os
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, HTTPRedirectHandler, ProxyHandler, build_opener
from dotenv import dotenv_values

ENDPOINT = 'https://api-v2.contaazul.com/oauth/token'
CONFIG = Path(__file__).resolve().parent.parent / '.venv/contaazul/credenciais.env'

class SemRedirecionamento(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def executar(path=CONFIG):
    path = Path(path)
    pending = path.with_name('tokens-pendentes.env')
    reserved = False
    received = False
    try:
        if not path.is_file():
            print('FALHA: arquivo local de credenciais ausente.')
            return 1
        values = dotenv_values(path, interpolate=False)
        keys = ('CLIENT_ID', 'CLIENT_SECRET', 'REFRESH_TOKEN')
        if not all(isinstance(values.get(k), str) and values[k].strip() for k in keys):
            print('FALHA: preencha CLIENT_ID, CLIENT_SECRET e REFRESH_TOKEN no arquivo local.')
            return 1
        # Reserva exclusiva impede duas renovações simultâneas e preserva recuperação.
        with pending.open('x', encoding='utf-8'):
            pass
        reserved = True
        basic = base64.b64encode((values['CLIENT_ID'] + ':' + values['CLIENT_SECRET']).encode()).decode('ascii')
        request = Request(ENDPOINT, method='POST', data=urlencode({
            'grant_type': 'refresh_token', 'refresh_token': values['REFRESH_TOKEN']
        }).encode(), headers={'Authorization': 'Basic ' + basic,
                             'Content-Type': 'application/x-www-form-urlencoded'})
        opener = build_opener(ProxyHandler({}), SemRedirecionamento())
        with opener.open(request, timeout=20) as response:
            payload = json.loads(response.read(1048576))
        if not isinstance(payload, dict) or not all(
            isinstance(payload.get(k), str) and payload[k] for k in ('access_token', 'refresh_token')
        ):
            print('FALHA: resposta incompleta; nao repita automaticamente. Confira o acesso no portal.')
            return 1
        received = True
        values = {k: values[k] for k in keys}
        values['ACCESS_TOKEN'] = payload['access_token']
        values['REFRESH_TOKEN'] = payload['refresh_token']
        # Arquivo exclusivo desta sonda: preserva apenas as quatro chaves conhecidas.
        def quote(value):
            return "'" + value.replace('\\', '\\\\').replace("'", "\\'") + "'"
        with pending.open('w', encoding='utf-8', newline='\n') as output:
            for key, value in values.items():
                output.write(key + '=' + quote(value) + '\n')
            output.flush()
            os.fsync(output.fileno())
        os.replace(pending, path)
        reserved = False
        print('SUCESSO: autenticacao concluida; novos tokens salvos localmente. Nenhum documento consultado ou enviado.')
        return 0
    except FileExistsError:
        print('FALHA: ha execucao em andamento ou tokens-pendentes.env para recuperar. Nao repetir antes de conferir.')
        return 1
    except Exception:
        if received:
            print('FALHA ao salvar: confira tokens-pendentes.env localmente antes de tentar novamente; o token anterior pode ter sido consumido.')
        else:
            print('FALHA na autenticacao/configuracao. Nenhum segredo exibido; sem repeticao automatica. Verifique o acesso antes de repetir.')
        return 1
    finally:
        if reserved and not received:
            try:
                pending.unlink()
            except OSError:
                pass

if __name__ == '__main__':
    raise SystemExit(executar())
