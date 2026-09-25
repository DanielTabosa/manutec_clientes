CREATE TABLE clientes (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    razao_social VARCHAR(150) NOT NULL,
    nome_fantasia VARCHAR(150),
    logradouro VARCHAR(150),
    numero VARCHAR(20),
    complemento VARCHAR(100),
    bairro VARCHAR(100),
    cidade VARCHAR(100),
    estado CHAR(2),
    cep VARCHAR(8),
    observacoes TEXT,
    criado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    atualizado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE historico_cnpj (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    cliente_id BIGINT NOT NULL,
    cnpj VARCHAR(14) NOT NULL UNIQUE,
    data_inicio DATE NOT NULL,
    data_fim DATE,

    CONSTRAINT fk_historico_cnpj_cliente
        FOREIGN KEY (cliente_id) REFERENCES clientes(id),

    CONSTRAINT chk_historico_cnpj_datas
        CHECK (data_fim IS NULL OR data_fim >= data_inicio)
);

-- Cada cliente pode ter somente um CNPJ atual.
CREATE UNIQUE INDEX uq_historico_cnpj_atual
    ON historico_cnpj (cliente_id)
    WHERE data_fim IS NULL;

CREATE TABLE contatos (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    cliente_id BIGINT NOT NULL,
    nome VARCHAR(150) NOT NULL,
    funcao VARCHAR(100),
    telefone VARCHAR(20),
    email VARCHAR(150),
    data_inicio DATE NOT NULL,
    data_fim DATE,

    CONSTRAINT fk_contato_cliente
        FOREIGN KEY (cliente_id) REFERENCES clientes(id),

    CONSTRAINT chk_contato_datas
        CHECK (data_fim IS NULL OR data_fim >= data_inicio)
);

CREATE TABLE administradoras (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    cnpj VARCHAR(14) UNIQUE,
    razao_social VARCHAR(150) NOT NULL,
    nome_fantasia VARCHAR(150),
    telefone VARCHAR(20),
    email VARCHAR(150),
    criado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    atualizado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE cliente_administradora (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    cliente_id BIGINT NOT NULL,
    administradora_id BIGINT NOT NULL,
    data_inicio DATE NOT NULL,
    data_fim DATE,

    CONSTRAINT fk_cliente_administradora_cliente
        FOREIGN KEY (cliente_id) REFERENCES clientes(id),

    CONSTRAINT fk_cliente_administradora_administradora
        FOREIGN KEY (administradora_id) REFERENCES administradoras(id),

    CONSTRAINT chk_cliente_administradora_datas
        CHECK (data_fim IS NULL OR data_fim >= data_inicio)
);

-- Cada cliente pode ter somente uma administradora atual.
CREATE UNIQUE INDEX uq_cliente_administradora_atual
    ON cliente_administradora (cliente_id)
    WHERE data_fim IS NULL;

CREATE TABLE contatos_administradora (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    administradora_id BIGINT NOT NULL,
    nome VARCHAR(150) NOT NULL,
    telefone VARCHAR(20),
    email VARCHAR(150),
    criado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_contato_administradora
        FOREIGN KEY (administradora_id) REFERENCES administradoras(id)
);

CREATE TABLE responsabilidades (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    contato_administradora_id BIGINT NOT NULL,
    cliente_id BIGINT NOT NULL,
    funcao VARCHAR(100) NOT NULL,
    data_inicio DATE NOT NULL,
    data_fim DATE,

    CONSTRAINT fk_responsabilidade_contato
        FOREIGN KEY (contato_administradora_id)
        REFERENCES contatos_administradora(id),

    CONSTRAINT fk_responsabilidade_cliente
        FOREIGN KEY (cliente_id) REFERENCES clientes(id),

    CONSTRAINT chk_responsabilidade_datas
        CHECK (data_fim IS NULL OR data_fim >= data_inicio)
);

CREATE TABLE destinatarios_faturamento (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    cliente_id BIGINT NOT NULL,
    nome VARCHAR(150),
    email VARCHAR(150) NOT NULL,
    tipo_destinatario VARCHAR(20) NOT NULL,
    data_inicio DATE NOT NULL,
    data_fim DATE,

    CONSTRAINT fk_destinatario_cliente
        FOREIGN KEY (cliente_id) REFERENCES clientes(id),

    CONSTRAINT chk_tipo_destinatario
        CHECK (tipo_destinatario IN ('principal', 'copia')),

    CONSTRAINT chk_destinatario_datas
        CHECK (data_fim IS NULL OR data_fim >= data_inicio)
);
