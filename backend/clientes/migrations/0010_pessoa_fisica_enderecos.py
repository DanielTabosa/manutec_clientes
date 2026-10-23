"""Pessoa física com CPF, situação ativo/inativo e vários endereços de atendimento por cliente.

O endereço único de `clientes` vira o endereço principal ("Principal") em `clientes_endereco`, com a
contagem conferida antes de remover as colunas antigas. Decisões do usuário em 23/10/2026."""
import django.core.validators
import django.db.models.deletion
from django.db import migrations, models

CAMPOS = ("cep", "logradouro", "numero", "complemento", "bairro", "cidade", "estado")

TRIGGERS = """
CREATE OR REPLACE FUNCTION manutec_exigir_cnpj_atual() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE alvo bigint; tipo varchar(2);
BEGIN
    IF TG_TABLE_NAME = 'clientes' THEN
        alvo := NEW.id;
    ELSIF TG_OP = 'DELETE' THEN
        alvo := OLD.cliente_id;
    ELSE
        alvo := NEW.cliente_id;
    END IF;
    SELECT tipo_pessoa INTO tipo FROM clientes WHERE id = alvo;
    IF tipo = 'PJ' AND NOT EXISTS (SELECT 1 FROM historico_cnpj WHERE cliente_id = alvo AND data_fim IS NULL) THEN
        RAISE EXCEPTION 'Cliente deve possuir CNPJ atual' USING ERRCODE = '23514';
    END IF;
    IF tipo = 'PF' AND EXISTS (SELECT 1 FROM historico_cnpj WHERE cliente_id = alvo) THEN
        RAISE EXCEPTION 'Cliente pessoa fisica nao possui CNPJ' USING ERRCODE = '23514';
    END IF;
    IF TG_TABLE_NAME = 'historico_cnpj' AND TG_OP = 'UPDATE' THEN
        IF OLD.cliente_id <> NEW.cliente_id
           AND EXISTS (SELECT 1 FROM clientes WHERE id = OLD.cliente_id AND tipo_pessoa = 'PJ')
           AND NOT EXISTS (SELECT 1 FROM historico_cnpj WHERE cliente_id = OLD.cliente_id AND data_fim IS NULL) THEN
            RAISE EXCEPTION 'Cliente anterior deve possuir CNPJ atual' USING ERRCODE = '23514';
        END IF;
    END IF;
    RETURN NULL;
END;
$$;
CREATE FUNCTION manutec_tipo_pessoa_imutavel() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.tipo_pessoa <> OLD.tipo_pessoa THEN
        RAISE EXCEPTION 'O tipo de pessoa do cliente nao pode ser alterado' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER cliente_tipo_pessoa_imutavel BEFORE UPDATE OF tipo_pessoa ON clientes
FOR EACH ROW EXECUTE FUNCTION manutec_tipo_pessoa_imutavel();
"""


def _pg(schema_editor):
    return schema_editor.connection.vendor == "postgresql"


def adicionar_colunas(apps, schema_editor):
    if _pg(schema_editor):
        schema_editor.execute("""
            ALTER TABLE clientes
                ADD COLUMN tipo_pessoa varchar(2) NOT NULL DEFAULT 'PJ',
                ADD COLUMN cpf varchar(11) NULL,
                ADD COLUMN ativo boolean NOT NULL DEFAULT true,
                ADD CONSTRAINT chk_clientes_tipo_pessoa CHECK (tipo_pessoa IN ('PJ', 'PF')),
                ADD CONSTRAINT chk_clientes_cpf CHECK ((tipo_pessoa = 'PJ' AND cpf IS NULL)
                                                       OR (tipo_pessoa = 'PF' AND cpf IS NOT NULL AND cpf ~ '^[0-9]{11}$')),
                ADD CONSTRAINT uq_clientes_cpf UNIQUE (cpf)""")


def remover_colunas(apps, schema_editor):
    if _pg(schema_editor):
        schema_editor.execute("ALTER TABLE clientes DROP COLUMN tipo_pessoa, DROP COLUMN cpf, DROP COLUMN ativo")


def copiar_enderecos(apps, schema_editor):
    if not _pg(schema_editor):
        return
    preenchido = " OR ".join(f"NULLIF(btrim({c}), '') IS NOT NULL" for c in CAMPOS)
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(f"SELECT count(*) FROM clientes WHERE {preenchido}")
        esperados = cursor.fetchone()[0]
        cursor.execute(f"""
            INSERT INTO clientes_endereco (cliente_id, descricao, principal, ativo, {", ".join(CAMPOS)}, criado_em, atualizado_em)
            SELECT id, 'Principal', true, true, {", ".join(CAMPOS)}, criado_em, atualizado_em
            FROM clientes WHERE {preenchido}""")
        copiados = cursor.rowcount
        cursor.execute(f"""
            SELECT count(*) FROM clientes c JOIN clientes_endereco e ON e.cliente_id = c.id
            WHERE {" AND ".join(f"c.{x} IS NOT DISTINCT FROM e.{x}" for x in CAMPOS)}""")
        iguais = cursor.fetchone()[0]
    if not (esperados == copiados == iguais):
        raise RuntimeError(f"Cópia de endereços divergente: {esperados} esperados, {copiados} copiados, {iguais} iguais.")


def devolver_enderecos(apps, schema_editor):
    if not _pg(schema_editor):
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM clientes WHERE tipo_pessoa = 'PF'")
        if cursor.fetchone()[0]:
            raise RuntimeError("Há clientes pessoa física: a reversão perderia o CPF. Reverta manualmente.")
        cursor.execute(f"""
            UPDATE clientes c SET {", ".join(f"{x} = e.{x}" for x in CAMPOS)}
            FROM clientes_endereco e WHERE e.cliente_id = c.id AND e.principal""")


def remover_colunas_endereco(apps, schema_editor):
    if _pg(schema_editor):
        schema_editor.execute("ALTER TABLE clientes " + ", ".join(f"DROP COLUMN {c}" for c in CAMPOS))


def recriar_colunas_endereco(apps, schema_editor):
    if _pg(schema_editor):
        schema_editor.execute("""
            ALTER TABLE clientes ADD COLUMN logradouro varchar(150), ADD COLUMN numero varchar(20),
                ADD COLUMN complemento varchar(100), ADD COLUMN bairro varchar(100), ADD COLUMN cidade varchar(100),
                ADD COLUMN estado char(2), ADD COLUMN cep varchar(8)""")


def criar_triggers(apps, schema_editor):
    if _pg(schema_editor):
        schema_editor.execute(TRIGGERS)


def remover_triggers(apps, schema_editor):
    if _pg(schema_editor):
        from importlib import import_module
        original = import_module("clientes.migrations.0003_cnpj_obrigatorio").SQL
        funcao = original[:original.index("CREATE CONSTRAINT TRIGGER")].replace("CREATE FUNCTION", "CREATE OR REPLACE FUNCTION", 1)
        schema_editor.execute("DROP TRIGGER IF EXISTS cliente_tipo_pessoa_imutavel ON clientes; "
                              "DROP FUNCTION IF EXISTS manutec_tipo_pessoa_imutavel();" + funcao)


class Migration(migrations.Migration):

    dependencies = [
        ("clientes", "0009_contratos"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[migrations.RunPython(adicionar_colunas, remover_colunas)],
            state_operations=[
                migrations.AddField(model_name="cliente", name="tipo_pessoa", field=models.CharField(
                    choices=[("PJ", "Pessoa jurídica (CNPJ)"), ("PF", "Pessoa física (CPF)")], default="PJ",
                    max_length=2, verbose_name="tipo de pessoa")),
                migrations.AddField(model_name="cliente", name="cpf", field=models.CharField(
                    blank=True, max_length=11, null=True, unique=True, verbose_name="CPF",
                    validators=[django.core.validators.RegexValidator("\\A[0-9]{11}\\Z", "Informe o CPF com 11 números.")])),
                migrations.AddField(model_name="cliente", name="ativo", field=models.BooleanField(default=True, verbose_name="ativo")),
            ],
        ),
        migrations.CreateModel(
            name="Endereco",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("descricao", models.CharField(default="Principal", help_text="Ex.: Principal, Matriz, Filial Aldeota.", max_length=60, verbose_name="descrição")),
                ("principal", models.BooleanField(default=False, verbose_name="principal")),
                ("ativo", models.BooleanField(default=True, help_text="Endereço que deixou de ser atendido fica inativo; nunca é apagado.", verbose_name="ativo")),
                ("cep", models.CharField(blank=True, max_length=8, null=True, validators=[django.core.validators.RegexValidator("\\A[0-9]{8}\\Z", "Informe o CEP com exatamente 8 numeros.")], verbose_name="CEP")),
                ("logradouro", models.CharField(blank=True, max_length=150, null=True, verbose_name="logradouro")),
                ("numero", models.CharField(blank=True, max_length=20, null=True, verbose_name="número")),
                ("complemento", models.CharField(blank=True, max_length=100, null=True, verbose_name="complemento")),
                ("bairro", models.CharField(blank=True, max_length=100, null=True, verbose_name="bairro")),
                ("cidade", models.CharField(blank=True, max_length=100, null=True, verbose_name="cidade")),
                ("estado", models.CharField(blank=True, choices=[(uf, uf) for uf in "AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO".split()], max_length=2, null=True, verbose_name="estado (UF)")),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
                ("cliente", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="enderecos", to="clientes.cliente")),
            ],
            options={
                "verbose_name": "endereço de atendimento",
                "verbose_name_plural": "endereços de atendimento",
                "ordering": ["-principal", "-ativo", "descricao", "id"],
                "default_permissions": (),
                "constraints": [
                    models.UniqueConstraint(condition=models.Q(("principal", True)), fields=("cliente",), name="uq_endereco_principal"),
                    models.CheckConstraint(condition=models.Q(("principal", False), ("ativo", True), _connector="OR"), name="chk_endereco_principal_ativo"),
                ],
            },
        ),
        migrations.RunPython(copiar_enderecos, devolver_enderecos),
        migrations.SeparateDatabaseAndState(
            database_operations=[migrations.RunPython(remover_colunas_endereco, recriar_colunas_endereco)],
            state_operations=[migrations.RemoveField(model_name="cliente", name=c) for c in CAMPOS],
        ),
        migrations.RunPython(criar_triggers, remover_triggers),
    ]
