from datetime import date
from unittest.mock import patch

from django.contrib.auth.models import Permission, User
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse

from clientes.models import (Administradora, Cliente, ClienteAdministradora, Contato, ContatoAdministradora,
                             HistoricoCNPJ)
from clientes.test_preparacao import BasePreparacao
from painel import completude, importacao


def csv_arquivo(texto, nome='lista.csv', codificacao='utf-8-sig'):
    return SimpleUploadedFile(nome, texto.encode(codificacao), content_type='text/csv')


class ImportacaoTests(BasePreparacao):
    def setUp(self):
        super().setUp()
        HistoricoCNPJ.objects.create(cliente=self.c, cnpj='11222333000181', data_inicio=date(2020, 1, 1))
        self.client.force_login(self.user)

    def enviar(self, tipo, texto, **kw):
        return self.client.post(reverse('painel:importar'), {'tipo': tipo, 'arquivo': csv_arquivo(texto, **kw)})

    def test_le_cp1252_virgula_e_reconhece_colunas_com_nomes_variados(self):
        cab, linhas, _ = importacao.ler('Condomínio,CNPJ,Município,UF\nEd. Sol,1234567000190,Fortaleza,CE\n'.encode('cp1252'))
        mapa = importacao.mapear('clientes', cab)
        self.assertEqual((mapa['razao_social'], mapa['cnpj'], mapa['cidade'], mapa['estado']), (0, 1, 2, 3))
        analise = importacao.analisar('clientes', linhas, mapa)
        self.assertEqual(analise[0]['dados']['cnpj'], '01234567000190')
        self.assertIn('CNPJ completado com zeros à esquerda', analise[0]['notas'])

    def test_fluxo_clientes_previa_confirmar_com_pendencias_e_administradora(self):
        texto = ('Razão social;CNPJ;CEP;Endereço;Número;Bairro;Cidade;UF;Administradora\n'
                 'Condomínio Novo;22.333.444/0001-55;60000-000;Rua A;10;Centro;Fortaleza;CE;Empresa QA\n'
                 'Edifício Incompleto;33.444.555/0001-66;;;;;;;Adm Nova\n'
                 'Condomínio QA;11.222.333/0001-81;;;;;;;\n'
                 ';44.555.666/0001-77;;;;;;;\n'
                 'Sem CNPJ;;;;;;;;\n')
        self.assertRedirects(self.enviar('clientes', texto), reverse('painel:importar_previa'))
        previa = self.client.get(reverse('painel:importar_previa')).content.decode()
        for trecho in ('Condomínio Novo', 'endereço pendente', 'será cadastrada', 'Já existe', 'Razão social vazia', 'CNPJ vazio'):
            self.assertIn(trecho, previa)
        self.assertEqual(Cliente.objects.count(), 1)  # nada gravado na prévia
        resposta = self.client.post(reverse('painel:importar_previa'), {'acao': 'confirmar', **self._mapa_atual()})
        self.assertRedirects(resposta, reverse('painel:importar_resultado'))
        self.assertContains(self.client.get(reverse('painel:importar_resultado')), 'cadastrado(s)')
        novo = Cliente.objects.get(razao_social='Condomínio Novo')
        self.assertEqual(novo.historico_cnpj.get().cnpj, '22333444000155')
        self.assertEqual(novo.historico_administradoras.get().administradora, self.a)
        incompleto = Cliente.objects.get(razao_social='Edifício Incompleto')
        self.assertIsNone(incompleto.logradouro)
        self.assertEqual(incompleto.historico_administradoras.get().administradora.razao_social, 'Adm Nova')
        anotado = completude.anotar(Cliente.objects.filter(pk=incompleto.pk)).get()
        self.assertEqual((anotado.ok_cnpj, anotado.ok_endereco, anotado.ok_administradora), (True, False, True))
        self.assertEqual(Cliente.objects.count(), 3)

    def _mapa_atual(self):
        estado = self.client.session['importacao']
        return {'col_' + k: str(v) for k, v in estado['mapa'].items()}

    def test_remapear_coluna_nao_reconhecida(self):
        self.enviar('administradoras', 'Empresa Gestora;Doc\nGestora X;55.666.777/0001-88\n')
        estado = self.client.session['importacao']
        self.assertEqual(estado['mapa'], {'razao_social': 0})  # "Doc" não reconhecido
        self.client.post(reverse('painel:importar_previa'), {'acao': 'remapear', 'col_razao_social': '0', 'col_cnpj': '1'})
        self.client.post(reverse('painel:importar_previa'), {'acao': 'confirmar', 'col_razao_social': '0', 'col_cnpj': '1'})
        self.assertEqual(Administradora.objects.get(razao_social='Gestora X').cnpj, '55666777000188')

    def test_contatos_e_contatos_da_administradora(self):
        self.enviar('contatos', 'CNPJ do condomínio;Nome;Função;E-mail;Telefone\n'
                                '11.222.333/0001-81;Fábio Zelador;Zelador;fabio@exemplo.test;85999990000\n'
                                '11222333000181;Ana;Síndica;ana@exemplo.test;\n'
                                '99.999.999/0001-99;Fantasma;;;\n'
                                'Condomínio QA;Gil;;email-invalido;\n')
        previa = self.client.get(reverse('painel:importar_previa')).content.decode()
        self.assertIn('Condomínio não encontrado', previa)
        self.assertIn('e-mail inválido ignorado', previa)
        self.client.post(reverse('painel:importar_previa'), {'acao': 'confirmar', **self._mapa_atual()})
        self.assertTrue(Contato.objects.filter(cliente=self.c, nome='Fábio Zelador', email='fabio@exemplo.test').exists())
        self.assertTrue(Contato.objects.filter(cliente=self.c, nome='Gil', email__isnull=True).exists())
        self.assertEqual(Contato.objects.filter(cliente=self.c, nome='Ana').count(), 1)  # já existia
        self.enviar('contatos_administradora', 'Administradora;Nome;E-mail\nEmpresa QA;Helena;helena@exemplo.test\nEmpresa QA;Bruno;\n')
        self.client.post(reverse('painel:importar_previa'), {'acao': 'confirmar', **self._mapa_atual()})
        self.assertTrue(ContatoAdministradora.objects.filter(administradora=self.a, nome='Helena').exists())
        self.assertEqual(ContatoAdministradora.objects.filter(administradora=self.a, nome='Bruno').count(), 1)

    def test_permissoes_modelo_e_descartar(self):
        resposta = self.client.get(reverse('painel:importar_modelo', args=['clientes']))
        self.assertIn('Razão social;CNPJ', resposta.content.decode('utf-8-sig'))
        self.enviar('clientes', 'Razão social;CNPJ\nX;22.333.444/0001-55\n')
        self.client.post(reverse('painel:importar_previa'), {'acao': 'descartar'})
        self.assertNotIn('importacao', self.client.session)
        self.assertFalse(Cliente.objects.filter(razao_social='X').exists())
        so_contatos = User.objects.create_user('so_contatos', password='somente-teste')
        so_contatos.user_permissions.add(Permission.objects.get(codename='add_contato'))
        self.client.force_login(so_contatos)
        self.assertEqual(self.enviar('clientes', 'Razão social;CNPJ\nY;22.333.444/0001-55\n').status_code, 403)
        self.assertEqual(self.client.get(reverse('painel:importar')).status_code, 200)
        self.assertContains(self.enviar('contatos', 'so cabecalho\n'), 'pelo menos uma linha')


class InicioPainelTests(BasePreparacao):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.client.force_login(self.user)

    def test_painel_foca_em_clientes_administradoras_e_contratos(self):
        pagina = self.client.get(reverse('painel:inicio')).content.decode()
        for trecho in ('Clientes cadastrados', 'Sem CNPJ atual', 'Administradoras', 'Envio de documentos'):
            self.assertIn(trecho, pagina)
        self.assertNotIn('Contratos ativos', pagina)  # Conta Azul não configurado nos testes
        self.assertLess(pagina.index('Clientes cadastrados'), pagina.index('secao-titulo'))
        lista = self.client.get(reverse('painel:clientes'), {'pendencia': 'cnpj'}).content.decode()
        self.assertIn('Condomínio QA', lista)

    @override_settings(CONTAAZUL_AMBIENTE='producao')
    def test_contratos_ativos_cruzados_com_a_base(self):
        HistoricoCNPJ.objects.create(cliente=self.c, cnpj='11222333000181', data_inicio=date(2020, 1, 1))
        itens = {'itens': [
            {'status': 'ATIVO', 'numero': 1, 'cliente': {'nome': 'Condominio QA', 'documento': '11.222.333/0001-81'}},
            {'status': 'ATIVO', 'numero': 2, 'cliente': {'nome': 'Edifício Sem Cadastro'}},
            {'status': 'INATIVO', 'numero': 3, 'cliente': {'nome': 'Antigo'}},
        ]}
        with patch('contaazul_boleto._cliente_http', return_value=lambda *a, **k: itens):
            pagina = self.client.get(reverse('painel:inicio')).content.decode()
        self.assertIn('Contratos ativos', pagina)
        self.assertIn('Edifício Sem Cadastro', pagina)
        self.assertNotIn('Antigo', pagina)
        self.assertIn('1 com cadastro aqui', pagina)
        cache.clear()
        from urllib.error import HTTPError
        with patch('contaazul_boleto._cliente_http', side_effect=HTTPError('https://x', 401, 'n', None, None)):
            self.assertContains(self.client.get(reverse('painel:inicio')), 'Autorização do Conta Azul expirada')
