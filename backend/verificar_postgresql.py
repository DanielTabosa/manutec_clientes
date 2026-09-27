"""Validação PostgreSQL em banco descartável; nunca reutiliza o banco instalado.

Execute da raiz: .venv/Scripts/python.exe backend/verificar_postgresql.py
Use --keep somente para inspeção visual posterior; remova o banco indicado ao terminar.
"""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import uuid

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--keep', action='store_true')
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    import django
    django.setup()
    if args.worker:
        return worker()
    import psycopg
    from psycopg import sql
    from django.db import connection
    params = connection.get_connection_params()
    params.pop('cursor_factory', None)
    params.pop('context', None)
    name = 'manutec_validacao_' + uuid.uuid4().hex[:12]
    with psycopg.connect(**params, autocommit=True) as admin:
        admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
        try:
            env = dict(os.environ, POSTGRES_DB=name, DJANGO_DEBUG='False')
            result = subprocess.run([sys.executable, __file__, '--worker'], env=env)
            if result.returncode:
                raise RuntimeError('Validação falhou; banco descartável será removido.')
            if args.keep:
                print('Banco isolado para inspeção:', name, flush=True)
                return
        finally:
            if not args.keep or sys.exc_info()[0]:
                admin.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name)))
                print('Banco descartável removido.', flush=True)


def worker():
    import unittest
    from concurrent.futures import ThreadPoolExecutor
    from datetime import date
    from threading import Event, Barrier
    import time
    from django.conf import settings
    from django.core.management import call_command
    from django.core.exceptions import ValidationError
    from django.db import connection, connections, transaction, IntegrityError
    from django.contrib.auth.models import User, Permission
    from django.test import Client, override_settings
    from rest_framework.test import APIClient
    from clientes.models import Cliente, Administradora, ContatoAdministradora, Responsabilidade
    from clientes.services import cadastrar_cliente, alterar_administradora
    assert settings.DATABASES['default']['NAME'].startswith('manutec_validacao_')
    with connection.cursor() as cursor:
        cursor.execute((Path(__file__).resolve().parent.parent / 'database/schema.sql').read_text())
    # Dados legados antes da migration nova: preservação verificada sem ler produção.
    with connection.cursor() as cursor:
        cursor.execute("INSERT INTO clientes (razao_social) VALUES ('Legado migration QA') RETURNING id")
        legado_id = cursor.fetchone()[0]
        cursor.execute("INSERT INTO historico_cnpj (cliente_id,cnpj,data_inicio) VALUES (%s,'98000000000100','2020-01-01')", [legado_id])
        cursor.execute("INSERT INTO destinatarios_faturamento (cliente_id,email,tipo_destinatario,data_inicio) VALUES (%s,'legado@example.invalid','copia','2020-01-01')", [legado_id])
    call_command('migrate', verbosity=0, interactive=False)
    with connection.cursor() as cursor:
        cursor.execute('SELECT email,tipo_destinatario FROM destinatarios_faturamento WHERE cliente_id=%s',[legado_id])
        assert cursor.fetchone() == ('legado@example.invalid','copia')


    class Validacao(unittest.TestCase):
        counter = 0

        def setUp(self):
            Validacao.counter += 1
            n = Validacao.counter
            self.a = Administradora.objects.create(razao_social=f'Administradora QA {n}')
            self.b = Administradora.objects.create(razao_social=f'Outra QA {n}')
            self.c = cadastrar_cliente(cnpj=f'{n:012d}00', razao_social=f'Condomínio QA {n}',
                logradouro='Rua de teste', numero='1', bairro='Centro', cidade='Fortaleza', estado='CE', cep='60000000', data_inicio=date(2020,1,1))
            alterar_administradora(self.c.pk, acao='vincular', administradora=self.a, data=date(2020,1,1))
            self.p = ContatoAdministradora.objects.create(administradora=self.a, nome='Ana QA', email='qa@example.invalid')

        def criar(self, **extra):
            dados = dict(cliente_id=self.c.pk, contato_administradora_id=self.p.pk, funcao='Financeiro', data_inicio=date(2020,2,1))
            dados.update(extra)
            return Responsabilidade.objects.create(**dados)

        def test_restricoes_reais_e_trigger_cnpj(self):
            with self.assertRaises(IntegrityError), transaction.atomic():
                Cliente.objects.create(razao_social='Sem CNPJ QA')
            with self.assertRaises(IntegrityError), transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute('INSERT INTO responsabilidades (cliente_id,contato_administradora_id,funcao,data_inicio,data_fim) VALUES (%s,%s,%s,%s,%s)',
                        [self.c.pk,self.p.pk,'QA',date(2020,2,1),date(2020,1,1)])
            with self.assertRaises(IntegrityError), transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute('INSERT INTO responsabilidades (cliente_id,contato_administradora_id,funcao,data_inicio) VALUES (%s,%s,%s,%s)',
                        [self.c.pk,-1,'QA',date(2020,2,1)])

        def test_datas_duplicidade_e_relacoes(self):
            r=self.criar()
            for extra in [dict(funcao=' FINANCEIRO '),dict(data_inicio=date(2999,1,1)),dict(data_fim=date(2999,1,1)),dict(data_inicio=date(2019,1,1)),dict(data_fim=date(2019,1,1))]:
                with self.assertRaises(ValidationError): self.criar(**extra)
            self.criar(funcao='Gerente')
            p=ContatoAdministradora.objects.create(administradora=self.a,nome=self.p.nome,email=self.p.email)
            self.criar(contato_administradora_id=p.pk)
            r.contato_administradora=p
            with self.assertRaises(ValidationError): r.save()
            self.p.administradora=self.b
            with self.assertRaises(ValidationError): self.p.save()

        def test_troca_rollback_e_retorno(self):
            r=self.criar()
            with self.assertRaises(ValidationError):
                alterar_administradora(self.c.pk,acao='vincular',administradora=self.b,data=date(2020,1,15))
            r.refresh_from_db(); self.assertIsNone(r.data_fim)
            self.assertEqual(self.c.historico_administradoras.count(),1)
            alterar_administradora(self.c.pk,acao='vincular',administradora=self.b,data=date(2020,3,1))
            r.refresh_from_db(); self.assertEqual(r.data_fim,date(2020,2,29))
            alterar_administradora(self.c.pk,acao='vincular',administradora=self.a,data=date(2020,4,1))
            with self.assertRaises(ValidationError): self.criar(funcao='Outra',data_fim=date(2020,4,2))
            self.criar(data_inicio=date(2020,4,1))

        def test_rollback_apos_encerrar_responsabilidades(self):
            from unittest.mock import patch
            r=self.criar()
            with patch('clientes.services.ClienteAdministradora.objects.create',side_effect=IntegrityError('falha simulada')):
                with self.assertRaises(ValidationError):
                    alterar_administradora(self.c.pk,acao='vincular',administradora=self.b,data=date(2020,3,1))
            r.refresh_from_db(); self.assertIsNone(r.data_fim)
            self.assertEqual(self.c.historico_administradoras.count(),1)
            self.assertIsNone(self.c.historico_administradoras.get().data_fim)

        def test_concorrencia_duplicidade(self):
            barrier=Barrier(2)
            def attempt():
                try:
                    barrier.wait(timeout=5)
                    self.criar()
                    return 'salvo'
                except ValidationError:
                    return 'rejeitado'
                finally:
                    connections.close_all()
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures=[pool.submit(attempt) for _ in range(2)]
                self.assertCountEqual([f.result(timeout=15) for f in futures],['salvo','rejeitado'])
            self.assertEqual(self.c.responsabilidades.count(),1)

        def corrida(self, troca_primeiro):
            locked=Event(); release=Event(); started=Event(); pid=[]
            def trocar():
                alterar_administradora(self.c.pk,acao='vincular',administradora=self.b,data=date(2020,3,1))
            first,second=(trocar,self.criar) if troca_primeiro else (self.criar,trocar)
            def owner():
                try:
                    with transaction.atomic():
                        Cliente.objects.select_for_update().get(pk=self.c.pk)
                        first();locked.set()
                        if not release.wait(10): raise AssertionError('timeout no bloqueio')
                finally: connections.close_all()
            def waiter():
                try:
                    with connections['default'].cursor() as cursor:
                        cursor.execute('SELECT pg_backend_pid()');pid.append(cursor.fetchone()[0])
                    started.set()
                    try: second();return 'salvo'
                    except ValidationError: return 'rejeitado'
                finally: connections.close_all()
            with ThreadPoolExecutor(max_workers=2) as pool:
                f=pool.submit(owner)
                self.assertTrue(locked.wait(5))
                g=pool.submit(waiter)
                try:
                    self.assertTrue(started.wait(5))
                    deadline=time.monotonic()+5;blocked=False
                    while time.monotonic()<deadline:
                        with connection.cursor() as cursor:
                            cursor.execute('SELECT cardinality(pg_blocking_pids(%s))',[pid[0]])
                            blocked=cursor.fetchone()[0]>0
                        if blocked: break
                        time.sleep(.02)
                    self.assertTrue(blocked,'A operação concorrente deve aguardar o cliente bloqueado')
                finally: release.set()
                f.result(timeout=10)
                self.assertEqual(g.result(timeout=10),'rejeitado' if troca_primeiro else 'salvo')
            if troca_primeiro: self.assertFalse(self.c.responsabilidades.exists())
            else: self.assertEqual(self.c.responsabilidades.get().data_fim,date(2020,2,29))

        def test_concorrencia_troca_antes_cadastro(self): self.corrida(True)
        def test_concorrencia_cadastro_antes_troca(self): self.corrida(False)

        @override_settings(ALLOWED_HOSTS=['testserver'])
        def test_painel_api_permissoes(self):
            u=User.objects.create_user(username='operador_qa',password='teste-isolado',is_staff=True)
            u.user_permissions.set(Permission.objects.filter(content_type__app_label='clientes',codename__in=[
                'view_cliente','view_administradora','add_contatoadministradora','view_contatoadministradora','change_contatoadministradora',
                'add_responsabilidade','view_responsabilidade','change_responsabilidade']))
            browser=Client();browser.force_login(u)
            data=dict(cliente=self.c.pk,contato_administradora=self.p.pk,funcao='Financeiro',data_inicio='2019-01-01',data_fim='',_save='Salvar')
            response=browser.post('/admin/clientes/responsabilidade/add/',data)
            self.assertEqual(response.status_code,200);self.assertIn('O período deve estar contido',response.content.decode())
            data['data_inicio']='2020-02-01'
            self.assertEqual(browser.post('/admin/clientes/responsabilidade/add/',data).status_code,302)
            r=self.c.responsabilidades.get()
            self.assertEqual(browser.get('/admin/clientes/responsabilidade/').status_code,200)
            data['data_fim']='2020-03-01'
            self.assertEqual(browser.post(f'/admin/clientes/responsabilidade/{r.pk}/change/',data).status_code,302)
            r.refresh_from_db();self.assertEqual(r.data_fim,date(2020,3,1))
            self.assertEqual(browser.get(f'/admin/clientes/responsabilidade/{r.pk}/delete/').status_code,403)
            api=APIClient();api.force_authenticate(u)
            self.assertEqual(api.get(f'/api/v1/responsabilidades/?cliente={self.c.pk}&vigente=false').data['count'],1)
            self.assertEqual(api.patch(f'/api/v1/contatos-administradora/{self.p.pk}/',{'telefone':'99999'}).status_code,200)
            r.refresh_from_db();self.assertEqual(r.contato_administradora.telefone,'99999')
            u.user_permissions.clear();api.force_authenticate(User.objects.get(pk=u.pk))
            self.assertEqual(api.get('/api/v1/responsabilidades/').status_code,403)


        def test_destinatarios_regras_constraints_historico(self):
            from clientes import destinatarios as d
            from clientes.models import ConfiguracaoDestinatarios, ItemDestinatario
            d.salvar(administradora_id=self.a.pk,numero=0,itens=[dict(contato_administradora_id=self.p.pk,laudo=True)])
            v=self.c.historico_administradoras.get(data_fim__isnull=True)
            d.salvar(cliente_id=self.c.pk,vinculo_id=v.pk,numero=0,modo='usar',itens=[dict(contato_administradora_id=self.p.pk,encerrado_local=True)])
            self.assertEqual(d.efetivos(self.c.pk),[])
            with self.assertRaises(IntegrityError),transaction.atomic():
                ConfiguracaoDestinatarios.objects.create(cliente=self.c,administradora=self.a)
            with self.assertRaises(IntegrityError),transaction.atomic():
                ItemDestinatario.objects.create(revisao=d.atual(cliente_id=self.c.pk),contato_administradora=self.p)
            self.assertEqual(d.atual(cliente_id=self.c.pk).numero,1)
            alterar_administradora(self.c.pk,acao='vincular',administradora=self.b,data=date(2021,1,1))
            self.assertEqual(d.atual(cliente_id=self.c.pk).numero,2)
            self.assertEqual(d.efetivos(self.c.pk),[])

        def test_destinatarios_edicao_concorrente(self):
            from clientes import destinatarios as d
            barrier=Barrier(2)
            def gravar():
                try:
                    barrier.wait(timeout=5)
                    d.salvar(administradora_id=self.a.pk,numero=0,itens=[dict(contato_administradora_id=self.p.pk,boleto=True)])
                    return 'salvo'
                except ValidationError: return 'rejeitado'
                finally: connections.close_all()
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures=[pool.submit(gravar) for _ in range(2)]
                self.assertCountEqual([f.result(timeout=15) for f in futures],['salvo','rejeitado'])

        def test_destinatarios_encerramento_bloqueia_selecao(self):
            from clientes import destinatarios as d
            locked=Event();release=Event();started=Event();pid=[]
            def encerrar():
                try:
                    with transaction.atomic():
                        d.encerrar_global(self.p.pk);locked.set()
                        if not release.wait(10): raise AssertionError('timeout')
                finally: connections.close_all()
            def selecionar():
                try:
                    with connections['default'].cursor() as cur:
                        cur.execute('SELECT pg_backend_pid()');pid.append(cur.fetchone()[0])
                    started.set()
                    try:
                        d.salvar(administradora_id=self.a.pk,numero=0,itens=[dict(contato_administradora_id=self.p.pk,boleto=True)])
                        return 'salvo'
                    except ValidationError: return 'rejeitado'
                finally: connections.close_all()
            with ThreadPoolExecutor(max_workers=2) as pool:
                first=pool.submit(encerrar);self.assertTrue(locked.wait(5));second=pool.submit(selecionar)
                try:
                    self.assertTrue(started.wait(5));deadline=time.monotonic()+5;blocked=False
                    while time.monotonic()<deadline:
                        with connection.cursor() as cur:
                            cur.execute('SELECT cardinality(pg_blocking_pids(%s))',[pid[0]]);blocked=cur.fetchone()[0]>0
                        if blocked: break
                        time.sleep(.02)
                    self.assertTrue(blocked)
                finally: release.set()
                first.result(timeout=10);self.assertEqual(second.result(timeout=10),'rejeitado')
            self.assertIsNone(d.atual(administradora_id=self.a.pk))

    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Validacao))
    if not result.wasSuccessful(): sys.exit(1)
    # Usuário fictício apenas no banco descartável, para inspeção visual local.
    User.objects.create_superuser(username='visual_qa',password='teste-visual-isolado',email='qa@example.invalid')
    a = Administradora.objects.create(razao_social='Administradora Visual Alfa')
    Administradora.objects.create(razao_social='Administradora Visual Beta')
    for i, nome in enumerate(['Condomínio Visual Sol', 'Condomínio Visual Mar'], 1):
        c = cadastrar_cliente(cnpj=f'99000000000{i}00', razao_social=nome,
            logradouro='Rua QA', numero='1', bairro='Centro', cidade='Fortaleza',
            estado='CE', cep='60000000', data_inicio=date(2020, 1, 1))
        alterar_administradora(c.pk, acao='vincular', administradora=a, data=date(2020, 1, 1))
    print('PostgreSQL: 11 verificações aprovadas; schema e migrations instalados apenas no banco descartável.',flush=True)


if __name__=='__main__': main()
