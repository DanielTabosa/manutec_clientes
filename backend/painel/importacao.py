"""Importação em lote por CSV: lê, reconhece as colunas, analisa cada linha (sem gravar) e importa só após confirmação.

Regras: nada é sobrescrito. Registros já existentes são ignorados e informados. Campos ausentes ou inválidos
não bloqueiam a linha quando não são obrigatórios: ficam como pendência (aparecem na completude do cadastro).
Cada linha é gravada na sua própria transação, então um erro não desfaz as demais."""
import csv
import io
import re
import unicodedata
from datetime import date, datetime

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction

from clientes.cnpj import normalizar_cnpj
from clientes.models import (Administradora, Cliente, ClienteAdministradora, Contato, ContatoAdministradora,
                             HistoricoCNPJ)

LIMITE_BYTES = 2 * 1024 * 1024
LIMITE_LINHAS = 5000
UFS = set("AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO".split())


def _chave(texto):
    texto = unicodedata.normalize('NFKD', str(texto or '')).encode('ascii', 'ignore').decode().lower()
    return ' '.join(re.sub(r'[^a-z0-9]+', ' ', texto).split())


# campo, rótulo, obrigatório, sinônimos de cabeçalho (comparados sem acento/caixa/pontuação)
TIPOS = {
    'clientes': dict(nome='Clientes (condomínios)', permissao='clientes.add_cliente', campos=[
        ('razao_social', 'Razão social', True, ['razao social', 'razao', 'condominio', 'nome do condominio', 'cliente', 'nome', 'nome cliente']),
        ('cnpj', 'CNPJ', True, ['cnpj', 'cnpj cpf', 'cpf cnpj', 'documento', 'cnpj do condominio']),
        ('nome_fantasia', 'Nome fantasia', False, ['nome fantasia', 'fantasia', 'apelido']),
        ('cep', 'CEP', False, ['cep', 'codigo postal']),
        ('logradouro', 'Logradouro', False, ['logradouro', 'endereco', 'rua', 'avenida', 'end']),
        ('numero', 'Número', False, ['numero', 'n', 'no', 'num', 'nro']),
        ('complemento', 'Complemento', False, ['complemento', 'compl']),
        ('bairro', 'Bairro', False, ['bairro']),
        ('cidade', 'Cidade', False, ['cidade', 'municipio']),
        ('estado', 'UF', False, ['uf', 'estado']),
        ('administradora', 'Administradora', False, ['administradora', 'adm', 'administradora atual', 'empresa administradora']),
        ('observacoes', 'Observações', False, ['observacoes', 'observacao', 'obs', 'notas']),
        ('data_inicio', 'CNPJ desde', False, ['cnpj desde', 'data inicio', 'inicio', 'desde']),
    ]),
    'contatos': dict(nome='Contatos dos condomínios', permissao='clientes.add_contato', campos=[
        ('cliente', 'Condomínio (CNPJ ou nome)', True, ['condominio', 'cliente', 'cnpj', 'cnpj do condominio', 'razao social', 'cnpj cliente']),
        ('nome', 'Nome do contato', True, ['nome', 'contato', 'nome do contato', 'responsavel']),
        ('funcao', 'Função', False, ['funcao', 'cargo', 'papel']),
        ('email', 'E-mail', False, ['email', 'e mail', 'correio eletronico']),
        ('telefone', 'Telefone', False, ['telefone', 'fone', 'celular', 'whatsapp', 'tel']),
        ('data_inicio', 'Desde', False, ['desde', 'data inicio', 'inicio']),
    ]),
    'administradoras': dict(nome='Administradoras', permissao='clientes.add_administradora', campos=[
        ('razao_social', 'Razão social', True, ['razao social', 'razao', 'administradora', 'nome', 'empresa']),
        ('cnpj', 'CNPJ', False, ['cnpj', 'documento']),
        ('nome_fantasia', 'Nome fantasia', False, ['nome fantasia', 'fantasia']),
        ('telefone', 'Telefone', False, ['telefone', 'fone', 'tel']),
        ('email', 'E-mail', False, ['email', 'e mail']),
    ]),
    'contatos_administradora': dict(nome='Contatos das administradoras', permissao='clientes.add_contatoadministradora', campos=[
        ('administradora', 'Administradora (CNPJ ou nome)', True, ['administradora', 'empresa', 'cnpj', 'cnpj administradora']),
        ('nome', 'Nome do contato', True, ['nome', 'contato', 'nome do contato']),
        ('email', 'E-mail', False, ['email', 'e mail']),
        ('telefone', 'Telefone', False, ['telefone', 'fone', 'celular', 'tel']),
    ]),
}


def modelo_csv(tipo):
    campos = TIPOS[tipo]['campos']
    exemplo = {
        'clientes': ['Condomínio Exemplo', '00.000.000/0001-00', 'Residencial Exemplo', '60000-000', 'Rua Exemplo', '100', 'Bloco A', 'Centro', 'Fortaleza', 'CE', 'Administradora Exemplo', '', '2024-01-01'],
        'contatos': ['00.000.000/0001-00', 'Maria Exemplo', 'Síndica', 'maria@exemplo.com.br', '(85) 99999-0000', '2024-01-01'],
        'administradoras': ['Administradora Exemplo Ltda', '00.000.000/0001-00', 'Administradora Exemplo', '(85) 3333-0000', 'contato@exemplo.com.br'],
        'contatos_administradora': ['Administradora Exemplo Ltda', 'João Exemplo', 'joao@exemplo.com.br', '(85) 99999-1111'],
    }[tipo]
    saida = io.StringIO()
    escritor = csv.writer(saida, delimiter=';')
    escritor.writerow([rotulo for _, rotulo, _, _ in campos])
    escritor.writerow(exemplo)
    return '﻿' + saida.getvalue()


def ler(conteudo):
    """bytes → (cabeçalhos, linhas). Aceita UTF-8 (com/sem BOM) ou Windows-1252; separador ; , ou tabulação."""
    if len(conteudo) > LIMITE_BYTES:
        raise ValidationError('Arquivo maior que 2 MB. Divida em partes menores.')
    for codificacao in ('utf-8-sig', 'cp1252'):
        try:
            texto = conteudo.decode(codificacao)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValidationError('Não foi possível ler o texto do arquivo. Salve como CSV (UTF-8).')
    amostra = texto[:5000]
    try:
        separador = csv.Sniffer().sniff(amostra, delimiters=';,\t').delimiter
    except csv.Error:
        separador = ';' if amostra.count(';') >= amostra.count(',') else ','
    linhas = [l for l in csv.reader(io.StringIO(texto), delimiter=separador) if any(c.strip() for c in l)]
    if len(linhas) < 2:
        raise ValidationError('O arquivo precisa de uma linha de cabeçalho e pelo menos uma linha de dados.')
    if len(linhas) - 1 > LIMITE_LINHAS:
        raise ValidationError(f'Mais de {LIMITE_LINHAS} linhas. Divida o arquivo em partes menores.')
    return [c.strip() for c in linhas[0]], linhas[1:], texto


def mapear(tipo, cabecalhos):
    """Associa cada campo à coluna do CSV pelo nome do cabeçalho; cada coluna é usada uma vez."""
    chaves = [_chave(c) for c in cabecalhos]
    mapa, usadas = {}, set()
    campos = TIPOS[tipo]['campos']

    def candidatos(campo, rotulo, sinonimos):
        return [_chave(rotulo), _chave(campo)] + [_chave(s) for s in sinonimos]

    # 1ª passada: nome igual; 2ª: todas as palavras do sinônimo presentes no cabeçalho (ex.: "Empresa gestora").
    for comparar in (lambda chave, alvo: chave == alvo,
                     lambda chave, alvo: bool(alvo) and set(alvo.split()) <= set(chave.split())):
        for campo, rotulo, _, sinonimos in campos:
            if campo in mapa:
                continue
            for alvo in candidatos(campo, rotulo, sinonimos):
                i = next((i for i, chave in enumerate(chaves) if i not in usadas and comparar(chave, alvo)), None)
                if i is not None:
                    mapa[campo] = i
                    usadas.add(i)
                    break
    return mapa


def _valor(linha, mapa, campo):
    i = mapa.get(campo)
    return linha[i].strip() if i is not None and i < len(linha) else ''


def _data(texto):
    for formato in ('%Y-%m-%d', '%d/%m/%Y', '%d/%m/%y', '%d-%m-%Y'):
        try:
            return datetime.strptime(texto.strip(), formato).date()
        except ValueError:
            continue
    return None


def _cnpj(texto, notas):
    bruto = re.sub(r'[.\s/-]', '', texto or '').upper()
    if bruto.isdigit() and 11 < len(bruto) < 14:
        bruto = bruto.zfill(14)  # planilhas costumam cortar o zero inicial
        notas.append('CNPJ completado com zeros à esquerda')
    return normalizar_cnpj(bruto)


def _email(texto, notas):
    if not texto:
        return None
    try:
        validate_email(texto)
        return texto.lower()
    except ValidationError:
        notas.append(f'e-mail inválido ignorado ({texto})')
        return None


def _localizar_cliente(texto):
    digitos = re.sub(r'[.\s/-]', '', texto).upper()
    if re.fullmatch(r'[A-Z0-9]{12}[0-9]{2}', digitos) or (digitos.isdigit() and 11 < len(digitos) < 14):
        h = HistoricoCNPJ.objects.filter(cnpj=digitos.zfill(14), data_fim__isnull=True).first()
        return h.cliente if h else None
    achados = list(Cliente.objects.filter(razao_social__iexact=texto)[:2]) or list(Cliente.objects.filter(nome_fantasia__iexact=texto)[:2])
    return achados[0] if len(achados) == 1 else None


def _localizar_administradora(texto):
    digitos = re.sub(r'[.\s/-]', '', texto).upper()
    if re.fullmatch(r'[A-Z0-9]{12}[0-9]{2}', digitos):
        a = Administradora.objects.filter(cnpj=digitos).first()
        if a:
            return a
    achados = list(Administradora.objects.filter(razao_social__iexact=texto)[:2]) or list(Administradora.objects.filter(nome_fantasia__iexact=texto)[:2])
    return achados[0] if len(achados) == 1 else None


def analisar(tipo, linhas, mapa):
    """Sem gravar nada: para cada linha, status 'novo' | 'existente' | 'erro', dados prontos e notas."""
    faltando = [r for c, r, obrig, _ in TIPOS[tipo]['campos'] if obrig and c not in mapa]
    if faltando:
        raise ValidationError('Associe as colunas obrigatórias: ' + ', '.join(faltando) + '.')
    vistos, resultado = set(), []
    for n, linha in enumerate(linhas, start=2):
        notas, dados = [], {}
        try:
            status, chave = getattr(_Analise, tipo)(linha, mapa, dados, notas)
            if status == 'novo' and chave in vistos:
                status, notas = 'existente', notas + ['repetido no próprio arquivo']
            vistos.add(chave)
        except ValidationError as exc:
            status, notas = 'erro', notas + exc.messages
        resultado.append(dict(linha=n, status=status, dados=dados, notas=notas,
                              titulo=dados.get('razao_social') or dados.get('nome') or (linha[0] if linha else '')))
    return resultado


class _Analise:
    @staticmethod
    def clientes(linha, mapa, dados, notas):
        v = lambda c: _valor(linha, mapa, c)  # noqa: E731
        dados['razao_social'] = v('razao_social')[:150]
        if not dados['razao_social']:
            raise ValidationError('Razão social vazia.')
        if not v('cnpj'):
            raise ValidationError('CNPJ vazio (obrigatório para todo cliente).')
        dados['cnpj'] = _cnpj(v('cnpj'), notas)
        for campo, limite in (('nome_fantasia', 150), ('logradouro', 150), ('numero', 20), ('complemento', 100),
                              ('bairro', 100), ('cidade', 100), ('observacoes', 5000)):
            dados[campo] = v(campo)[:limite] or None
        cep = re.sub(r'\D', '', v('cep'))
        if cep and len(cep) != 8:
            notas.append(f'CEP inválido ignorado ({v("cep")})')
            cep = ''
        dados['cep'] = cep or None
        uf = v('estado').upper()
        if uf and uf not in UFS:
            notas.append(f'UF inválida ignorada ({uf})')
            uf = ''
        dados['estado'] = uf or None
        dados['data_inicio'] = _data(v('data_inicio')) or date.today()
        if v('administradora'):
            adm = _localizar_administradora(v('administradora'))
            dados['administradora'] = adm.pk if adm else None
            dados['administradora_nova'] = None if adm else v('administradora')[:150]
            if not adm:
                notas.append(f'administradora "{v("administradora")}" será cadastrada')
        faltam = [n for c, n in (('logradouro', 'logradouro'), ('numero', 'número'), ('bairro', 'bairro'),
                                 ('cidade', 'cidade'), ('estado', 'UF'), ('cep', 'CEP')) if not dados[c]]
        if faltam:
            notas.append('endereço pendente: ' + ', '.join(faltam))
        if HistoricoCNPJ.objects.filter(cnpj=dados['cnpj']).exists():
            return 'existente', dados['cnpj']
        return 'novo', dados['cnpj']

    @staticmethod
    def contatos(linha, mapa, dados, notas):
        v = lambda c: _valor(linha, mapa, c)  # noqa: E731
        cliente = _localizar_cliente(v('cliente'))
        if not cliente:
            raise ValidationError(f'Condomínio não encontrado: "{v("cliente")}". Use o CNPJ atual ou o nome exato.')
        dados.update(cliente=cliente.pk, cliente_nome=cliente.razao_social, nome=v('nome')[:150])
        if not dados['nome']:
            raise ValidationError('Nome do contato vazio.')
        dados.update(funcao=v('funcao')[:100] or None, telefone=v('telefone')[:20] or None,
                     email=_email(v('email'), notas), data_inicio=_data(v('data_inicio')) or date.today())
        if not dados['email']:
            notas.append('sem e-mail: não poderá receber documentos por e-mail')
        chave = (cliente.pk, dados['nome'].lower())
        if Contato.objects.filter(cliente=cliente, nome__iexact=dados['nome'], data_fim__isnull=True).exists():
            return 'existente', chave
        return 'novo', chave

    @staticmethod
    def administradoras(linha, mapa, dados, notas):
        v = lambda c: _valor(linha, mapa, c)  # noqa: E731
        dados['razao_social'] = v('razao_social')[:150]
        if not dados['razao_social']:
            raise ValidationError('Razão social vazia.')
        dados['cnpj'] = _cnpj(v('cnpj'), notas) if v('cnpj') else None
        dados.update(nome_fantasia=v('nome_fantasia')[:150] or None, telefone=v('telefone')[:20] or None,
                     email=_email(v('email'), notas))
        existe = Administradora.objects.filter(razao_social__iexact=dados['razao_social'])
        if dados['cnpj']:
            existe = existe | Administradora.objects.filter(cnpj=dados['cnpj'])
        chave = dados['cnpj'] or dados['razao_social'].lower()
        return ('existente' if existe.exists() else 'novo'), chave

    @staticmethod
    def contatos_administradora(linha, mapa, dados, notas):
        v = lambda c: _valor(linha, mapa, c)  # noqa: E731
        adm = _localizar_administradora(v('administradora'))
        if not adm:
            raise ValidationError(f'Administradora não encontrada: "{v("administradora")}". Importe as administradoras antes.')
        dados.update(administradora=adm.pk, administradora_nome=adm.razao_social, nome=v('nome')[:150])
        if not dados['nome']:
            raise ValidationError('Nome do contato vazio.')
        dados.update(email=_email(v('email'), notas), telefone=v('telefone')[:20] or None)
        chave = (adm.pk, dados['nome'].lower())
        if ContatoAdministradora.objects.filter(administradora=adm, nome__iexact=dados['nome'], encerrado_em__isnull=True).exists():
            return 'existente', chave
        return 'novo', chave


def importar(tipo, analise):
    """Grava as linhas 'novo' (reanalisadas no momento da gravação). Retorna contagens e falhas por linha."""
    from clientes.services import alterar_administradora, cadastrar_cliente
    criados, falhas = 0, []
    for item in analise:
        if item['status'] != 'novo':
            continue
        d = dict(item['dados'])
        try:
            with transaction.atomic():
                if tipo == 'clientes':
                    adm_id, adm_nova = d.pop('administradora', None), d.pop('administradora_nova', None)
                    cliente = cadastrar_cliente(exigir_endereco=False, **d)
                    if adm_nova:
                        existente = Administradora.objects.filter(razao_social__iexact=adm_nova).first()
                        adm_id = existente.pk if existente else Administradora.objects.create(razao_social=adm_nova).pk
                    if adm_id:
                        alterar_administradora(cliente.pk, acao='vincular', data=min(d['data_inicio'], date.today()),
                                               administradora=Administradora.objects.get(pk=adm_id))
                elif tipo == 'contatos':
                    d.pop('cliente_nome', None)
                    obj = Contato(cliente_id=d.pop('cliente'), **d)
                    obj.full_clean()
                    obj.save()
                elif tipo == 'administradoras':
                    obj = Administradora(**d)
                    obj.full_clean()
                    obj.save()
                elif tipo == 'contatos_administradora':
                    d.pop('administradora_nome', None)
                    ContatoAdministradora(administradora_id=d.pop('administradora'), **d).save()
            criados += 1
        except ValidationError as exc:
            falhas.append((item['linha'], item['titulo'], '; '.join(exc.messages)))
        except Exception as exc:  # integridade/concorrência: registra e segue
            falhas.append((item['linha'], item['titulo'], type(exc).__name__))
    return dict(criados=criados, falhas=falhas)
