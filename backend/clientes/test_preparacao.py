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


class PreparacaoTests(TransactionTestCase):
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
        for acao in (lambda: p.anexar(prep.pk, pdf('n.pdf', 'n'), 'nota_fiscal', '', self.user), lambda: p.cancelar(prep.pk),
                     lambda: self.confirmar(prep)):
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
