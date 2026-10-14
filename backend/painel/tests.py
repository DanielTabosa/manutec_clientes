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
        self.assertContains(self.client.get(reverse('painel:inicio')), 'Clientes cadastrados')

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


class CadastrosTests(BasePreparacao):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)

    def dados_cliente(self, **extra):
        dados = dict(cnpj='22.333.444/0001-55', razao_social='Condomínio Novo', nome_fantasia='', cep='60000-000',
                     logradouro='Rua A', numero='10', complemento='', bairro='Centro', cidade='Fortaleza', estado='CE',
                     data_inicio='2024-01-01', observacoes='')
        dados.update(extra)
        return dados

    def test_cadastro_edicao_cnpj_e_administradora(self):
        from clientes.models import Cliente, Administradora
        url = reverse('painel:cliente_novo')
        self.assertContains(self.client.get(url), 'Consultar CNPJ')
        resposta = self.client.post(url, self.dados_cliente())
        novo = Cliente.objects.get(razao_social='Condomínio Novo')
        self.assertRedirects(resposta, reverse('painel:cliente', args=[novo.pk]))
        self.assertEqual(novo.historico_cnpj.get().cnpj, '22333444000155')
        self.assertContains(self.client.post(url, self.dados_cliente(razao_social='Outro')), 'já está cadastrado')
        self.assertContains(self.client.post(url, self.dados_cliente(cnpj='33444555000166', logradouro='')), 'Confira os campos')
        self.client.post(reverse('painel:cliente_editar', args=[novo.pk]), self.dados_cliente(razao_social='Condomínio Renomeado'))
        novo.refresh_from_db()
        self.assertEqual(novo.razao_social, 'Condomínio Renomeado')
        self.client.post(reverse('painel:cliente_cnpj', args=[novo.pk]), {'cnpj': '44555666000177', 'data_inicio': '2025-01-01'})
        self.assertEqual(novo.historico_cnpj.filter(data_fim__isnull=True).get().cnpj, '44555666000177')
        self.assertEqual(novo.historico_cnpj.count(), 2)
        outra = Administradora.objects.create(razao_social='Outra Empresa')
        self.client.post(reverse('painel:cliente_administradora', args=[novo.pk]), {'acao': 'vincular', 'administradora': outra.pk, 'data': '2025-02-01'})
        self.assertEqual(novo.historico_administradoras.get(data_fim__isnull=True).administradora, outra)
        ficha = self.client.get(reverse('painel:cliente', args=[novo.pk])).content.decode()
        self.assertIn('Outra Empresa', ficha)
        self.assertIn('44.555.666/0001-77', ficha)

    def test_contatos_do_condominio_e_encerramento(self):
        from clientes.models import Contato
        from clientes import destinatarios as d
        self.client.post(reverse('painel:contato_novo', args=[self.c.pk]),
                         {'nome': 'Fábio', 'funcao': 'Zelador', 'email': 'fabio@exemplo.test', 'data_inicio': '2024-01-01'})
        self.assertTrue(Contato.objects.filter(nome='Fábio', cliente=self.c).exists())
        ana = Contato.objects.get(nome='Ana')
        self.client.post(reverse('painel:contato_editar', args=[ana.pk]),
                         {'nome': 'Ana', 'email': 'ana@exemplo.test', 'data_inicio': '2020-01-01', 'data_fim': '2026-10-01'})
        self.assertNotIn('Ana', [e['nome'] for e in d.efetivos(self.c.pk)])
        self.assertContains(self.client.post(reverse('painel:contato_editar', args=[ana.pk]),
                            {'nome': 'Ana', 'data_inicio': '2020-01-01', 'data_fim': '2019-01-01'}), 'anterior ao início')

    def test_destinatarios_pela_interface(self):
        from clientes.models import Contato
        from clientes import destinatarios as d
        url = reverse('painel:cliente_destinatarios', args=[self.c.pk])
        pagina = self.client.get(url).content.decode()
        for trecho in ('Quem recebe documentos', 'Resultado: quem recebe hoje', 'Histórico de alterações', 'Sem e-mail'):
            self.assertIn(trecho, pagina)
        ana = Contato.objects.get(nome='Ana')
        atual = d.atual(cliente_id=self.c.pk)
        resposta = self.client.post(url, {'numero': atual.numero, 'vinculo_id': self.v.pk, 'modo': 'usar',
                                          'form-TOTAL_FORMS': 1, 'form-INITIAL_FORMS': 1, 'form-MIN_NUM_FORMS': 0, 'form-MAX_NUM_FORMS': 1000,
                                          'form-0-contato_id': ana.pk, 'form-0-boleto': 'on'})
        self.assertRedirects(resposta, url)
        ana_ef = [e for e in d.efetivos(self.c.pk) if e['nome'] == 'Ana'][0]
        self.assertEqual(ana_ef['categorias'], ['boleto'])
        conflito = self.client.post(url, {'numero': atual.numero, 'vinculo_id': self.v.pk, 'modo': 'usar',
                                          'form-TOTAL_FORMS': 0, 'form-INITIAL_FORMS': 0, 'form-MIN_NUM_FORMS': 0, 'form-MAX_NUM_FORMS': 1000})
        self.assertContains(conflito, 'outro operador')
        self.assertContains(self.client.get(reverse('painel:administradora_destinatarios', args=[self.a.pk])), 'Padrão da Empresa QA')

    def test_administradoras_contatos_e_encerramento_global(self):
        from clientes.models import Administradora, ContatoAdministradora
        from clientes import destinatarios as d
        lista = self.client.get(reverse('painel:administradoras')).content.decode()
        self.assertIn('Empresa QA', lista)
        ficha = self.client.get(reverse('painel:administradora', args=[self.a.pk])).content.decode()
        for trecho in ('Bruno', 'Carla', 'Condomínio QA', 'nota fiscal'):
            self.assertIn(trecho, ficha)
        self.client.post(reverse('painel:administradora_nova'), {'cnpj': '', 'razao_social': 'Nova Adm', 'nome_fantasia': '', 'telefone': '', 'email': ''})
        nova = Administradora.objects.get(razao_social='Nova Adm')
        self.client.post(reverse('painel:contato_adm_novo', args=[nova.pk]), {'nome': 'Gil', 'email': 'gil@exemplo.test', 'telefone': ''})
        self.assertTrue(nova.contatos.filter(nome='Gil').exists())
        bruno = ContatoAdministradora.objects.get(nome='Bruno')
        self.assertEqual(self.client.get(reverse('painel:contato_adm_encerrar', args=[bruno.pk])).status_code, 405)
        self.client.post(reverse('painel:contato_adm_encerrar', args=[bruno.pk]))
        bruno.refresh_from_db()
        self.assertIsNotNone(bruno.encerrado_em)
        self.assertNotIn('Bruno', [e['nome'] for e in d.efetivos(self.c.pk)])

    def test_consultas_e_permissoes(self):
        from unittest.mock import patch
        operador = User.objects.create_user('sem', password='somente-teste')
        operador.user_permissions.add(Permission.objects.get(codename='view_cliente'))
        self.client.force_login(operador)
        bloqueadas = [('cliente_novo', []), ('cliente_editar', [self.c.pk]), ('cliente_destinatarios', [self.c.pk]),
                      ('administradoras', []), ('consulta_cnpj', [])]
        for nome, args in bloqueadas:
            self.assertEqual(self.client.get(reverse('painel:' + nome, args=args)).status_code, 403, nome)
        self.client.force_login(self.user)
        with patch('painel.cadastros.consultar_cnpj', return_value={'razao_social': 'X'}):
            self.assertEqual(self.client.get(reverse('painel:consulta_cnpj'), {'cnpj': '22333444000155'}).json(), {'razao_social': 'X'})
        self.assertEqual(self.client.get(reverse('painel:consulta_cep'), {'cep': '123'}).status_code, 400)


class BuscaTests(BasePreparacao):
    def test_busca_global_respeita_permissoes(self):
        self.client.force_login(self.user)
        url = reverse('painel:busca')
        self.assertContains(self.client.get(url, {'q': 'a'}), 'ao menos 2 letras')
        pagina = self.client.get(url, {'q': 'QA'}).content.decode()
        self.assertIn('Condomínio QA', pagina)
        self.assertIn('Empresa QA', pagina)
        prep = self.nova()
        self.assertContains(self.client.get(url, {'q': f'#{prep.pk}'}), f'Preparação {prep.pk}')
        self.assertContains(self.client.get(url, {'q': 'zzzz'}), 'Nada encontrado')
        restrito = User.objects.create_user('restrito', password='somente-teste')
        restrito.user_permissions.add(Permission.objects.get(codename='view_cliente'))
        self.client.force_login(restrito)
        pagina = self.client.get(url, {'q': 'QA'}).content.decode()
        self.assertIn('Condomínio QA', pagina)
        self.assertNotIn('Empresa QA', pagina)


class VoltarAtrasTests(BasePreparacao):
    def test_botoes_de_voltar_e_cancelar_pela_interface(self):
        self.client.force_login(self.user)
        prep = self.confirmada()
        url = reverse('painel:preparacao', args=[prep.pk])
        pagina = self.client.get(url).content.decode()
        self.assertIn('Voltar para rascunho', pagina)
        self.assertIn('Cancelar preparação', pagina)
        self.client.post(url, {'acao': 'reabrir'})
        prep.refresh_from_db()
        self.assertEqual(prep.status, 'rascunho')
        self.confirmar(prep)
        self.client.post(url, {'acao': 'cancelar'})
        prep.refresh_from_db()
        self.assertEqual(prep.status, 'cancelada')
        pagina = self.client.get(url).content.decode()
        self.assertNotIn('Voltar para rascunho', pagina)
        operador = User.objects.create_user('so_edita', password='somente-teste')
        operador.user_permissions.add(*Permission.objects.filter(codename__in=['view_preparacaoenvio', 'add_preparacaoenvio']))
        self.client.force_login(operador)
        outra = self.confirmada()
        self.assertEqual(self.client.post(reverse('painel:preparacao', args=[outra.pk]), {'acao': 'reabrir'}).status_code, 403)
