from datetime import date

from django.contrib.auth.models import Permission, User
from django.urls import reverse

from clientes.contratos_models import Contrato, TipoContrato
from clientes.models import Cliente, HistoricoCNPJ
from clientes.test_preparacao import BasePreparacao
from painel import importacao
from painel.test_importacao import csv_arquivo


class ContratosTests(BasePreparacao):
    def setUp(self):
        super().setUp()
        HistoricoCNPJ.objects.create(cliente=self.c, cnpj='11222333000181', data_inicio=date(2020, 1, 1))
        self.manut = TipoContrato.objects.create(nome='Manutenção preventiva')
        self.locacao = TipoContrato.objects.create(nome='Locação de bombas')
        self.client.force_login(self.user)

    def test_cliente_pode_ter_varios_contratos_de_tipos_diferentes(self):
        url = reverse('painel:contrato_novo', args=[self.c.pk])
        for tipo, situacao in ((self.manut, 'ativo'), (self.locacao, 'suspenso')):
            r = self.client.post(url, dict(tipo=tipo.pk, situacao=situacao, data_inicio='2024-01-01'))
            self.assertRedirects(r, reverse('painel:cliente', args=[self.c.pk]))
        self.assertEqual(self.c.contratos.count(), 2)
        ficha = self.client.get(reverse('painel:cliente', args=[self.c.pk])).content.decode()
        for trecho in ('Manutenção preventiva', 'Locação de bombas', 'Suspenso'):
            self.assertIn(trecho, ficha)
        inicio = self.client.get(reverse('painel:inicio')).content.decode()
        self.assertIn('1 cliente(s) com contrato ativo', inicio)
        self.assertIn('1 suspenso(s)', inicio)

    def test_datas_invalidas_e_tipo_indisponivel_sao_recusados(self):
        url = reverse('painel:contrato_novo', args=[self.c.pk])
        r = self.client.post(url, dict(tipo=self.manut.pk, situacao='ativo', data_inicio='2024-05-01', data_fim='2024-01-01'))
        self.assertContains(r, 'O fim não pode ser anterior ao início.')
        self.locacao.ativo = False
        self.locacao.save()
        r = self.client.post(url, dict(tipo=self.locacao.pk, situacao='ativo', data_inicio='2024-01-01'))
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Contrato.objects.exists())

    def test_edicao_mantem_tipo_desativado_do_proprio_contrato(self):
        c = Contrato.objects.create(cliente=self.c, tipo=self.locacao, data_inicio=date(2024, 1, 1))
        self.locacao.ativo = False
        self.locacao.save()
        r = self.client.post(reverse('painel:contrato_editar', args=[c.pk]),
                             dict(tipo=self.locacao.pk, situacao='inativo', data_inicio='2024-01-01', data_fim='2024-12-31'))
        self.assertRedirects(r, reverse('painel:cliente', args=[self.c.pk]))
        c.refresh_from_db()
        self.assertEqual((c.situacao, c.data_fim), ('inativo', date(2024, 12, 31)))

    def test_lista_filtra_por_situacao_e_tipo(self):
        outro = Cliente.objects.create(razao_social='Edifício Sol')
        Contrato.objects.create(cliente=self.c, tipo=self.manut, data_inicio=date(2024, 1, 1))
        Contrato.objects.create(cliente=outro, tipo=self.locacao, situacao='inativo', data_inicio=date(2023, 1, 1))
        url = reverse('painel:contratos')
        self.assertEqual(self.client.get(url).content.decode().count('data-contrato'), 2)
        ativos = self.client.get(url, {'situacao': 'ativo'}).content.decode()
        self.assertIn('Condomínio QA', ativos)
        self.assertNotIn('Edifício Sol', ativos)
        por_tipo = self.client.get(url, {'tipo': self.locacao.pk}).content.decode()
        self.assertEqual(por_tipo.count('data-contrato'), 1)
        self.assertIn('Edifício Sol', por_tipo)

    def test_tipos_cadastrados_na_tela_sem_duplicar_nome(self):
        url = reverse('painel:tipos_contrato')
        self.assertRedirects(self.client.post(url, dict(nome='  Retrofit   de válvulas ')), url)
        self.assertTrue(TipoContrato.objects.get(nome='Retrofit de válvulas').ativo)
        self.assertContains(self.client.post(url, dict(nome='manutenção PREVENTIVA')), 'Já existe um tipo com este nome.')
        self.assertEqual(TipoContrato.objects.count(), 3)

    def test_permissoes(self):
        u = User.objects.create_user('leitor', password='somente-teste')
        u.user_permissions.add(Permission.objects.get(codename='view_contrato'))
        self.client.force_login(u)
        self.assertEqual(self.client.get(reverse('painel:contratos')).status_code, 200)
        self.assertEqual(self.client.get(reverse('painel:contrato_novo', args=[self.c.pk])).status_code, 403)
        self.assertEqual(self.client.get(reverse('painel:tipos_contrato')).status_code, 403)

    def test_importacao_csv_de_contratos(self):
        Contrato.objects.create(cliente=self.c, tipo=self.manut, data_inicio=date(2024, 1, 1))
        texto = ('Condomínio;Tipo de contrato;Situação;Início;Fim;Número\n'
                 '11.222.333/0001-81;Manutenção preventiva;Ativo;01/01/2024;;10\n'      # já existe
                 '11.222.333/0001-81;locação de bombas;Suspenso;2024-03-01;;11\n'       # novo (tipo sem diferenciar caixa)
                 'Condomínio QA;Locação de bombas;;;;12\n'                              # novo: ativo, hoje
                 '11.222.333/0001-81;Tipo Inexistente;Ativo;2024-01-01;;13\n'
                 '99.999.999/0001-99;Manutenção preventiva;Ativo;2024-01-01;;14\n'
                 '11.222.333/0001-81;Manutenção preventiva;Cancelado;2024-01-01;;15\n')
        r = self.client.post(reverse('painel:importar'), {'tipo': 'contratos', 'arquivo': csv_arquivo(texto)})
        self.assertRedirects(r, reverse('painel:importar_previa'))
        previa = self.client.get(reverse('painel:importar_previa')).content.decode()
        for trecho in ('Tipo de contrato não cadastrado', 'Condomínio não encontrado', 'Situação inválida', 'situação não informada'):
            self.assertIn(trecho, previa)
        self.assertEqual(Contrato.objects.count(), 1)
        cab, linhas, _ = importacao.ler(texto.encode())
        mapa = importacao.mapear('contratos', cab)
        resultado = importacao.importar('contratos', importacao.analisar('contratos', linhas, mapa))
        self.assertEqual(resultado['criados'], 2)
        self.assertEqual(Contrato.objects.filter(cliente=self.c).count(), 3)
        novo = Contrato.objects.get(identificador='11')
        self.assertEqual((novo.tipo, novo.situacao, novo.data_inicio), (self.locacao, 'suspenso', date(2024, 3, 1)))
        self.assertEqual(Contrato.objects.get(identificador='12').situacao, 'ativo')
