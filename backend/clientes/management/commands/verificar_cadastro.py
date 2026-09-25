from datetime import date
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction, IntegrityError
from clientes.models import Cliente, HistoricoCNPJ
from clientes.services import cadastrar_cliente, trocar_cnpj


class Command(BaseCommand):
    help = "Verifica a integridade do cadastro PostgreSQL com rollback de todos os dados temporários."

    def handle(self, *args, **options):
        if connection.vendor != "postgresql":
            raise CommandError("Use PostgreSQL para esta verificação.")
        with transaction.atomic():
            try:
                with transaction.atomic():
                    Cliente.objects.create(razao_social="TESTE TEMPORARIO SEM CNPJ")
                    with connection.cursor() as cursor:
                        cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
            except IntegrityError:
                self.stdout.write("OK: banco bloqueou cliente sem CNPJ.")
            else:
                raise CommandError("Banco aceitou cliente sem CNPJ.")
            numeros = [str(n).zfill(14) for n in range(1000)
                       if not HistoricoCNPJ.objects.filter(cnpj=str(n).zfill(14)).exists()][:2]
            cliente = cadastrar_cliente(cnpj=numeros[0], data_inicio=date(2020, 1, 1),
                razao_social="TESTE TEMPORARIO COM CNPJ", logradouro="Rua Teste", numero="S/N",
                bairro="Centro", cidade="Fortaleza", estado="CE", cep="60000000")
            trocar_cnpj(cliente.pk, numeros[1], date(2021, 1, 1))
            with connection.cursor() as cursor:
                cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
                cursor.execute("SET CONSTRAINTS ALL DEFERRED")
            try:
                with transaction.atomic():
                    cliente.historico_cnpj.filter(data_fim__isnull=True).delete()
                    with connection.cursor() as cursor:
                        cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
            except IntegrityError:
                self.stdout.write("OK: banco impediu remover o último CNPJ atual.")
            else:
                raise CommandError("Banco aceitou remoção do CNPJ atual.")
            assert cliente.historico_cnpj.count() == 2
            transaction.set_rollback(True)
        self.stdout.write("OK: cadastro e troca atômicos. Dados temporários desfeitos.")
