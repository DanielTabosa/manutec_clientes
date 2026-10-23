"""API de leitura do Jiraya, pessoa física com CPF e endereços de atendimento."""
from datetime import date, datetime, timedelta
from unittest.mock import patch

from django.contrib.auth.models import Permission, User
from django.core.exceptions import ValidationError
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from .cpf import cpf_valido, normalizar_cpf
from .models import Cliente, Contato, Endereco, HistoricoCNPJ
from .services import cadastrar_cliente, trocar_cnpj
from .test_preparacao import BasePreparacao

TOKEN = "t" * 40
CPF = "52998224725"
ENDERECO = dict(cep="60000000", logradouro="Rua A", numero="10", bairro="Centro", cidade="Fortaleza", estado="CE")


class CPFTests(BasePreparacao):
    def test_digitos_verificadores(self):
        self.assertTrue(cpf_valido(CPF))
        self.assertTrue(cpf_valido("11144477735"))
        for invalido in ("52998224724", "11111111111", "1234567890"):
            self.assertFalse(cpf_valido(invalido))
        self.assertEqual(normalizar_cpf("529.982.247-25"), CPF)
        with self.assertRaisesMessage(ValidationError, "dígitos verificadores"):
            normalizar_cpf("529.982.247-24")


@override_settings(INTEGRACAO_JIRAYA_TOKEN=TOKEN)
class IntegracaoJirayaTests(BasePreparacao):
    def setUp(self):
        super().setUp()
        HistoricoCNPJ.objects.create(cliente=self.c, cnpj="11222333000181", data_inicio=date(2020, 1, 1))
        Endereco(cliente=self.c, descricao="Principal", **ENDERECO).save()
        self.pf = cadastrar_cliente(tipo_pessoa="PF", cpf="529.982.247-25", razao_social="José Ávila",
                                    **dict(ENDERECO, cidade="Caucaia"))
        self.api = APIClient()

    def jiraya(self, token=TOKEN):
        self.api.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        return self.api

    def test_autenticacao_por_token_somente_leitura(self):
        url = "/api/integracao/v1/clientes/?busca=co"
        sem = self.api.get(url)
        self.assertEqual((sem.status_code, sem.json()["erro"]["codigo"]), (401, "nao_autenticado"))
        self.assertIn("Bearer", sem["WWW-Authenticate"])
        self.assertEqual(self.jiraya("errado").get(url).status_code, 401)
        self.assertEqual(self.jiraya(TOKEN.upper()).get(url).status_code, 401)
        with patch("clientes.integracao.hmac.compare_digest", wraps=__import__("hmac").compare_digest) as comparar:
            self.assertEqual(self.jiraya().get(url).status_code, 200)
        comparar.assert_called_once()
        # Escrita: 405 para o token; sem token, 401 antes de qualquer coisa.
        resposta = self.jiraya().post("/api/integracao/v1/clientes/", {"razao_social": "X"}, format="json")
        self.assertEqual((resposta.status_code, resposta.json()["erro"]["codigo"]), (405, "metodo_nao_permitido"))
        self.assertEqual(self.jiraya().delete(f"/api/integracao/v1/clientes/{self.c.pk}/").status_code, 405)
        self.api.credentials()
        self.assertEqual(self.api.post("/api/integracao/v1/clientes/", {}, format="json").status_code, 401)
        self.assertEqual(Cliente.objects.count(), 2)

    def test_token_nao_abre_painel_admin_nem_api_de_escrita(self):
        api = self.jiraya()
        self.assertIn(api.get("/api/v1/clientes/").status_code, (401, 403))
        self.assertIn(api.post("/api/v1/clientes/", {"razao_social": "X"}, format="json").status_code, (401, 403))
        self.assertEqual(api.get(reverse("painel:clientes")).status_code, 302)
        self.assertEqual(api.get("/admin/clientes/cliente/").status_code, 302)
        # Sessão de usuário do painel não substitui o token.
        self.api.credentials()
        self.api.force_login(self.user)
        self.assertEqual(self.api.get("/api/integracao/v1/clientes/?busca=co").status_code, 401)

    def test_token_curto_ou_vazio_desliga(self):
        for valor in ("", "curto"):
            with self.settings(INTEGRACAO_JIRAYA_TOKEN=valor):
                self.assertEqual(self.jiraya(valor or "x").get("/api/integracao/v1/clientes/?busca=co").status_code, 401)

    def test_busca_sem_acento_documento_situacao_e_paginacao(self):
        api = self.jiraya()
        dados = api.get("/api/integracao/v1/clientes/?busca=jose avila").json()
        self.assertEqual([r["id"] for r in dados["resultados"]], [self.pf.pk])
        item = dados["resultados"][0]
        self.assertEqual((item["tipo_pessoa"], item["documento"], item["nome_fantasia"], item["cidade"], item["ativo"]),
                         ("PF", {"tipo": "CPF", "numero": CPF}, None, "Caucaia", True))
        self.assertTrue(item["atualizado_em"].endswith("-03:00"))
        self.assertEqual(api.get("/api/integracao/v1/clientes/?busca=529.982").json()["total"], 1)
        # CNPJ atual e anterior encontram o cliente; o documento devolvido é sempre o atual.
        trocar_cnpj(self.c.pk, "22333444000155", date(2024, 1, 1))
        for busca in ("11.222.333", "22333444"):
            r = api.get("/api/integracao/v1/clientes/", {"busca": busca}).json()["resultados"]
            self.assertEqual([(x["id"], x["documento"]["numero"]) for x in r], [(self.c.pk, "22333444000155")])
        self.pf.ativo = False
        self.pf.save()
        self.assertEqual(api.get("/api/integracao/v1/clientes/?busca=jose").json()["total"], 0)
        self.assertEqual(api.get("/api/integracao/v1/clientes/?busca=jose&situacao=inativo").json()["total"], 1)
        self.assertEqual(api.get("/api/integracao/v1/clientes/?busca=jose&situacao=todos").json()["total"], 1)
        for i in range(3):
            Cliente.objects.create(razao_social=f"Condomínio Extra {i}")
        pagina = api.get("/api/integracao/v1/clientes/?busca=condominio&limite=2").json()
        self.assertEqual((pagina["total"], len(pagina["resultados"]), pagina["pagina"]), (4, 2, 1))
        segunda = api.get(pagina["proxima"]).json()
        self.assertEqual((len(segunda["resultados"]), segunda["proxima"]), (2, None))
        self.assertFalse({r["id"] for r in pagina["resultados"]} & {r["id"] for r in segunda["resultados"]})
        for consulta, campo in (("busca=c", "busca"), ("busca=co&limite=21", "limite"), ("busca=co&limite=0", "limite"),
                                ("busca=co&situacao=x", "situacao"), ("busca=co&pagina=a", "pagina")):
            erro = api.get("/api/integracao/v1/clientes/?" + consulta)
            self.assertEqual((erro.status_code, erro.json()["erro"]["codigo"], erro.json()["erro"]["campo"]),
                             (400, "parametro_invalido", campo))

    def test_detalhe_com_enderecos_e_contatos_vigentes(self):
        filial = Endereco(cliente=self.c, descricao="Filial Aldeota", **dict(ENDERECO, complemento="Bloco B"))
        filial.save()
        antigo = Endereco(cliente=self.c, descricao="Antigo", ativo=False, **ENDERECO)
        antigo.save()
        Contato.objects.filter(nome="Davi").update(data_fim=date(2024, 1, 1))
        dados = self.jiraya().get(f"/api/integracao/v1/clientes/{self.c.pk}/").json()
        self.assertEqual((dados["tipo_pessoa"], dados["documento"], dados["nome"], dados["ativo"]),
                         ("PJ", {"tipo": "CNPJ", "numero": "11222333000181"}, "Condomínio QA", True))
        self.assertEqual([(e["descricao"], e["principal"], e["ativo"]) for e in dados["enderecos"]],
                         [("Principal", True, True), ("Filial Aldeota", False, True), ("Antigo", False, False)])
        self.assertEqual(dados["enderecos"][1]["complemento"], "Bloco B")
        self.assertEqual(set(dados["enderecos"][0]), {"id", "descricao", "principal", "ativo", "logradouro", "numero",
                                                      "complemento", "bairro", "cidade", "estado", "cep"})
        self.assertEqual([c["nome"] for c in dados["contatos"]], ["Ana", "Eva"])
        self.assertEqual(set(dados["contatos"][0]), {"id", "nome", "funcao", "telefone", "email"})
        nao = self.jiraya().get("/api/integracao/v1/clientes/999999/")
        self.assertEqual((nao.status_code, nao.json()["erro"]["codigo"]), (404, "nao_encontrado"))
        self.assertEqual(self.jiraya().get("/api/integracao/v1/outra/").status_code, 404)
        self.assertEqual(self.jiraya().get("/api/integracao/v2/clientes/").status_code, 404)

    def test_alteracoes_por_cursor_e_atualizado_em(self):
        api = self.jiraya()
        marco = datetime.now() - timedelta(seconds=1)
        Cliente.objects.update(atualizado_em=marco)
        desde = (marco - timedelta(seconds=1)).isoformat()
        vazio = api.get("/api/integracao/v1/clientes/alteracoes/", {"desde": marco.isoformat()}).json()
        self.assertEqual(vazio["resultados"], [])
        # Contato, endereço e troca de CNPJ renovam atualizado_em do cliente.
        Contato.objects.create(cliente=self.pf, nome="Maria", data_inicio=date(2024, 1, 1))
        depois = Cliente.objects.get(pk=self.pf.pk).atualizado_em
        self.assertGreater(depois, marco)
        Cliente.objects.filter(pk=self.pf.pk).update(atualizado_em=marco)
        Endereco(cliente=self.pf, descricao="Casa de praia", **ENDERECO).save()
        self.assertGreater(Cliente.objects.get(pk=self.pf.pk).atualizado_em, marco)
        Cliente.objects.update(atualizado_em=marco)
        trocar_cnpj(self.c.pk, "22333444000155", date(2024, 1, 1))
        self.assertGreater(Cliente.objects.get(pk=self.c.pk).atualizado_em, marco)
        # Cursor estável: vários clientes no mesmo instante.
        Cliente.objects.update(atualizado_em=marco)
        extra = Cliente.objects.create(razao_social="Extra")
        Cliente.objects.filter(pk=extra.pk).update(atualizado_em=marco)
        vistos, url = [], "/api/integracao/v1/clientes/alteracoes/?" + __import__("urllib.parse").parse.urlencode(
            {"desde": desde, "limite": 1})
        while url:
            dados = api.get(url).json()
            vistos += [r["id"] for r in dados["resultados"]]
            url = dados["proxima"]
        self.assertEqual(vistos, sorted(Cliente.objects.values_list("pk", flat=True)))
        self.assertEqual(api.get("/api/integracao/v1/clientes/alteracoes/?desde=ontem").status_code, 400)
        self.assertEqual(api.get("/api/integracao/v1/clientes/alteracoes/").json()["erro"]["campo"], "desde")


class PessoaFisicaEnderecosTests(BasePreparacao):
    def setUp(self):
        super().setUp()
        self.api = APIClient()
        self.api.force_authenticate(self.user)

    def test_cadastro_pf_pela_api_e_regras(self):
        dados = dict(tipo_pessoa="PF", cpf="529.982.247-25", razao_social="José", **ENDERECO)
        resposta = self.api.post("/api/v1/clientes/", dados, format="json")
        self.assertEqual(resposta.status_code, 201, resposta.content)
        cliente = Cliente.objects.get(pk=resposta.json()["id"])
        self.assertEqual((cliente.cpf, cliente.historico_cnpj.count(), cliente.enderecos.get().principal), (CPF, 0, True))
        self.assertEqual(self.api.post("/api/v1/clientes/", dados, format="json").json()["cpf"],
                         ["Este CPF já pertence a um cliente cadastrado."])
        for extra, campo in ((dict(cpf="52998224724"), "cpf"), (dict(cpf=""), "cpf"),
                             (dict(cpf="111.444.777-35", cnpj="11222333000181"), "cnpj")):
            self.assertIn(campo, self.api.post("/api/v1/clientes/", dict(dados, **extra), format="json").json())
        self.assertIn("cpf", self.api.post("/api/v1/clientes/", dict(ENDERECO, razao_social="PJ", cnpj="11222333000181",
                                                                      cpf=CPF), format="json").json())
        url = f"/api/v1/clientes/{cliente.pk}/"
        self.assertIn("tipo_pessoa", self.api.patch(url, {"tipo_pessoa": "PJ"}, format="json").json())
        self.assertIn("endereco", self.api.patch(url, {"cidade": "Recife"}, format="json").json())
        self.assertEqual(self.api.patch(url, {"cpf": "111.444.777-35", "ativo": False}, format="json").status_code, 200)
        cliente.refresh_from_db()
        self.assertEqual((cliente.cpf, cliente.ativo), ("11144477735", False))
        self.assertIn("cnpj", self.api.post(url + "cnpj/", {"cnpj": "11222333000181", "data_inicio": "2024-01-01"},
                                            format="json").json())
        self.assertEqual(self.api.get(url).json()["enderecos"][0]["cidade"], "Fortaleza")

    def test_enderecos_principal_unico_e_inativacao(self):
        principal = Endereco(cliente=self.c, descricao="Matriz", **ENDERECO)
        principal.save()
        self.assertTrue(principal.principal)  # o primeiro endereço ativo vira principal
        filial = Endereco(cliente=self.c, descricao="Filial", **ENDERECO)
        filial.save()
        self.assertFalse(filial.principal)
        principal.ativo = False
        with self.assertRaisesMessage(ValidationError, "não pode ficar inativo"):
            principal.save()
        principal.refresh_from_db()
        principal.principal = False
        with self.assertRaisesMessage(ValidationError, "marque outro"):
            principal.save()
        filial.principal = True
        filial.save()
        principal.refresh_from_db()
        self.assertFalse(principal.principal)
        principal.ativo = False
        principal.save()
        self.assertEqual(list(self.c.enderecos.values_list("descricao", "principal", "ativo")),
                         [("Filial", True, True), ("Matriz", False, False)])
        # API: listagem por cliente; escrita exige change_cliente; sem exclusão.
        operador = User.objects.create_user("leitor", password="x")
        operador.user_permissions.add(Permission.objects.get(codename="view_cliente"))
        api = APIClient()
        api.force_authenticate(operador)
        self.assertEqual(len(api.get(f"/api/v1/enderecos/?cliente={self.c.pk}").json()["results"]), 2)
        self.assertEqual(api.post("/api/v1/enderecos/", dict(ENDERECO, cliente=self.c.pk, descricao="X"), format="json").status_code, 403)
        novo = self.api.post("/api/v1/enderecos/", dict(ENDERECO, cliente=self.c.pk, descricao="Filial 2", principal=True), format="json")
        self.assertEqual(novo.status_code, 201, novo.content)
        self.assertEqual(self.c.enderecos.get(principal=True).descricao, "Filial 2")
        self.assertIn("ativo", self.api.patch(f"/api/v1/enderecos/{novo.json()['id']}/", {"ativo": False}, format="json").json())
        self.assertEqual(self.api.delete(f"/api/v1/enderecos/{novo.json()['id']}/").status_code, 405)
        self.assertIn("logradouro", self.api.post("/api/v1/enderecos/", dict(cliente=self.c.pk, descricao="Y"), format="json").json())

    def test_painel_cadastro_pf_ficha_e_enderecos(self):
        self.client.force_login(self.user)
        dados = dict(tipo_pessoa="PF", cpf="529.982.247-25", cnpj="", razao_social="Maria Residência", nome_fantasia="",
                     cep="60000-000", logradouro="Rua A", numero="10", complemento="", bairro="Centro", cidade="Fortaleza",
                     estado="CE", data_inicio="", observacoes="")
        self.assertContains(self.client.post(reverse("painel:cliente_novo"), dict(dados, cpf="111")), "11 números")
        resposta = self.client.post(reverse("painel:cliente_novo"), dados)
        cliente = Cliente.objects.get(razao_social="Maria Residência")
        self.assertRedirects(resposta, reverse("painel:cliente", args=[cliente.pk]))
        self.assertEqual((cliente.tipo_pessoa, cliente.cpf), ("PF", CPF))
        ficha = self.client.get(reverse("painel:cliente", args=[cliente.pk])).content.decode()
        for trecho in ("529.982.247-25", "Pessoa física", "Endereços de atendimento", "Principal"):
            self.assertIn(trecho, ficha)
        self.assertNotIn("Trocar CNPJ", ficha)
        self.assertRedirects(self.client.get(reverse("painel:cliente_cnpj", args=[cliente.pk])),
                             reverse("painel:cliente", args=[cliente.pk]))
        url = reverse("painel:endereco_novo", args=[cliente.pk])
        endereco = dict(descricao="Casa de praia", cep="61600-000", logradouro="Av. B", numero="S/N", complemento="",
                        bairro="Praia", cidade="Caucaia", estado="CE")
        self.assertRedirects(self.client.post(url, endereco), reverse("painel:cliente", args=[cliente.pk]) + "#t-enderecos",
                             fetch_redirect_response=False)
        praia = cliente.enderecos.get(descricao="Casa de praia")
        self.assertFalse(praia.principal)
        self.client.post(reverse("painel:endereco_editar", args=[praia.pk]), dict(endereco, principal="on", ativo="on"))
        self.assertEqual(cliente.enderecos.get(principal=True).pk, praia.pk)
        busca = self.client.get(reverse("painel:clientes"), {"q": "Caucaia"}).content.decode()
        self.assertIn("Maria Residência", busca)
        self.assertIn("Maria Residência", self.client.get(reverse("painel:clientes"), {"q": "52998"}).content.decode())
        self.client.post(reverse("painel:cliente_editar", args=[cliente.pk]),
                         dict(razao_social="Maria Residência", cpf="111.444.777-35", observacoes=""))
        cliente.refresh_from_db()
        self.assertEqual((cliente.cpf, cliente.ativo), ("11144477735", False))  # caixa desmarcada = inativo

    def test_importacao_csv_com_cpf(self):
        from painel import importacao
        cabecalhos = ["Nome", "CPF/CNPJ", "Tipo", "Cidade"]
        linhas = [["Maria", "529.982.247-25", "", "Fortaleza"], ["Cond", "11222333000181", "", ""],
                  ["João", "1234567890", "", ""], ["Zé", "52998224724", "PF", ""], ["Ana", "52998224725", "X", ""]]
        mapa = importacao.mapear("clientes", cabecalhos)
        resultado = importacao.analisar("clientes", linhas, mapa)
        self.assertEqual([r["status"] for r in resultado], ["novo", "novo", "novo", "erro", "erro"])
        self.assertEqual((resultado[0]["dados"]["tipo_pessoa"], resultado[0]["dados"]["cpf"]), ("PF", CPF))
        self.assertEqual(resultado[1]["dados"]["tipo_pessoa"], "PJ")
        self.assertIn("CPF completado com zeros à esquerda", resultado[2]["notas"])
        with patch("painel.importacao.cnpj_dv_valido", return_value=True):
            ambiguo = importacao.analisar("clientes", [["Maria", CPF, "", ""]], mapa)[0]
        self.assertIn("Informe a coluna Tipo", " ".join(ambiguo["notas"]))
        importacao.importar("clientes", resultado)
        maria = Cliente.objects.get(cpf=CPF)
        self.assertEqual(maria.enderecos.get().cidade, "Fortaleza")
        self.assertEqual(importacao.analisar("clientes", [["Maria", CPF, "PF", ""]], mapa)[0]["status"], "existente")
        contato = importacao.analisar("contatos", [[CPF, "Pessoa"]], {"cliente": 0, "nome": 1})[0]
        self.assertEqual(contato["dados"]["cliente"], maria.pk)
