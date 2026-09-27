# Manutec Clientes

Sistema Django/DRF e PostgreSQL para clientes, contatos e administradoras.
Inclui históricos, painel administrativo e consultas públicas CNPJ/CEP.

- [Instalação e uso](backend/README.md)
- [Instruções permanentes](AGENTS.md) e [retomada da sessão](SESSION_HANDOFF.md): leitura inicial.
- [Estado global](PROJECT_STATE.md): consultar quando necessário.
- [Arquitetura](docs/ARQUITETURA.md) e [regras de negócio](docs/REGRAS_NEGOCIO.md): consultar conforme a tarefa.
- [Papéis especializados](agents/ORQUESTRADOR.md): responsabilidades sob demanda; não são carregados automaticamente.
- [Auditoria preservada](AUDITORIA_ARQUITETURA.md), [histórico selecionado](docs/HISTORICO.md) e [contexto legado](contexto_projeto.md): evidências históricas, não contexto padrão.

Em uma instalação nova: prepare Python 3.12 e PostgreSQL 18, instale
backend/requirements.lock.txt em um ambiente virtual, crie um banco vazio
e execute database/schema.sql uma única vez. Configure backend/.env a partir
do exemplo, com chave Django aleatória e credenciais locais. Execute migrate,
createsuperuser e runserver conforme o README do backend.

Não execute o schema sobre um banco existente. As migrações complementam
o schema original. Não versionar senhas, .env, dados do banco ou .venv.
Configuração atual destinada a desenvolvimento local.
