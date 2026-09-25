from django.db import migrations

SQL = """
CREATE FUNCTION manutec_exigir_cnpj_atual() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE alvo bigint;
BEGIN
    IF TG_TABLE_NAME = 'clientes' THEN
        alvo := NEW.id;
    ELSIF TG_OP = 'DELETE' THEN
        alvo := OLD.cliente_id;
    ELSE
        alvo := NEW.cliente_id;
    END IF;
    IF EXISTS (SELECT 1 FROM clientes WHERE id = alvo)
       AND NOT EXISTS (SELECT 1 FROM historico_cnpj WHERE cliente_id = alvo AND data_fim IS NULL) THEN
        RAISE EXCEPTION 'Cliente deve possuir CNPJ atual' USING ERRCODE = '23514';
    END IF;
    IF TG_TABLE_NAME = 'historico_cnpj' AND TG_OP = 'UPDATE' THEN
        IF OLD.cliente_id <> NEW.cliente_id
           AND EXISTS (SELECT 1 FROM clientes WHERE id = OLD.cliente_id)
           AND NOT EXISTS (SELECT 1 FROM historico_cnpj WHERE cliente_id = OLD.cliente_id AND data_fim IS NULL) THEN
            RAISE EXCEPTION 'Cliente anterior deve possuir CNPJ atual' USING ERRCODE = '23514';
        END IF;
    END IF;
    RETURN NULL;
END;
$$;
CREATE CONSTRAINT TRIGGER cliente_exige_cnpj
AFTER INSERT ON clientes DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION manutec_exigir_cnpj_atual();
CREATE CONSTRAINT TRIGGER historico_preserva_cnpj
AFTER INSERT OR UPDATE OR DELETE ON historico_cnpj DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION manutec_exigir_cnpj_atual();
"""


def criar(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(SQL)


def remover(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute("DROP TRIGGER IF EXISTS cliente_exige_cnpj ON clientes; DROP TRIGGER IF EXISTS historico_preserva_cnpj ON historico_cnpj; DROP FUNCTION IF EXISTS manutec_exigir_cnpj_atual();")


class Migration(migrations.Migration):
    dependencies = [("clientes", "0002_historicocnpj")]
    operations = [migrations.RunPython(criar, remover)]
