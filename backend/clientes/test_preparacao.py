import shutil
import tempfile
from datetime import date

from django.contrib.auth.models import Permission, User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, connection, transaction
from django.test import TransactionTestCase, override_settings
from django.urls import reverse

from . import destinatarios as d
from . import preparacao as p
from .models import (Administradora, Cliente, ClienteAdministradora, Contato, ContatoAdministradora,
                     HistoricoCNPJ, Responsabilidade, DocumentoPreparacao, PreparacaoEnvio, ItemPreparacao)


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
