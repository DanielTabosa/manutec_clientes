from datetime import timedelta
from unittest.mock import patch, MagicMock
from urllib.error import URLError

from django.contrib.auth.models import Permission, User
from django.db import connection
from django.test import TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIClient

from .models import Cliente, HistoricoCNPJ, Contato, Administradora, ClienteAdministradora


class ClienteAPITests(TransactionTestCase):
    """Cria a tabela nao gerenciada somente no banco descartavel de testes."""

    def setUp(self):
        with connection.schema_editor() as editor:
            editor.create_model(Cliente)
            editor.create_model(HistoricoCNPJ)
            editor.create_model(Contato)
            editor.create_model(Administradora)
            editor.create_model(ClienteAdministradora)
        self.api = APIClient()
        self.user = User.objects.create_user(username="operador", password="teste-local")

    def tearDown(self):
        with connection.schema_editor() as editor:
            editor.delete_model(ClienteAdministradora)
            editor.delete_model(Administradora)
            editor.delete_model(Contato)
            editor.delete_model(HistoricoCNPJ)
            editor.delete_model(Cliente)

    def autorizar(self, *codigos):
        self.user.user_permissions.set(Permission.objects.filter(
            content_type__app_label="clientes", codename__in=codigos
        ))
        self.api.force_authenticate(User.objects.get(pk=self.user.pk))

    def test_administradora_cadastro_cnpj_opcional_normalizado_e_duplicado(self):
        self.autorizar("add_administradora", "view_administradora", "change_administradora")
        for nome in ["Admin A", "Admin B"]:
            r = self.api.post("/api/v1/administradoras/", {"razao_social": nome, "cnpj": ""})
            self.assertEqual(r.status_code, 201, r.data)
            self.assertIsNone(r.data["cnpj"])
        payload = {"razao_social": "Admin C", "cnpj": "AB.123.456/0001-00"}
        r = self.api.post("/api/v1/administradoras/", payload)
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["cnpj"], "AB123456000100")
        self.assertEqual(self.api.post("/api/v1/administradoras/", payload).status_code, 400)
        self.assertEqual(self.api.post("/api/v1/administradoras/", {"razao_social": "X", "email": "invalido"}).status_code, 400)

    def test_administradora_troca_encerramento_retorno_e_multiplos_clientes(self):
        self.autorizar("change_cliente", "view_cliente", "view_administradora")
        a = Administradora.objects.create(razao_social="A")
        b = Administradora.objects.create(razao_social="B")
        c = Cliente.objects.create(razao_social="Cliente")
        outro = Cliente.objects.create(razao_social="Outro")
        url = f"/api/v1/clientes/{c.pk}/administradora/"
        self.assertIsNone(self.api.get(url).data["atual"])
        for cliente in [c, outro]:
            r = self.api.post(f"/api/v1/clientes/{cliente.pk}/administradora/", {"acao": "vincular", "administradora": a.pk, "data": "2020-01-01"})
            self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(self.api.post(url, {"acao": "vincular", "administradora": b.pk, "data": "2021-01-01"}).status_code, 201)
        historico = self.api.get(url).data
        self.assertEqual(historico["atual"]["administradora"], b.pk)
        self.assertEqual(historico["historico"][1]["data_fim"], "2020-12-31")
        r = self.api.post(url, {"acao": "encerrar", "data": "2022-01-01"})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertIsNone(self.api.get(url).data["atual"])
        self.assertEqual(self.api.post(url, {"acao": "vincular", "administradora": a.pk, "data": "2023-01-01"}).status_code, 201)
        self.assertEqual(c.historico_administradoras.count(), 3)
        self.assertEqual(outro.historico_administradoras.get().administradora_id, a.pk)

    def test_administradora_erros_preservam_vinculo(self):
        self.autorizar("change_cliente", "view_administradora")
        c = Cliente.objects.create(razao_social="Cliente")
        a = Administradora.objects.create(razao_social="A")
        b = Administradora.objects.create(razao_social="B")
        vinculo = ClienteAdministradora.objects.create(cliente=c, administradora=a, data_inicio="2020-01-01")
        url = f"/api/v1/clientes/{c.pk}/administradora/"
        for payload in [
            {"acao": "encerrar", "data": "2019-01-01"},
            {"acao": "vincular", "administradora": b.pk, "data": "2020-01-01"},
            {"acao": "vincular", "administradora": b.pk, "data": "2999-01-01"},
            {"acao": "vincular", "administradora": a.pk, "data": "2021-01-01"},
            {"acao": "vincular", "administradora": 999999, "data": "2021-01-01"},
            {"acao": "vincular", "data": "2021-01-01"},
            {"acao": "encerrar", "administradora": b.pk, "data": "2021-01-01"},
        ]:
            self.assertEqual(self.api.post(url, payload).status_code, 400, payload)
            vinculo.refresh_from_db()
            self.assertIsNone(vinculo.data_fim)
            self.assertEqual(c.historico_administradoras.count(), 1)

    def test_administradora_permissoes_e_sem_exclusao(self):
        c = Cliente.objects.create(razao_social="Cliente")
        a = Administradora.objects.create(razao_social="A")
        url = f"/api/v1/clientes/{c.pk}/administradora/"
        self.assertEqual(self.api.get("/api/v1/administradoras/").status_code, 403)
        for perm in ["view_cliente", "change_cliente", "view_administradora"]:
            self.autorizar(perm)
            self.assertEqual(self.api.post(url, {"acao": "vincular", "administradora": a.pk, "data": "2020-01-01"}).status_code, 403)
        self.autorizar("delete_administradora")
        self.assertEqual(self.api.delete(f"/api/v1/administradoras/{a.pk}/").status_code, 405)

    def test_admin_administradora_e_vinculo(self):
        self.user.is_staff = True
        self.user.save()
        self.user.user_permissions.set(Permission.objects.filter(content_type__app_label="clientes", codename__in=["add_administradora", "view_administradora", "change_cliente", "view_cliente"]))
        self.client.force_login(self.user)
        payload = {"razao_social": "Admin Teste", "cnpj": "12.345.678/0001-00", "nome_fantasia": "", "telefone": "", "email": "", "_save": "Salvar"}
        self.assertEqual(self.client.post("/admin/clientes/administradora/add/", payload).status_code, 302)
        a = Administradora.objects.get()
        self.assertEqual(a.cnpj, "12345678000100")
        c = Cliente.objects.create(razao_social="Cliente")
        url = f"/admin/clientes/cliente/{c.pk}/administradora/"
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.post(url, {"acao": "vincular", "administradora": a.pk, "data": "2020-01-01"}).status_code, 302)
        self.assertContains(self.client.get(f"/admin/clientes/cliente/{c.pk}/change/"), "Admin Teste")
        self.assertEqual(self.client.post(url, {"acao": "encerrar", "data": "2019-01-01"}).status_code, 200)
        self.assertEqual(self.client.post(url, {"acao": "encerrar", "data": "2021-01-01"}).status_code, 302)
        self.assertIsNotNone(c.historico_administradoras.get().data_fim)

    def test_contato_cadastro_encerramento_e_historico(self):
        self.autorizar("add_contato", "change_contato", "view_contato")
        cliente = Cliente.objects.create(razao_social="Condomínio")
        payload = {"cliente": cliente.pk, "nome": "Ana", "funcao": "Síndica",
                   "telefone": "85999999999", "email": "ana@example.com", "data_inicio": "2020-01-01"}
        response = self.api.post("/api/v1/contatos/", payload)
        self.assertEqual(response.status_code, 201, response.data)
        contato_id = response.data["id"]
        self.assertTrue(response.data["vigente"])
        response = self.api.patch(f"/api/v1/contatos/{contato_id}/", {"data_fim": "2021-01-01"})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(response.data["vigente"])
        self.assertEqual(self.api.get(f"/api/v1/contatos/?cliente={cliente.pk}&vigente=true").data["count"], 0)
        self.assertEqual(self.api.get(f"/api/v1/contatos/?cliente={cliente.pk}&vigente=false").data["count"], 1)
        payload.update(nome="João", data_inicio="2021-01-02")
        self.assertEqual(self.api.post("/api/v1/contatos/", payload).status_code, 201)
        self.assertEqual(cliente.contatos.count(), 2)
        self.assertEqual(self.api.get("/api/v1/contatos/?search=João").data["count"], 1)

    def test_contato_permissoes_e_exclusao(self):
        cliente = Cliente.objects.create(razao_social="Condomínio")
        contato = Contato.objects.create(cliente=cliente, nome="Ana", data_inicio="2020-01-01")
        self.assertEqual(self.api.get("/api/v1/contatos/").status_code, 403)
        self.autorizar("view_cliente", "change_cliente")
        self.assertEqual(self.api.get("/api/v1/contatos/").status_code, 403)
        self.autorizar("view_contato")
        self.assertEqual(self.api.get("/api/v1/contatos/").status_code, 200)
        self.assertEqual(self.api.patch(f"/api/v1/contatos/{contato.pk}/", {"nome": "Outro"}).status_code, 403)
        self.autorizar("delete_contato")
        self.assertEqual(self.api.delete(f"/api/v1/contatos/{contato.pk}/").status_code, 405)
        self.assertTrue(Contato.objects.filter(pk=contato.pk).exists())

    def test_contato_valida_datas_email_e_cliente(self):
        self.autorizar("add_contato", "change_contato", "view_contato")
        cliente = Cliente.objects.create(razao_social="Condomínio")
        outro = Cliente.objects.create(razao_social="Outro")
        base = {"cliente": cliente.pk, "nome": "Ana", "data_inicio": "2020-01-01"}
        for extra in [{"email": "invalido"}, {"nome": " "}, {"data_fim": "2019-01-01"}, {"cliente": 999999}]:
            response = self.api.post("/api/v1/contatos/", {**base, **extra})
            self.assertEqual(response.status_code, 400, response.data)
        contato = Contato.objects.create(cliente=cliente, nome="Ana", data_inicio="2020-01-01", data_fim="2021-01-01")
        url = f"/api/v1/contatos/{contato.pk}/"
        for extra in [{"cliente": outro.pk}, {"data_inicio": "2022-01-01"}, {"data_fim": "2019-01-01"}]:
            self.assertEqual(self.api.patch(url, extra).status_code, 400)
        contato.refresh_from_db()
        self.assertEqual(contato.cliente_id, cliente.pk)
        self.assertEqual(str(contato.data_inicio), "2020-01-01")
        for query in ["cliente=abc", "vigente=sim"]:
            self.assertEqual(self.api.get("/api/v1/contatos/?" + query).status_code, 400)

    def test_contatos_multiplos_e_filtro_por_cliente(self):
        self.autorizar("view_contato")
        a = Cliente.objects.create(razao_social="A")
        b = Cliente.objects.create(razao_social="B")
        for cliente, nome in [(a, "Síndico"), (a, "Encarregado"), (b, "Supervisor")]:
            Contato.objects.create(cliente=cliente, nome=nome, data_inicio="2020-01-01")
        self.assertEqual(self.api.get(f"/api/v1/contatos/?cliente={a.pk}&vigente=true").data["count"], 2)

    def test_admin_contato_preserva_vinculo_e_rejeita_datas(self):
        self.user.is_staff = True
        self.user.save()
        self.user.user_permissions.set(Permission.objects.filter(content_type__app_label="clientes", codename__in=["add_contato", "change_contato", "view_contato", "view_cliente"]))
        self.client.force_login(self.user)
        cliente = Cliente.objects.create(razao_social="Cliente")
        data = {"cliente": cliente.pk, "nome": "Ana", "funcao": "Síndica", "telefone": "", "email": "",
                "data_inicio": "2020-01-01", "data_fim": "2019-01-01", "_save": "Salvar"}
        response = self.client.post("/admin/clientes/contato/add/", data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "O encerramento não pode ser anterior ao início.")
        self.assertFalse(Contato.objects.exists())
        data["data_fim"] = ""
        self.assertEqual(self.client.post("/admin/clientes/contato/add/", data).status_code, 302)
        contato = Contato.objects.get()
        page = self.client.get(f"/admin/clientes/contato/{contato.pk}/change/")
        self.assertNotContains(page, 'name="cliente"')
        self.assertContains(self.client.get(f"/admin/clientes/cliente/{cliente.pk}/change/"), "Ana")
        self.assertEqual(self.client.get(f"/admin/clientes/contato/{contato.pk}/delete/").status_code, 403)

    def test_anonimo_nao_consulta_nem_cadastra(self):
        self.assertEqual(self.api.get("/api/v1/clientes/").status_code, 403)
        self.assertEqual(self.api.post("/api/v1/clientes/", {
            "razao_social": "Teste"
        }).status_code, 403)

    def test_login_sem_permissao_nao_consulta(self):
        self.api.force_authenticate(self.user)
        self.assertEqual(self.api.get("/api/v1/clientes/").status_code, 403)

    def test_leitor_pesquisa_mas_nao_cadastra(self):
        Cliente.objects.create(razao_social="Condominio Boa Vista", cidade="Fortaleza")
        Cliente.objects.create(razao_social="Condominio Jardim", cidade="Recife")
        self.autorizar("view_cliente")
        response = self.api.get("/api/v1/clientes/?search=Fortaleza")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["razao_social"], "Condominio Boa Vista")
        self.assertEqual(self.api.post("/api/v1/clientes/", {
            "razao_social": "Nao autorizado"
        }).status_code, 403)

    def test_cadastro_e_edicao_preservam_id_e_criacao(self):
        self.autorizar("add_cliente", "change_cliente", "view_cliente")
        response = self.api.post("/api/v1/clientes/", {
            "cnpj": "12.345.678/0001-00", "logradouro": "Rua Teste", "numero": "10", "bairro": "Centro", "cidade": "Fortaleza",
            "razao_social": "Condominio Teste", "estado": "CE", "cep": "60000000",
            "id": 999999, "criado_em": "2000-01-01T00:00:00",
        }, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        cliente = Cliente.objects.get(pk=response.data["id"])
        self.assertNotEqual(cliente.pk, 999999)
        self.assertEqual(cliente.historico_cnpj.get().cnpj, "12345678000100")
        criado = cliente.criado_em
        anterior = timezone.now() - timedelta(days=1)
        Cliente.objects.filter(pk=cliente.pk).update(atualizado_em=anterior)
        response = self.api.patch(f"/api/v1/clientes/{cliente.pk}/", {
            "nome_fantasia": "Novo nome", "criado_em": "2000-01-01T00:00:00"
        }, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        cliente.refresh_from_db()
        self.assertEqual(cliente.criado_em, criado)
        self.assertGreater(cliente.atualizado_em, anterior)
        self.assertEqual(cliente.nome_fantasia, "Novo nome")

    def test_rejeita_campos_invalidos(self):
        self.autorizar("add_cliente")
        for payload, campo in [
            ({"razao_social": "   "}, "razao_social"),
            ({"razao_social": "Teste", "cep": "60000-000"}, "cep"),
            ({"razao_social": "Teste", "estado": "ZZ"}, "estado"),
        ]:
            with self.subTest(campo=campo):
                response = self.api.post("/api/v1/clientes/", payload, format="json")
                self.assertEqual(response.status_code, 400)
                self.assertIn(campo, response.data)
        self.assertEqual(Cliente.objects.count(), 0)

    def test_exclusao_indisponivel_mesmo_com_permissao(self):
        self.autorizar("delete_cliente", "view_cliente")
        cliente = Cliente.objects.create(razao_social="Preservar")
        self.assertEqual(self.api.delete(f"/api/v1/clientes/{cliente.pk}/").status_code, 405)
        self.assertTrue(Cliente.objects.filter(pk=cliente.pk).exists())

    def test_cliente_inexistente_retorna_404(self):
        self.autorizar("view_cliente")
        self.assertEqual(self.api.get("/api/v1/clientes/999999/").status_code, 404)

    def test_troca_cnpj_preserva_historico(self):
        self.autorizar("change_cliente", "view_cliente")
        cliente = Cliente.objects.create(razao_social="Historico")
        url = f"/api/v1/clientes/{cliente.pk}/cnpj/"
        self.assertIsNone(self.api.get(url).data["atual"])
        for cnpj, inicio in [("12345678000100", "2020-01-01"), ("22345678000100", "2021-01-01")]:
            response = self.api.post(url, {"cnpj": cnpj, "data_inicio": inicio})
            self.assertEqual(response.status_code, 201, response.data)
        data = self.api.get(url).data
        self.assertEqual(data["atual"]["cnpj"], "22345678000100")
        self.assertEqual(len(data["historico"]), 2)
        self.assertEqual(data["historico"][1]["data_fim"], "2020-12-31")
        self.assertEqual(Cliente.objects.count(), 1)

    def test_cnpj_invalido_duplicado_e_datas_nao_encerram_atual(self):
        self.autorizar("change_cliente")
        cliente = Cliente.objects.create(razao_social="Original")
        outro = Cliente.objects.create(razao_social="Outro")
        HistoricoCNPJ.objects.create(cliente=cliente, cnpj="12345678000100", data_inicio="2020-01-01")
        HistoricoCNPJ.objects.create(cliente=outro, cnpj="22345678000100", data_inicio="2020-01-01")
        for cnpj, inicio in [("123", "2021-01-01"), ("22345678000100", "2021-01-01"),
                             ("32345678000100", "2020-01-01"), ("32345678000100", "2999-01-01")]:
            with self.subTest(cnpj=cnpj, inicio=inicio):
                response = self.api.post(f"/api/v1/clientes/{cliente.pk}/cnpj/", {"cnpj": cnpj, "data_inicio": inicio})
                self.assertEqual(response.status_code, 400, response.data)
                self.assertEqual(cliente.historico_cnpj.count(), 1)
                self.assertIsNone(cliente.historico_cnpj.get().data_fim)

    def test_cnpj_leitor_e_cadastrador_nao_trocam(self):
        cliente = Cliente.objects.create(razao_social="Protegido")
        for permission in ["view_cliente", "add_cliente"]:
            self.autorizar(permission)
            response = self.api.post(f"/api/v1/clientes/{cliente.pk}/cnpj/", {"cnpj": "12345678000100", "data_inicio": "2020-01-01"})
            self.assertEqual(response.status_code, 403)
        self.assertFalse(HistoricoCNPJ.objects.exists())

    def test_admin_formulario_e_historico(self):
        self.user.is_staff = True
        self.user.save()
        self.user.user_permissions.set(Permission.objects.filter(content_type__app_label="clientes", codename__in=["view_cliente", "change_cliente"]))
        self.client.force_login(self.user)
        cliente = Cliente.objects.create(razao_social="Painel")
        url = f"/admin/clientes/cliente/{cliente.pk}/cnpj/"
        self.assertEqual(self.client.get(url).status_code, 200)
        response = self.client.post(url, {"cnpj": "123", "data_inicio": "2020-01-01"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(HistoricoCNPJ.objects.exists())
        response = self.client.post(url, {"cnpj": "12345678000100", "data_inicio": "2020-01-01"})
        self.assertEqual(response.status_code, 302)
        response = self.client.get(f"/admin/clientes/cliente/{cliente.pk}/change/")
        self.assertContains(response, "12345678000100")
        self.user.user_permissions.clear()
        self.assertEqual(self.client.get(url).status_code, 403)

    def dados_cadastro(self):
        return {"cnpj": "12.345.678/0001-00", "razao_social": "Novo cliente",
                "logradouro": "Rua Teste", "numero": "S/N", "bairro": "Centro",
                "cidade": "Fortaleza", "estado": "CE", "cep": "60000000", "data_inicio": "2020-01-01"}

    def test_cadastro_exige_cnpj_e_endereco(self):
        self.autorizar("add_cliente")
        for campo in ["cnpj", "logradouro", "numero", "bairro", "cidade", "estado", "cep"]:
            payload = self.dados_cadastro()
            payload.pop(campo)
            response = self.api.post("/api/v1/clientes/", payload)
            self.assertEqual(response.status_code, 400, response.data)
            self.assertIn(campo, response.data)
        self.assertEqual(Cliente.objects.count(), 0)

    def test_cadastro_duplicado_ou_data_invalida_nao_deixa_cliente_orfao(self):
        self.autorizar("add_cliente")
        payload = self.dados_cadastro()
        self.assertEqual(self.api.post("/api/v1/clientes/", payload).status_code, 201)
        self.assertEqual(self.api.post("/api/v1/clientes/", payload).status_code, 400)
        payload.update(cnpj="AB123456000100", data_inicio="2999-01-01")
        self.assertEqual(self.api.post("/api/v1/clientes/", payload).status_code, 400)
        self.assertEqual(Cliente.objects.count(), 1)
        self.assertEqual(HistoricoCNPJ.objects.count(), 1)

    def test_admin_cadastra_cliente_e_cnpj_juntos(self):
        self.user.is_staff = True
        self.user.save()
        self.user.user_permissions.set(Permission.objects.filter(content_type__app_label="clientes", codename__in=["add_cliente", "view_cliente"]))
        self.client.force_login(self.user)
        url = "/admin/clientes/cliente/add/"
        page = self.client.get(url)
        self.assertContains(page, 'id_cnpj')
        self.assertLess(page.content.index(b'id_cnpj'), page.content.index(b'id_razao_social'))
        dados = self.dados_cadastro()
        dados.pop("cnpj")
        self.assertEqual(self.client.post(url, dados).status_code, 200)
        self.assertEqual(Cliente.objects.count(), 0)
        self.assertEqual(self.client.post(url, self.dados_cadastro()).status_code, 302)
        self.assertEqual(Cliente.objects.get().historico_cnpj.count(), 1)

    def test_consulta_mapeia_endereco_e_trata_falha(self):
        from .consulta import consultar_cnpj, ErroConsulta
        response = MagicMock()
        response.__enter__.return_value.read.return_value = b'{"cnpj":"12345678000100","razao_social":"Exemplo","municipio":"Fortaleza","uf":"CE","cep":"60000-000","descricao_tipo_de_logradouro":"RUA","logradouro":"TESTE"}'
        with patch("clientes.consulta.urlopen", return_value=response):
            dados = consultar_cnpj("12.345.678/0001-00")
        self.assertEqual(dados["logradouro"], "RUA TESTE")
        self.assertEqual(dados["cep"], "60000000")
        self.assertEqual(dados["cidade"], "Fortaleza")
        with patch("clientes.consulta.urlopen", side_effect=URLError("offline")):
            with self.assertRaises(ErroConsulta):
                consultar_cnpj("12345678000100")

    def test_consulta_exige_permissao_e_cnpj_valido(self):
        self.user.is_staff = True
        self.user.save()
        self.client.force_login(self.user)
        url = "/admin/clientes/cliente/consultar-cnpj/"
        self.assertEqual(self.client.get(url, {"cnpj": "12345678000100"}).status_code, 403)
        self.user.user_permissions.add(Permission.objects.get(content_type__app_label="clientes", codename="add_cliente"))
        with patch("clientes.consulta.urlopen") as consulta:
            self.assertEqual(self.client.get(url, {"cnpj": "../"}).status_code, 400)
            consulta.assert_not_called()

    def test_cep_mapeamento_erros_e_campos_preservados(self):
        from .consulta import consultar_cep, ErroConsulta
        response = MagicMock()
        response.__enter__.return_value.read.return_value = b'{"cep":"01001-000","logradouro":"Praca da Se","bairro":"Se","localidade":"Sao Paulo","uf":"SP","complemento":"lado impar"}'
        with patch("clientes.consulta.urlopen", return_value=response):
            dados = consultar_cep("01001-000")
        self.assertEqual(dados, {"logradouro": "Praca da Se", "bairro": "Se", "cidade": "Sao Paulo", "estado": "SP"})
        response.__enter__.return_value.read.return_value = b'{"erro":true}'
        with patch("clientes.consulta.urlopen", return_value=response):
            with self.assertRaises(ErroConsulta):
                consultar_cep("99999999")
        with patch("clientes.consulta.urlopen", side_effect=URLError("offline")):
            with self.assertRaises(ErroConsulta):
                consultar_cep("01001000")

    def test_cep_ordem_normalizacao_e_permissao(self):
        from .forms import CadastroClienteForm, ClienteEnderecoForm
        dados = self.dados_cadastro()
        dados["cep"] = "60000-000"
        form = CadastroClienteForm(dados)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["cep"], "60000000")
        self.assertLess(list(form.fields).index("cep"), list(form.fields).index("logradouro"))
        edit = ClienteEnderecoForm(dados, instance=Cliente(razao_social="Editar"))
        self.assertTrue(edit.is_valid(), edit.errors)
        self.assertEqual(edit.cleaned_data["cep"], "60000000")
        self.user.is_staff = True
        self.user.save()
        self.client.force_login(self.user)
        url = "/admin/clientes/cliente/consultar-cep/"
        self.assertEqual(self.client.get(url, {"cep": "01001000"}).status_code, 403)
        self.user.user_permissions.add(Permission.objects.get(content_type__app_label="clientes", codename="change_cliente"))
        with patch("clientes.consulta.urlopen") as consulta:
            self.assertEqual(self.client.get(url, {"cep": "../"}).status_code, 400)
            consulta.assert_not_called()

    def test_consulta_cnpj_administradora_e_troca_cliente(self):
        self.user.is_staff = True
        self.user.save()
        self.client.force_login(self.user)
        url = "/admin/clientes/administradora/consultar-cnpj/"
        self.assertEqual(self.client.get(url, {"cnpj": "12345678000100"}).status_code, 403)
        self.user.user_permissions.set(Permission.objects.filter(content_type__app_label="clientes", codename__in=["change_administradora", "change_cliente"]))
        dados = {"razao_social": "Empresa teste", "telefone": "1133334444", "email": "teste@example.com"}
        with patch("clientes.admin.consultar_cnpj", return_value=dados):
            self.assertEqual(self.client.get(url, {"cnpj": "12345678000100"}).json(), dados)
            self.assertEqual(self.client.get("/admin/clientes/cliente/consultar-cnpj/", {"cnpj": "12345678000100"}).status_code, 200)
        a = Administradora.objects.create(razao_social="A")
        self.assertContains(self.client.get(f"/admin/clientes/administradora/{a.pk}/change/"), "consulta-cnpj-script")
        c = Cliente.objects.create(razao_social="Cliente")
        self.assertContains(self.client.get(f"/admin/clientes/cliente/{c.pk}/cnpj/"), "consulta-cnpj-script")
