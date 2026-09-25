-- Execute este arquivo inteiro no Query Tool do banco manutec_clientes.
-- Dados ficticios: todas as insercoes sao desfeitas pelo ROLLBACK final.
-- As sequencias dos IDs podem avancar mesmo com ROLLBACK; isso e normal.
BEGIN;

DO $$
DECLARE
    cliente BIGINT;
    outro_cliente BIGINT;
    administradora BIGINT;
    contato_administradora BIGINT;
    cnpj_teste TEXT;
    cnpj_novo TEXT;
BEGIN
    INSERT INTO clientes (razao_social)
    VALUES ('TESTE - Condominio Boa Vista') RETURNING id INTO cliente;
    INSERT INTO clientes (razao_social)
    VALUES ('TESTE - Condominio Jardim') RETURNING id INTO outro_cliente;

    -- Escolhe identificadores ficticios ainda nao usados neste banco.
    SELECT lpad(n::text, 14, '0') INTO cnpj_teste
    FROM generate_series(0::bigint, 999999::bigint) AS s(n)
    WHERE NOT EXISTS (
        SELECT 1 FROM historico_cnpj WHERE cnpj = lpad(n::text, 14, '0')
    ) LIMIT 1;
    SELECT lpad(n::text, 14, '0') INTO cnpj_novo
    FROM generate_series(0::bigint, 999999::bigint) AS s(n)
    WHERE lpad(n::text, 14, '0') <> cnpj_teste
      AND NOT EXISTS (
          SELECT 1 FROM historico_cnpj WHERE cnpj = lpad(n::text, 14, '0')
      ) LIMIT 1;
    IF cnpj_teste IS NULL OR cnpj_novo IS NULL THEN
        RAISE EXCEPTION 'Nao foi possivel reservar CNPJs ficticios para o teste';
    END IF;

    INSERT INTO historico_cnpj (cliente_id, cnpj, data_inicio)
    VALUES (cliente, cnpj_teste, DATE '2026-01-01');
    INSERT INTO contatos (cliente_id, nome, funcao, data_inicio)
    VALUES (cliente, 'TESTE - Ana', 'Sindica', DATE '2026-01-01');
    INSERT INTO administradoras (razao_social)
    VALUES ('TESTE - Administradora Central') RETURNING id INTO administradora;
    INSERT INTO cliente_administradora (cliente_id, administradora_id, data_inicio)
    VALUES (cliente, administradora, DATE '2026-01-01'),
           (outro_cliente, administradora, DATE '2026-01-01');
    INSERT INTO contatos_administradora (administradora_id, nome, email)
    VALUES (administradora, 'TESTE - Maria', 'maria@example.com')
    RETURNING id INTO contato_administradora;
    INSERT INTO responsabilidades (contato_administradora_id, cliente_id, funcao, data_inicio)
    VALUES (contato_administradora, cliente, 'Contas a pagar', DATE '2026-01-01'),
           (contato_administradora, outro_cliente, 'Contas a pagar', DATE '2026-01-01');
    INSERT INTO destinatarios_faturamento (cliente_id, email, tipo_destinatario, data_inicio)
    VALUES (cliente, 'maria@example.com', 'principal', DATE '2026-01-01'),
           (cliente, 'ana@example.com', 'copia', DATE '2026-01-01');
    RAISE NOTICE 'OK: insercoes nas 8 tabelas e relacionamentos compartilhados';

    BEGIN
        INSERT INTO historico_cnpj (cliente_id, cnpj, data_inicio)
        VALUES (cliente, cnpj_novo, DATE '2026-02-01');
        RAISE EXCEPTION 'FALHOU: aceitou dois CNPJs atuais';
    EXCEPTION WHEN unique_violation THEN
        RAISE NOTICE 'OK: bloqueou dois CNPJs atuais';
    END;
    BEGIN
        INSERT INTO historico_cnpj (cliente_id, cnpj, data_inicio)
        VALUES (outro_cliente, cnpj_teste, DATE '2026-01-01');
        RAISE EXCEPTION 'FALHOU: aceitou o mesmo CNPJ em outro cliente';
    EXCEPTION WHEN unique_violation THEN
        RAISE NOTICE 'OK: bloqueou CNPJ duplicado entre clientes';
    END;
    BEGIN
        INSERT INTO cliente_administradora (cliente_id, administradora_id, data_inicio)
        VALUES (cliente, administradora, DATE '2026-02-01');
        RAISE EXCEPTION 'FALHOU: aceitou duas administradoras atuais';
    EXCEPTION WHEN unique_violation THEN
        RAISE NOTICE 'OK: bloqueou duas administradoras atuais';
    END;
    BEGIN
        INSERT INTO contatos (cliente_id, nome, data_inicio, data_fim)
        VALUES (cliente, 'TESTE - Data invalida', DATE '2026-02-01', DATE '2026-01-01');
        RAISE EXCEPTION 'FALHOU: aceitou data final anterior a inicial';
    EXCEPTION WHEN check_violation THEN
        RAISE NOTICE 'OK: bloqueou datas inconsistentes em contatos';
    END;
    BEGIN
        INSERT INTO destinatarios_faturamento (cliente_id, email, tipo_destinatario, data_inicio)
        VALUES (cliente, 'teste@example.com', 'invalido', DATE '2026-01-01');
        RAISE EXCEPTION 'FALHOU: aceitou tipo de destinatario invalido';
    EXCEPTION WHEN check_violation THEN
        RAISE NOTICE 'OK: bloqueou tipo de destinatario invalido';
    END;
    BEGIN
        DELETE FROM clientes WHERE id = cliente;
        RAISE EXCEPTION 'FALHOU: permitiu excluir cliente com relacionamentos';
    EXCEPTION WHEN foreign_key_violation THEN
        RAISE NOTICE 'OK: chave estrangeira protegeu cliente com relacionamentos';
    END;

    UPDATE historico_cnpj SET data_fim = DATE '2026-01-31'
    WHERE cliente_id = cliente AND data_fim IS NULL;
    INSERT INTO historico_cnpj (cliente_id, cnpj, data_inicio)
    VALUES (cliente, cnpj_novo, DATE '2026-02-01');
    UPDATE cliente_administradora SET data_fim = DATE '2026-01-31'
    WHERE cliente_id = cliente AND data_fim IS NULL;
    INSERT INTO cliente_administradora (cliente_id, administradora_id, data_inicio)
    VALUES (cliente, administradora, DATE '2026-02-01');
    RAISE NOTICE 'OK: novos vinculos atuais apos encerrar os anteriores';
    RAISE NOTICE 'SUCESSO: todos os testes passaram. As insercoes serao desfeitas.';
END;
$$;

ROLLBACK;
