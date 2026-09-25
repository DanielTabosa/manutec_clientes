# Manutec Clientes

Sistema Django/DRF e PostgreSQL para clientes, contatos e administradoras.
Inclui históricos, painel administrativo e consultas públicas CNPJ/CEP.

- [Instalação e uso](backend/README.md)
- [Contexto do projeto](contexto_projeto.md)

Em uma instalação nova: prepare Python 3.12 e PostgreSQL 18, instale
backend/requirements.lock.txt em um ambiente virtual, crie um banco vazio
e execute database/schema.sql uma única vez. Configure backend/.env a partir
do exemplo, com chave Django aleatória e credenciais locais. Execute migrate,
createsuperuser e runserver conforme o README do backend.

Não execute o schema sobre um banco existente. As migrações complementam
o schema original. Não versionar senhas, .env, dados do banco ou .venv.
Configuração atual destinada a desenvolvimento local.
