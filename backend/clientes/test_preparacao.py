import shutil
import tempfile
from datetime import date

from django.contrib.auth.models import Permission, User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, connection, transaction
from django.test import TransactionTestCase, override_settings
from django.core import mail
from django.core.mail.backends.locmem import EmailBackend as LocmemBackend
from django.urls import reverse

from . import destinatarios as d
from . import preparacao as p
from .models import (Administradora, Cliente, ClienteAdministradora, Contato, ContatoAdministradora,
                     HistoricoCNPJ, Responsabilidade, DocumentoPreparacao, PreparacaoEnvio, ItemPreparacao)


class FalhaParaBruno(LocmemBackend):
    def send_messages(self, messages):
        if any('bruno' in m.to[0] for m in messages):
            raise OSError('550 caixa indisponível')
        return super().send_messages(messages)


class ConexaoRecusada(LocmemBackend):
    def open(self):
        raise OSError('autenticação recusada')


SMTP_TESTE = dict(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', EMAIL_HOST='smtp.exemplo.test',
                  DEFAULT_FROM_EMAIL='Manutec <envio@exemplo.test>', EMAIL_REPLY_TO='')


def pdf(nome, conteudo='a'):
    return SimpleUploadedFile(nome, f'%PDF-1.4\n{conteudo}\n%%EOF\n'.encode(), content_type='application/pdf')


class BasePreparacao(TransactionTestCase):
    def setUp(self):
        self.pasta = tempfile.mkdtemp()
        self.settings_ctx = override_settings(ARQUIVOS_PRIVADOS_DIR=self.pasta)
        self.settings_ctx.enable()
        if 'clientes' not in connection.introspection.table_names():
            with connection.schema_editor() as editor:
                for m in (Cliente, HistoricoCNPJ, Contato, Administradora, ClienteAdministradora, ContatoAdministradora, Responsabilidade):
                    editor.create_model(m)
        self.c = Cliente.objects.create(razao_social='Condomínio QA')
        self.a = Administradora.objects.create(razao_social='Empresa QA')
        self.v = ClienteAdministradora.objects.create(cliente=self.c, administradora=self.a, data_inicio=date(2020, 1, 1))
        ana = Contato.objects.create(cliente=self.c, nome='Ana', email='ana@exemplo.test', data_inicio=date(2020, 1, 1))
        davi = Contato.objects.create(cliente=self.c, nome='Davi', data_inicio=date(2020, 1, 1))
        eva = Contato.objects.create(cliente=self.c, nome='Eva', email=' ANA@exemplo.test ', data_inicio=date(2020, 1, 1))
        bruno = ContatoAdministradora.objects.create(administradora=self.a, nome='Bruno', email='bruno@exemplo.test')
        carla = ContatoAdministradora.objects.create(administradora=self.a, nome='Carla', email='carla@exemplo.test')
        d.salvar(administradora_id=self.a.pk, numero=0, itens=[dict(contato_administradora_id=bruno.pk, boleto=True),
                                                                dict(contato_administradora_id=carla.pk, nota_fiscal=True)])
        d.salvar(cliente_id=self.c.pk, vinculo_id=self.v.pk, numero=0, modo='usar', itens=[
            dict(contato_id=ana.pk, boleto=True, nota_fiscal=True), dict(contato_id=davi.pk, boleto=True, nota_fiscal=True),
            dict(contato_id=eva.pk, laudo=True)])
        self.user = User.objects.create_superuser('qa', 'qa@example.invalid', 'somente-teste')

    def tearDown(self):
        self.settings_ctx.disable()
        shutil.rmtree(self.pasta, ignore_errors=True)
        with connection.cursor() as cursor:
            for table in ('clientes_itempreparacao', 'clientes_destinatariopreparacao', 'clientes_documentopreparacao', 'clientes_preparacaoenvio',
                          'clientes_itemdestinatario', 'clientes_revisaodestinatarios', 'clientes_configuracaodestinatarios', 'responsabilidades',
                          'contatos_administradora', 'cliente_administradora', 'administradoras', 'contatos', 'historico_cnpj', 'clientes'):
                cursor.execute('DELETE FROM ' + connection.ops.quote_name(table))

    def nova(self, *docs):
        prep = p.criar(self.c.pk, self.user)
        for nome, categoria, conteudo in docs:
            p.anexar(prep.pk, pdf(nome, conteudo), categoria, '', self.user)
        return prep

    def confirmar(self, prep, motivo=''):
        prep.refresh_from_db()
        return p.confirmar(prep.pk, impressao=p.plano(prep)['impressao'], assunto=prep.assunto, mensagem=prep.mensagem,
                           autor=self.user, motivo_reenvio=motivo)

    def confirmada(self):
        prep = self.nova(('boleto.pdf', 'boleto', 'b'), ('nota.pdf', 'nota_fiscal', 'n'))
        self.confirmar(prep)
        prep.refresh_from_db()
        return prep


class PreparacaoTests(BasePreparacao):
    def test_plano_categorias_independentes_sem_email_e_mesmo_email(self):
        prep = self.nova(('boleto.pdf', 'boleto', 'b'), ('nota.pdf', 'nota_fiscal', 'n'))
        plano = p.plano(prep)
        envios = {g['email']: [x.nome_original for x in g['documentos']] for g in plano['envios']}
        self.assertEqual(envios, {'ana@exemplo.test': ['boleto.pdf', 'nota.pdf'], 'bruno@exemplo.test': ['boleto.pdf'],
                                  'carla@exemplo.test': ['nota.pdf']})
        self.assertEqual([c['nome'] for c in plano['sem_email']], ['Davi'])
        self.assertEqual([c['nome'] for c in plano['sem_anexo']], ['Eva'])
        p.anexar(prep.pk, pdf('laudo.pdf', 'l'), 'laudo', '', self.user)
        ana = [g for g in p.plano(prep)['envios'] if g['email'] == 'ana@exemplo.test'][0]
        self.assertEqual(ana['nomes'], 'Ana, Eva')
        self.assertEqual(len(ana['documentos']), 3)

    def test_validacao_de_arquivos_e_duplicidade(self):
        prep = self.nova()
        for arquivo, msg in ((SimpleUploadedFile('x.pdf', b'<html>'), 'PDF completo'), (pdf('x.txt'), 'somente arquivos PDF')):
            with self.assertRaisesMessage(ValidationError, msg):
                p.anexar(prep.pk, arquivo, 'boleto', '', self.user)
        with self.assertRaisesMessage(ValidationError, 'categoria'):
            p.anexar(prep.pk, pdf('a.pdf'), 'outra', '', self.user)
        doc = p.anexar(prep.pk, pdf('a.pdf'), 'boleto', 'venc. 13/11', self.user)
        with self.assertRaisesMessage(ValidationError, 'já está anexado'):
            p.anexar(prep.pk, pdf('copia.pdf'), 'nota_fiscal', '', self.user)
        p.remover_documento(prep.pk, doc.pk)
        p.anexar(prep.pk, pdf('a.pdf'), 'boleto', '', self.user)
        self.assertEqual(DocumentoPreparacao.objects.filter(preparacao=prep).count(), 2)
        with self.assertRaises(IntegrityError), transaction.atomic():
            DocumentoPreparacao.objects.create(preparacao=prep, categoria='boleto', arquivo='x.pdf', nome_original='x', tamanho=1,
                                               sha256=prep.documentos.filter(removido_em__isnull=True).get().sha256)

    def test_confirmacao_registra_retrato_e_bloqueia_mudancas(self):
        prep = self.nova(('boleto.pdf', 'boleto', 'b'))
        with self.assertRaisesMessage(ValidationError, 'mudaram'):
            p.confirmar(prep.pk, impressao='antiga', assunto='A', mensagem='M', autor=self.user)
        self.confirmar(prep)
        prep.refresh_from_db()
        self.assertEqual(prep.status, 'confirmada')
        self.assertEqual(sorted(prep.destinatarios.values_list('email', flat=True)), ['ana@exemplo.test', 'bruno@exemplo.test'])
        for acao in (lambda: p.anexar(prep.pk, pdf('n.pdf', 'n'), 'nota_fiscal', '', self.user), lambda: self.confirmar(prep)):
            with self.assertRaisesMessage(ValidationError, 'rascunho'):
                acao()

    def test_reenvio_exige_motivo_e_fica_registrado(self):
        self.confirmar(self.nova(('boleto.pdf', 'boleto', 'b')))
        segunda = self.nova(('boleto-de-novo.pdf', 'boleto', 'b'), ('nota.pdf', 'nota_fiscal', 'n'))
        conflitos = p.plano(segunda)['conflitos']
        self.assertEqual(sorted(c['email'] for c in conflitos), ['ana@exemplo.test', 'bruno@exemplo.test'])
        with self.assertRaisesMessage(ValidationError, 'motivo'):
            self.confirmar(segunda)
        self.confirmar(segunda, motivo='Cliente pediu novamente')
        segunda.refresh_from_db()
        self.assertEqual(segunda.motivo_reenvio, 'Cliente pediu novamente')
        reenvios = ItemPreparacao.objects.filter(destinatario__preparacao=segunda, reenvio=True)
        self.assertEqual(sorted(i.destinatario.email for i in reenvios), ['ana@exemplo.test', 'bruno@exemplo.test'])
        self.assertFalse(ItemPreparacao.objects.filter(destinatario__preparacao=segunda, documento__nome_original='nota.pdf', reenvio=True).exists())

    def test_cancelada_nao_conta_como_reenvio(self):
        prep = self.nova(('boleto.pdf', 'boleto', 'b'))
        p.cancelar(prep.pk)
        self.assertEqual(p.plano(self.nova(('boleto.pdf', 'boleto', 'b')))['conflitos'], [])

    def test_painel_permissoes_fluxo_e_arquivo(self):
        operador = User.objects.create_user('op', password='somente-teste', is_staff=True)
        operador.user_permissions.add(*Permission.objects.filter(codename__in=['view_preparacaoenvio', 'add_preparacaoenvio', 'view_cliente']))
        self.client.force_login(operador)
        resposta = self.client.post(reverse('admin:clientes_preparacaoenvio_add'), {'cliente': self.c.pk})
        prep = PreparacaoEnvio.objects.get()
        self.assertRedirects(resposta, reverse('admin:clientes_preparacaoenvio_change', args=[prep.pk]), fetch_redirect_response=False)
        url = reverse('admin:clientes_preparacaoenvio_change', args=[prep.pk])
        self.client.post(url, {'acao': 'anexar', 'categoria': 'boleto', 'arquivos': [pdf('b.pdf', 'b'), SimpleUploadedFile('ruim.pdf', b'x')]})
        pagina = self.client.get(url).content.decode()
        self.assertIn('b.pdf', pagina)
        self.assertIn('Sem e-mail', pagina)
        self.assertNotIn('Confirmar preparação', pagina)
        self.assertEqual(self.client.post(url, {'acao': 'confirmar'}).status_code, 403)
        doc = prep.documentos.get()
        arquivo = self.client.get(reverse('admin:clientes_preparacaoenvio_documento', args=[prep.pk, doc.pk]))
        self.assertEqual(arquivo['Content-Type'], 'application/pdf')
        self.assertTrue(arquivo['Content-Disposition'].startswith('inline'))
        self.assertTrue(b''.join(arquivo.streaming_content).startswith(b'%PDF-'))
        operador.user_permissions.add(Permission.objects.get(codename='confirmar_preparacaoenvio'))
        operador = User.objects.get(pk=operador.pk)
        self.client.force_login(operador)
        impressao = p.plano(prep)['impressao']
        resposta = self.client.post(url, {'acao': 'confirmar', 'impressao': impressao, 'assunto': 'Assunto', 'mensagem': 'Texto'})
        self.assertContains(resposta, 'Marque a conferência')
        self.client.post(url, {'acao': 'confirmar', 'conferido': 'sim', 'impressao': impressao, 'assunto': 'Assunto', 'mensagem': 'Texto'})
        prep.refresh_from_db()
        self.assertEqual((prep.status, prep.confirmada_por, prep.assunto), ('confirmada', operador, 'Assunto'))
        self.assertContains(self.client.get(url), 'Nenhuma mensagem foi enviada')
        self.client.logout()
        self.assertEqual(self.client.get(reverse('admin:clientes_preparacaoenvio_documento', args=[prep.pk, doc.pk])).status_code, 302)
        leitor = User.objects.create_user('leitor', password='somente-teste', is_staff=True)
        self.client.force_login(leitor)
        self.assertEqual(self.client.get(url).status_code, 403)

    def confirmada(self):
        prep = self.nova(('boleto.pdf', 'boleto', 'b'), ('nota.pdf', 'nota_fiscal', 'n'))
        self.confirmar(prep)
        return prep

    def status(self, prep):
        return dict(prep.destinatarios.values_list('email', 'status_envio'))

    @override_settings(**SMTP_TESTE)
    def test_envio_anexos_por_destinatario_e_sem_duplicidade(self):
        rascunho = self.nova(('x.pdf', 'boleto', 'x'))
        with self.assertRaisesMessage(ValidationError, 'confirmadas'):
            p.enviar(rascunho.pk, self.user)
        prep = self.confirmada()
        self.assertEqual(p.enviar(prep.pk, self.user), dict(aceitos=3, falhas=0))
        anexos = {m.to[0]: sorted(a[0] for a in m.attachments) for m in mail.outbox}
        self.assertEqual(anexos, {'ana@exemplo.test': ['boleto.pdf', 'nota.pdf'], 'bruno@exemplo.test': ['boleto.pdf'],
                                  'carla@exemplo.test': ['nota.pdf']})
        self.assertTrue(all(m.subject == prep.assunto and m.from_email == 'Manutec <envio@exemplo.test>' for m in mail.outbox))
        self.assertTrue(all(m.attachments[0][1].startswith(b'%PDF-') for m in mail.outbox))
        self.assertEqual(set(self.status(prep).values()), {'aceito'})
        self.assertTrue(all(prep.destinatarios.values_list('message_id', flat=True)))
        with self.assertRaisesMessage(ValidationError, 'Nenhum destinatário pendente'):
            p.enviar(prep.pk, self.user)
        self.assertEqual(len(mail.outbox), 3)

    @override_settings(**dict(SMTP_TESTE, EMAIL_BACKEND='clientes.test_preparacao.FalhaParaBruno'))
    def test_falha_parcial_e_nova_tentativa_somente_da_falha(self):
        prep = self.confirmada()
        self.assertEqual(p.enviar(prep.pk, self.user), dict(aceitos=2, falhas=1))
        self.assertEqual(self.status(prep)['bruno@exemplo.test'], 'falha')
        self.assertIn('550', prep.destinatarios.get(email='bruno@exemplo.test').ultimo_erro)
        with override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'):
            mail.outbox = []
            self.assertEqual(p.enviar(prep.pk, self.user), dict(aceitos=1, falhas=0))
            self.assertEqual([m.to[0] for m in mail.outbox], ['bruno@exemplo.test'])
        self.assertEqual(prep.destinatarios.get(email='bruno@exemplo.test').tentativas, 2)

    @override_settings(**dict(SMTP_TESTE, EMAIL_BACKEND='clientes.test_preparacao.ConexaoRecusada'))
    def test_conexao_recusada_marca_falha_sem_enviar(self):
        prep = self.confirmada()
        self.assertEqual(p.enviar(prep.pk, self.user), dict(aceitos=0, falhas=3))
        self.assertIn('autenticação recusada', prep.destinatarios.first().ultimo_erro)

    @override_settings(**SMTP_TESTE)
    def test_indeterminado_so_com_confirmacao_explicita(self):
        prep = self.confirmada()
        prep.destinatarios.update(status_envio='enviando')
        with self.assertRaisesMessage(ValidationError, 'Nenhum destinatário pendente'):
            p.enviar(prep.pk, self.user)
        self.assertEqual(p.enviar(prep.pk, self.user, incluir_indeterminados=True)['aceitos'], 3)

    def test_envio_sem_configuracao_e_permissao_no_painel(self):
        prep = self.confirmada()
        with override_settings(EMAIL_HOST='', DEFAULT_FROM_EMAIL=''):
            with self.assertRaisesMessage(ValidationError, 'não configurado'):
                p.enviar(prep.pk, self.user)
            self.client.force_login(self.user)
            self.assertContains(self.client.get(reverse('admin:clientes_preparacaoenvio_change', args=[prep.pk])), 'ainda não configurado')
        operador = User.objects.create_user('op2', password='somente-teste', is_staff=True)
        operador.user_permissions.add(*Permission.objects.filter(codename__in=['view_preparacaoenvio', 'add_preparacaoenvio', 'confirmar_preparacaoenvio']))
        self.client.force_login(operador)
        url = reverse('admin:clientes_preparacaoenvio_change', args=[prep.pk])
        self.assertEqual(self.client.post(url, {'acao': 'enviar'}).status_code, 403)
        with override_settings(**SMTP_TESTE):
            self.client.force_login(self.user)
            self.client.post(url, {'acao': 'enviar'})
            self.assertEqual(len(mail.outbox), 3)
            pagina = self.client.get(url).content.decode()
            self.assertIn('Aceito pelo servidor', pagina)
            self.assertNotIn('Enviar e-mails (', pagina)


def zip_nfse(*notas):
    import io as _io
    import zipfile
    buffer = _io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as z:
        for numero, documento in notas:
            z.writestr(f'PDF/nota-{numero}.pdf', f'%PDF-1.4\nnota {numero}\n%%EOF\n'.encode())
            z.writestr(f'XML/nota-{numero}.xml', (
                f'<NFSe xmlns="http://www.sped.fazenda.gov.br/nfse"><infNFSe><nNFSe>{numero}</nNFSe>'
                f'<DPS><infDPS><nDPS>{numero + 400}</nDPS><toma><CNPJ>{documento}</CNPJ></toma>'
                '<valores><vServPrest><vServ>1500.00</vServ></vServPrest></valores></infDPS></DPS></infNFSe></NFSe>').encode())
    return SimpleUploadedFile('notas.zip', buffer.getvalue(), content_type='application/zip')


class ContaAzulPreparacaoTests(BasePreparacao):
    CNPJ = '11111111000101'

    def setUp(self):
        super().setUp()
        HistoricoCNPJ.objects.create(cliente=self.c, cnpj=self.CNPJ, data_inicio=date(2020, 1, 1))

    def nota_api(self, numero, status='EMITIDA', documento=None):
        return {'numero_nfse': numero, 'numero_rps': numero + 400, 'documento_cliente': documento or self.CNPJ,
                'valor_total_nfse': 1500, 'status': status}

    def test_valor_em_formato_brasileiro(self):
        from decimal import Decimal
        self.assertEqual(p.ler_valor('R$ 1.500,00'), Decimal('1500.00'))
        self.assertEqual(p.ler_valor('1500.5'), Decimal('1500.5'))
        for invalido in ('abc', '0', '10,555'):
            with self.assertRaises(ValidationError):
                p.ler_valor(invalido)

    def test_zip_anexa_so_notas_do_cliente_emitidas(self):
        from unittest.mock import patch
        prep = self.nova()
        api = [self.nota_api(101), self.nota_api(102, status='CANCELAMENTO_MANUAL'), self.nota_api(103, documento='22222222000102')]
        with override_settings(CONTAAZUL_AMBIENTE='producao'), patch('contaazul_nfse.consultar', return_value=api) as consultar:
            r = p.importar_nfse_zip(prep.pk, zip_nfse((101, self.CNPJ), (102, self.CNPJ), (103, '22222222000102')), date(2026, 10, 1), self.user)
            self.assertEqual(consultar.call_args.args[0], date(2026, 10, 1))
            self.assertEqual((r['anexadas'], r['outros_tomadores']), ([101], 1))
            self.assertEqual(r['pendentes'], [(102, 'status diferente de EMITIDA')])
            doc = prep.documentos.get()
            self.assertEqual((doc.categoria, doc.origem, doc.nome_original), ('nota_fiscal', 'zip_nfse', 'nota-101.pdf'))
            r = p.importar_nfse_zip(prep.pk, zip_nfse((101, self.CNPJ)), date(2026, 10, 1), self.user)
            self.assertIn('já está anexado', r['pendentes'][0][1])
            with self.assertRaisesMessage(ValidationError, 'tomador o CNPJ atual'):
                p.importar_nfse_zip(prep.pk, zip_nfse((103, '22222222000102')), date(2026, 10, 1), self.user)
        with override_settings(CONTAAZUL_AMBIENTE='producao'), patch('contaazul_nfse.consultar', side_effect=ValueError()):
            with self.assertRaisesMessage(ValidationError, 'Nada foi anexado'):
                p.importar_nfse_zip(prep.pk, zip_nfse((104, self.CNPJ)), date(2026, 10, 1), self.user)
        with override_settings(CONTAAZUL_AMBIENTE='producao'):
            with self.assertRaisesMessage(ValidationError, 'ZIP inválido'):
                p.importar_nfse_zip(prep.pk, SimpleUploadedFile('x.zip', b'nao e zip'), date(2026, 10, 1), self.user)
        self.assertEqual(prep.documentos.count(), 1)

    CONTAS = [
        {'id': '11111111-0000-4000-8000-000000000001', 'cliente': 'Outro Prédio', 'descricao': 'Venda 10', 'total': None,
         'nao_pago': None, 'status': 'Em aberto'},
        {'id': '11111111-0000-4000-8000-000000000002', 'cliente': 'CONDOMINIO QA', 'descricao': 'Parcela 2/6', 'total': None,
         'nao_pago': None, 'status': 'Em aberto'},
    ]

    def contas(self):
        from decimal import Decimal
        return [dict(c, total=Decimal('3000.00'), nao_pago=Decimal('500.00')) for c in self.CONTAS]

    def test_lista_parcelas_com_provavel_cliente_primeiro_e_filtro(self):
        from unittest.mock import patch
        from decimal import Decimal
        from urllib.error import HTTPError
        prep = self.nova()
        venc = date(2026, 11, 13)
        with self.assertRaisesMessage(ValidationError, 'não configurada'):
            p.listar_boletos(prep.pk, venc)
        with override_settings(CONTAAZUL_AMBIENTE='producao'):
            with patch('contaazul_boleto.listar_contas', return_value=self.contas()):
                contas = p.listar_boletos(prep.pk, venc)
                self.assertEqual([(c['cliente'], c['provavel']) for c in contas], [('CONDOMINIO QA', True), ('Outro Prédio', False)])
                self.assertEqual(contas[0]['valor_br'], '500,00')
                self.assertEqual(len(p.listar_boletos(prep.pk, venc, Decimal('500.00'))), 2)
                self.assertEqual(p.listar_boletos(prep.pk, venc, Decimal('1.00')), [])
            with patch('contaazul_boleto.listar_contas', side_effect=HTTPError('https://x', 401, 'n', None, None)):
                with self.assertRaisesMessage(ValidationError, 'HTTP 401'):
                    p.listar_boletos(prep.pk, venc)
            with patch('contaazul_boleto.listar_contas', side_effect=ValueError()):
                with self.assertRaisesMessage(ValidationError, 'Não foi possível listar'):
                    p.listar_boletos(prep.pk, venc)

    def test_anexa_boleto_da_parcela_escolhida(self):
        from unittest.mock import patch
        prep = self.nova()
        info = {'descricao': 'Parcela 2/6', 'data_vencimento': '2026-11-13', 'nao_pago': 500}
        with override_settings(CONTAAZUL_AMBIENTE='producao'):
            with patch('contaazul_boleto.baixar_pdf_parcela', return_value=(b'%PDF-1.4\nparcela\n%%EOF\n', info)) as baixar:
                doc = p.importar_boleto_parcela(prep.pk, self.CONTAS[1]['id'], self.user)
            self.assertEqual(baixar.call_args.args[0], self.CONTAS[1]['id'])
            self.assertEqual((doc.categoria, doc.origem, doc.nome_original), ('boleto', 'contaazul', 'boleto-20261113.pdf'))
            self.assertEqual(doc.referencia, 'Conta Azul · Parcela 2/6 · venc. 13/11/2026 · R$ 500,00')
            with patch('contaazul_boleto.baixar_pdf_parcela', side_effect=ValueError()):
                with self.assertRaisesMessage(ValidationError, 'exatamente uma cobrança registrada'):
                    p.importar_boleto_parcela(prep.pk, self.CONTAS[0]['id'], self.user)
        self.assertEqual(prep.documentos.count(), 1)

    def test_painel_lista_e_anexa_parcela(self):
        from unittest.mock import patch
        prep = self.nova()
        self.client.force_login(self.user)
        url = reverse('admin:clientes_preparacaoenvio_change', args=[prep.pk])
        self.assertContains(self.client.get(url), 'Busca no Conta Azul desabilitada')
        info = {'descricao': 'Parcela 2/6', 'data_vencimento': '2026-11-13', 'nao_pago': 500}
        with override_settings(CONTAAZUL_AMBIENTE='producao'), \
                patch('contaazul_boleto.listar_contas', return_value=self.contas()), \
                patch('contaazul_boleto.baixar_pdf_parcela', return_value=(b'%PDF-1.4\nb\n%%EOF\n', info)):
            pagina = self.client.post(url, {'acao': 'listar_boletos', 'vencimento': '2026-11-13', 'valor': ''}).content.decode()
            self.assertIn('Provável deste cliente', pagina)
            self.assertLess(pagina.index('CONDOMINIO QA'), pagina.index('Outro Prédio'))
            self.assertContains(self.client.post(url, {'acao': 'listar_boletos', 'vencimento': ''}), 'data de vencimento')
            self.client.post(url, {'acao': 'boleto_parcela', 'parcela': self.CONTAS[1]['id']})
        self.assertEqual(prep.documentos.get().origem, 'contaazul')

    def test_voltar_para_rascunho_antes_de_qualquer_envio(self):
        prep = self.confirmada()
        self.assertTrue(p.pode_reabrir(prep))
        p.reabrir(prep.pk)
        prep.refresh_from_db()
        self.assertEqual((prep.status, prep.confirmada_em, prep.destinatarios.count()), ('rascunho', None, 0))
        self.assertEqual(prep.documentos.count(), 2)
        p.anexar(prep.pk, pdf('laudo.pdf', 'l'), 'laudo', '', self.user)
        self.confirmar(prep)
        prep.refresh_from_db()
        self.assertEqual(prep.status, 'confirmada')
        with self.assertRaisesMessage(ValidationError, 'Só uma preparação confirmada'):
            p.reabrir(self.nova().pk)

    @override_settings(**dict(SMTP_TESTE, EMAIL_BACKEND='clientes.test_preparacao.FalhaParaBruno'))
    def test_cancelar_ate_o_fim_da_operacao(self):
        prep = self.confirmada()
        self.assertEqual(p.enviar(prep.pk, self.user)['falhas'], 1)
        self.assertFalse(p.pode_reabrir(prep))
        with self.assertRaisesMessage(ValidationError, 'Já houve envio'):
            p.reabrir(prep.pk)
        self.assertTrue(p.pode_cancelar(prep))
        p.cancelar(prep.pk)
        prep.refresh_from_db()
        self.assertEqual(prep.status, 'cancelada')
        with self.assertRaisesMessage(ValidationError, 'confirmadas'):
            p.enviar(prep.pk, self.user)
        with self.assertRaisesMessage(ValidationError, 'já está cancelada'):
            p.cancelar(prep.pk)
        # O que já foi aceito continua contando para o bloqueio de reenvio.
        nova = self.nova(('boleto-de-novo.pdf', 'boleto', 'b'))
        self.assertEqual(sorted(c['email'] for c in p.plano(nova)['conflitos']), ['ana@exemplo.test'])

    @override_settings(**SMTP_TESTE)
    def test_operacao_concluida_nao_cancela(self):
        prep = self.confirmada()
        p.enviar(prep.pk, self.user)
        self.assertFalse(p.pode_cancelar(prep))
        with self.assertRaisesMessage(ValidationError, 'operação terminou'):
            p.cancelar(prep.pk)

