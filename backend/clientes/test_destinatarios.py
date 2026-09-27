from datetime import date
from django.core.exceptions import ValidationError
from django.db import connection, transaction, IntegrityError
from django.contrib.auth.models import User, Permission
from django.test import TransactionTestCase
from rest_framework.test import APIClient
from .models import (Cliente, HistoricoCNPJ, Contato, Administradora, ClienteAdministradora,
                     ContatoAdministradora, Responsabilidade, ConfiguracaoDestinatarios, ItemDestinatario)
from . import destinatarios as d
from .services import alterar_administradora


class DestinatariosTests(TransactionTestCase):
    def setUp(self):
        if 'clientes' not in connection.introspection.table_names():
            with connection.schema_editor() as editor:
                for m in (Cliente, HistoricoCNPJ, Contato, Administradora, ClienteAdministradora, ContatoAdministradora, Responsabilidade):
                    editor.create_model(m)
        self.c = Cliente.objects.create(razao_social='Condomínio QA')
        self.outro = Cliente.objects.create(razao_social='Outro QA')
        self.a = Administradora.objects.create(razao_social='Empresa QA')
        self.v = ClienteAdministradora.objects.create(cliente=self.c, administradora=self.a, data_inicio=date(2020,1,1))
        ClienteAdministradora.objects.create(cliente=self.outro, administradora=self.a, data_inicio=date(2020,1,1))
        self.p = ContatoAdministradora.objects.create(administradora=self.a, nome='Contato padrão', telefone='85999999999')
        self.q = ContatoAdministradora.objects.create(administradora=self.a, nome='Contato específico')
        self.direto = Contato.objects.create(cliente=self.c, nome='Contato direto', data_inicio=date(2020,1,1))
        self.user = User.objects.create_superuser('qa', 'qa@example.invalid', 'somente-teste')
        self.api = APIClient()
        self.api.force_authenticate(self.user)

    def tearDown(self):
        with connection.cursor() as cursor:
            for table in ('clientes_itemdestinatario','clientes_revisaodestinatarios','clientes_configuracaodestinatarios','responsabilidades','contatos_administradora','cliente_administradora','administradoras','contatos','historico_cnpj','clientes'):
                cursor.execute('DELETE FROM ' + connection.ops.quote_name(table))

    def padrao(self, contato=None, numero=0, **categorias):
        return d.salvar(administradora_id=self.a.pk, numero=numero, itens=[dict(contato_administradora_id=(contato or self.p).pk, **(categorias or {'boleto': True}))])

    def local(self, itens, numero=0, modo='complementar'):
        return d.salvar(cliente_id=self.c.pk, vinculo_id=self.v.pk, numero=numero, modo=modo, itens=itens)

    def test_categorias_independentes_e_sem_email(self):
        self.padrao(laudo=True, cobranca=True)
        self.local([dict(contato_id=self.direto.pk, nota_fiscal=True)])
        r = d.efetivos(self.c.pk)
        self.assertEqual({tuple(i['categorias']) for i in r}, {('nota_fiscal',), ('laudo','cobranca')})
        self.assertEqual(len(d.efetivos(self.outro.pk)), 1)

    def test_padrao_dinamico_complementar_substituir(self):
        self.padrao()
        self.local([dict(contato_administradora_id=self.q.pk, laudo=True)])
        self.padrao(numero=1, comunicado=True)
        self.assertEqual({tuple(i['categorias']) for i in d.efetivos(self.c.pk)}, {('comunicado',), ('laudo',)})
        self.local([dict(contato_administradora_id=self.q.pk, laudo=True)], numero=1, modo='substituir')
        self.padrao(numero=2, cobranca=True)
        self.assertEqual(d.efetivos(self.c.pk)[0]['categorias'], ['laudo'])

    def test_encerramento_local_prevalece_preserva_outro(self):
        self.padrao()
        self.local([dict(contato_administradora_id=self.p.pk, encerrado_local=True)], modo='usar')
        self.assertEqual(d.efetivos(self.c.pk), [])
        self.assertEqual(len(d.efetivos(self.outro.pk)), 1)
        self.padrao(numero=1, laudo=True)
        self.local([], numero=1, modo='usar')
        self.assertEqual(d.efetivos(self.c.pk), [])
        with self.assertRaises(ValidationError):
            self.local([dict(contato_administradora_id=self.p.pk, boleto=True)], numero=1)

    def test_encerramento_global_e_edicao_antiga_nao_reativa(self):
        self.padrao()
        antigo = ContatoAdministradora.objects.get(pk=self.p.pk)
        d.encerrar_global(self.p.pk)
        antigo.nome = 'Nome corrigido'
        antigo.save()
        self.assertIsNotNone(antigo.encerrado_em)
        self.assertEqual(d.efetivos(self.c.pk), [])
        self.assertEqual(d.efetivos(self.outro.pk), [])
        self.assertEqual(d.atual(administradora_id=self.a.pk).itens.count(), 1)

    def test_encerramento_direto_registra_historico(self):
        self.local([dict(contato_id=self.direto.pk, boleto=True)])
        self.direto.data_fim = date(2021,1,1)
        self.direto.save()
        self.assertEqual(d.efetivos(self.c.pk), [])
        self.assertEqual(d.atual(cliente_id=self.c.pk).numero, 2)
        self.assertEqual(d.RevisaoDestinatarios.objects.filter(configuracao__cliente=self.c, numero=1).get().itens.count(), 1)

    def test_troca_retorno_nao_reativa_especificos(self):
        self.padrao()
        self.local([dict(contato_id=self.direto.pk, boleto=True),dict(contato_administradora_id=self.q.pk, laudo=True)], modo='substituir')
        b = Administradora.objects.create(razao_social='Nova QA')
        alterar_administradora(self.c.pk, acao='vincular', data=date(2021,1,1), administradora=b)
        self.assertEqual(len(d.efetivos(self.c.pk)), 1)
        alterar_administradora(self.c.pk, acao='vincular', data=date(2022,1,1), administradora=self.a)
        self.assertEqual({i['nome'] for i in d.efetivos(self.c.pk)}, {self.direto.nome,self.p.nome})
        self.assertEqual(d.atual(cliente_id=self.c.pk).numero, 3)

    def test_duplicidade_origem_invalida_e_atomicidade(self):
        fora = Contato.objects.create(cliente=self.outro,nome='Fora',data_inicio=date(2020,1,1))
        for itens in [[dict(contato_id=fora.pk,boleto=True)], [dict(contato_id=self.direto.pk)], [dict(contato_id=self.direto.pk,boleto=True)]*2]:
            with self.assertRaises(ValidationError): self.local(itens)
        self.assertFalse(ConfiguracaoDestinatarios.objects.filter(cliente=self.c).exists())

    def test_edicao_conflitante_e_salvar_sem_mudanca(self):
        r = self.padrao()
        self.assertEqual(self.padrao(numero=1).pk, r.pk)
        with self.assertRaises(ValidationError): self.padrao(numero=0,laudo=True)
        self.assertEqual(d.atual(administradora_id=self.a.pk).numero,1)

    def test_constraints_banco(self):
        r = self.padrao()
        with self.assertRaises(IntegrityError), transaction.atomic():
            ConfiguracaoDestinatarios.objects.create(cliente=self.c,administradora=self.a)
        with self.assertRaises(IntegrityError), transaction.atomic():
            ItemDestinatario.objects.create(revisao=r,contato=self.direto)

    def test_api_permissoes_historico_e_encerramento(self):
        url=f'/api/v1/clientes/{self.c.pk}/destinatarios/'
        self.assertEqual(self.api.put(url,dict(numero=0,vinculo_id=self.v.pk,modo='usar',itens=[dict(contato_id=self.direto.pk,boleto=True)]),format='json').status_code,200)
        self.assertEqual(self.api.get(url+'historico/').data['count'],1)
        operador=User.objects.create_user('sem-permissao')
        self.api.force_authenticate(operador)
        self.assertEqual(self.api.get(url).status_code,403)
        operador.user_permissions.set(Permission.objects.filter(codename__in=['view_configuracaodestinatarios','view_cliente','view_contato','view_administradora','view_contatoadministradora']))
        self.api.force_authenticate(User.objects.get(pk=operador.pk))
        self.assertEqual(self.api.get(url).status_code,200)
        self.assertEqual(self.api.put(url,{},format='json').status_code,403)
        self.assertEqual(self.api.post(f'/api/v1/contatos-administradora/{self.p.pk}/encerrar/').status_code,403)
        self.api.force_authenticate(self.user)
        self.assertEqual(self.api.post(f'/api/v1/contatos-administradora/{self.p.pk}/encerrar/').status_code,200)

    def test_painel_formulario_salvar_e_consultar(self):
        self.client.force_login(self.user)
        url=f'/admin/clientes/cliente/{self.c.pk}/destinatarios/'
        r=self.client.get(url)
        self.assertContains(r,'Destinatários')
        self.assertContains(r,'Sem e-mail')
        self.assertContains(self.client.get(f'/admin/clientes/administradora/{self.a.pk}/destinatarios/'), 'Este padrão é usado por 2 condomínio(s).')
        payload={'numero':0,'vinculo_id':self.v.pk,'modo':'usar','form-TOTAL_FORMS':1,'form-INITIAL_FORMS':0,'form-0-contato_id':self.direto.pk,'form-0-boleto':'on'}
        self.assertEqual(self.client.post(url,payload).status_code,302)
        self.assertContains(self.client.get(url),'Revisão 1')
        self.assertEqual(d.efetivos(self.c.pk)[0]['categorias'],['boleto'])