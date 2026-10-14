from datetime import date

from django.contrib.auth.models import Permission, User
from django.urls import reverse

from clientes.models import HistoricoCNPJ, PreparacaoEnvio
from clientes.test_preparacao import BasePreparacao, pdf


class InterfaceTests(BasePreparacao):
    def setUp(self):
        super().setUp()
        HistoricoCNPJ.objects.create(cliente=self.c, cnpj='11222333000181', data_inicio=date(2020, 1, 1))

    def operador(self, *codigos):
        u = User.objects.create_user('op', password='somente-teste')
        u.user_permissions.add(*Permission.objects.filter(content_type__app_label='clientes', codename__in=codigos))
        self.client.force_login(u)
        return u

    def test_login_e_acesso_anonimo(self):
        self.assertRedirects(self.client.get(reverse('painel:clientes')), reverse('painel:entrar') + '?next=' + reverse('painel:clientes'))
        self.assertContains(self.client.get(reverse('painel:entrar')), 'Entrar')
        resposta = self.client.post(reverse('painel:entrar'), {'username': 'qa', 'password': 'errada'})
        self.assertContains(resposta, 'Usuário ou senha incorretos')
        resposta = self.client.post(reverse('painel:entrar'), {'username': 'qa', 'password': 'somente-teste'})
        self.assertRedirects(resposta, reverse('painel:inicio'))
        self.assertContains(self.client.get(reverse('painel:inicio')), 'Preparações recentes')

    def test_permissoes_sem_acesso(self):
        self.operador()
        for nome in ('clientes', 'preparacoes'):
            self.assertEqual(self.client.get(reverse('painel:' + nome)).status_code, 403)
        self.assertEqual(self.client.post(reverse('painel:nova_preparacao'), {'cliente': self.c.pk}).status_code, 403)
        pagina = self.client.get(reverse('painel:inicio')).content.decode()
        self.assertNotIn('Envio de documentos', pagina)

    def test_lista_busca_e_detalhe_do_cliente(self):
        self.operador('view_cliente')
        pagina = self.client.get(reverse('painel:clientes')).content.decode()
        self.assertIn('Condomínio QA', pagina)
        self.assertIn('11.222.333/0001-81', pagina)
        self.assertIn('Empresa QA', pagina)
        self.assertNotIn('Preparar envio para', pagina)
        self.assertContains(self.client.get(reverse('painel:clientes'), {'q': '11222333'}), 'Condomínio QA')
        self.assertContains(self.client.get(reverse('painel:clientes'), {'q': 'inexistente'}), 'Nenhum cliente encontrado')
        detalhe = self.client.get(reverse('painel:cliente', args=[self.c.pk])).content.decode()
        for trecho in ('Quem recebe documentos', 'ana@exemplo.test', 'Bruno', 'Sem e-mail', 'Padrão da administradora'):
            self.assertIn(trecho, detalhe)

    def test_fluxo_completo_pela_interface(self):
        self.operador('view_cliente', 'view_preparacaoenvio', 'add_preparacaoenvio', 'confirmar_preparacaoenvio')
        resposta = self.client.post(reverse('painel:nova_preparacao'), {'cliente': self.c.pk})
        prep = PreparacaoEnvio.objects.get()
        url = reverse('painel:preparacao', args=[prep.pk])
        self.assertRedirects(resposta, url)
        self.client.post(url, {'acao': 'anexar', 'categoria': 'boleto', 'arquivos': [pdf('b.pdf', 'b')]})
        pagina = self.client.get(url).content.decode()
        self.assertIn('b.pdf', pagina)
        self.assertIn('Revisão e confirmação', pagina)
        doc = prep.documentos.get()
        arquivo = self.client.get(reverse('painel:documento', args=[prep.pk, doc.pk]))
        self.assertTrue(arquivo['Content-Disposition'].startswith('inline'))
        from clientes import preparacao as p
        impressao = p.plano(prep)['impressao']
        self.client.post(url, {'acao': 'confirmar', 'conferido': 'sim', 'impressao': impressao, 'assunto': 'A', 'mensagem': 'M'})
        prep.refresh_from_db()
        self.assertEqual(prep.status, 'confirmada')
        pagina = self.client.get(url).content.decode()
        self.assertIn('Envio por e-mail', pagina)
        self.assertNotIn('Enviar e-mails (', pagina)  # sem permissão de envio
        self.assertEqual(self.client.post(url, {'acao': 'enviar'}).status_code, 403)
        lista = self.client.get(reverse('painel:preparacoes'), {'status': 'confirmada'}).content.decode()
        self.assertIn('Condomínio QA', lista)
        self.assertNotIn('Condomínio QA', self.client.get(reverse('painel:preparacoes'), {'status': 'cancelada'}).content.decode())
