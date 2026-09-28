"""Sonda manual de autenticação Conta Azul. Não importa Django nem consulta o banco."""
import argparse
import getpass
import secrets
import warnings
import webbrowser
import base64
import json
import os
from pathlib import Path
from urllib.parse import urlencode, urlsplit, parse_qs
from urllib.request import Request, HTTPRedirectHandler, ProxyHandler, build_opener
from dotenv import dotenv_values

ENDPOINT = 'https://api-v2.contaazul.com/oauth/token'
CONFIG = Path(__file__).resolve().parent.parent / '.venv/contaazul/credenciais.env'

class SemRedirecionamento(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def executar(path=CONFIG, *, code=None, redirect_uri=None):
    path = Path(path)
    pending = path.with_name('tokens-pendentes.env')
    reserved = False
    received = False
    try:
        if not path.is_file():
            print('FALHA: arquivo local de credenciais ausente.')
            return 1
        values = dotenv_values(path, interpolate=False)
        keys = ('CLIENT_ID', 'CLIENT_SECRET') if code is not None else ('CLIENT_ID', 'CLIENT_SECRET', 'REFRESH_TOKEN')
        if not all(isinstance(values.get(k), str) and values[k].strip() for k in keys):
            print('FALHA: preencha os campos exigidos: ' + ', '.join(keys) + '.')
            return 1
        if code is not None and (not code.strip() or not redirect_uri):
            print('FALHA: codigo ou redirecionamento ausente.')
            return 1
        form = ({'grant_type': 'authorization_code', 'code': code, 'redirect_uri': redirect_uri}
                if code is not None else {'grant_type': 'refresh_token', 'refresh_token': values['REFRESH_TOKEN']})
        # Reserva exclusiva impede duas renovações simultâneas e preserva recuperação.
        with pending.open('x', encoding='utf-8'):
            pass
        reserved = True
        basic = base64.b64encode((values['CLIENT_ID'] + ':' + values['CLIENT_SECRET']).encode()).decode('ascii')
        request = Request(ENDPOINT, method='POST', data=urlencode(form).encode(), headers={'Authorization': 'Basic ' + basic,
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

def preparar_autorizacao(url, client_id):
    parsed = urlsplit(url.strip())
    if parsed.scheme != 'https' or parsed.netloc != 'login.contaazul.com' or parsed.path not in ('', '/'):
        raise ValueError('URL de autorizacao invalida')
    route, _, query = parsed.fragment.partition('?')
    params = parse_qs(query)
    if route != '/oauth/authorize' or params.get('client_id') != [client_id]:
        raise ValueError('Aplicacao diferente')
    redirects = params.get('redirect_uri', [])
    if len(redirects) != 1:
        raise ValueError('Redirecionamento ausente')
    redirect = redirects[0]
    target = urlsplit(redirect)
    if target.scheme != 'https' or not target.netloc or target.username or target.password or target.query or target.fragment:
        raise ValueError('Redirecionamento nao suportado nesta sonda')
    state = secrets.token_urlsafe(32)
    args = dict(response_type='code', client_id=client_id, redirect_uri=redirect, state=state,
                scope='openid profile aws.cognito.signin.user.admin')
    return 'https://login.contaazul.com/#/oauth/authorize?' + urlencode(args), redirect, state


def extrair_codigo(url, redirect, state):
    parsed, expected = urlsplit(url.strip()), urlsplit(redirect)
    if (parsed.scheme, parsed.netloc, parsed.path.rstrip('/')) != (expected.scheme, expected.netloc, expected.path.rstrip('/')):
        raise ValueError('Retorno diferente')
    params = parse_qs(parsed.query)
    if parsed.fragment or params.get('state') != [state] or 'error' in params or len(params.get('code', [])) != 1:
        raise ValueError('Retorno invalido')
    return params['code'][0]


def autorizar(path=CONFIG):
    try:
        if Path(path).with_name('tokens-pendentes.env').exists():
            print('FALHA: confira tokens-pendentes.env antes de iniciar outra autorizacao.')
            return 1
        values = dotenv_values(path, interpolate=False)
        if not all(values.get(k, '').strip() for k in ('CLIENT_ID', 'CLIENT_SECRET')):
            print('FALHA: preencha CLIENT_ID e CLIENT_SECRET no arquivo local primeiro.')
            return 1
        with warnings.catch_warnings():
            warnings.simplefilter('error', getpass.GetPassWarning)
            link = getpass.getpass('Cole a URL para obter o Codigo de Autorizacao do portal e pressione Enter (entrada oculta): ')
            url, redirect, state = preparar_autorizacao(link, values['CLIENT_ID'])
            print('Abrindo autorizacao. Use o usuario de teste da aplicacao de desenvolvimento.')
            if not webbrowser.open(url):
                print('FALHA: nao foi possivel abrir o navegador.')
                return 1
            returned = getpass.getpass('Apos autorizar, copie o endereco COMPLETO da pagina de retorno, cole aqui e pressione Enter (entrada oculta): ')
        code = extrair_codigo(returned, redirect, state)
        return executar(path, code=code, redirect_uri=redirect)
    except (Exception, KeyboardInterrupt):
        print('FALHA: autorizacao interrompida ou URL/aplicacao/state invalido. Nenhum segredo exibido; nenhuma repeticao automatica.')
        return 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Teste local de autenticacao Conta Azul, sem exibir tokens.')
    parser.add_argument('--autorizar', action='store_true', help='Obter os primeiros tokens pelo navegador e colagem local oculta.')
    args = parser.parse_args()
    raise SystemExit(autorizar() if args.autorizar else executar())
