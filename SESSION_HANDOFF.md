# Retomada — integração Jiraya, pessoa física e endereços (23/10/2026)

## Onde paramos

Implementado e validado: contrato de leitura para o Jiraya ([docs/INTEGRACAO_JIRAYA.md](docs/INTEGRACAO_JIRAYA.md), aprovado pelo usuário em 23/10), token de serviço e modelo novo (pessoa física com CPF, situação ativo/inativo, vários endereços de atendimento). Detalhes em `PROJECT_STATE.md` (seção de 23/10) e regras em `docs/REGRAS_NEGOCIO.md`.

**Pendente, bloqueante:** aplicar a migration 0010 ao banco instalado. Só com OK explícito do usuário. Até lá, o código do `main` não funciona contra o banco instalado (falta `tipo_pessoa`, `cpf`, `ativo` e `clientes_endereco`); não suba o servidor do usuário com esse código antes de aplicar.

- Backup feito em 23/10: `.venv/backups/pre_0010_20261023/pre_0010.dump` (116.153 bytes; SHA-256 em `verification.json`), restaurado em banco temporário com contagem e md5 do conteúdo idênticos nas 27 tabelas (1.025 registros); temporário removido. Banco instalado em 0009: 360 clientes, todos com algum campo de endereço (viram 360 endereços "Principal").
- Para aplicar: `.venv\Scripts\python.exe backend/manage.py migrate` (a 0010 confere a cópia antes de remover as colunas). Depois, conferir: 360 linhas em `clientes_endereco`, todas principal/ativo; nenhuma coluna de endereço em `clientes`; todos `tipo_pessoa='PJ'` e `ativo`; `makemigrations --check` limpo; contagens das demais tabelas iguais ao `verification.json` (exceto `django_migrations` +1 e `django_content_type` +1).
- Se precisar voltar: `migrate clientes 0009` devolve o endereço principal às colunas (recusa se já houver pessoa física) ou restaurar o dump.

## Para o Jiraya configurar

- URL: `<endereço do manutec-clientes>/api/integracao/v1/` (local: `http://127.0.0.1:8000/api/integracao/v1/`). Produção ainda não definida (fase de implantação pendente).
- Token: gerar e colocar em `backend/.env` como `DJANGO_INTEGRACAO_JIRAYA_TOKEN` (mínimo 32 caracteres); o mesmo valor vai na configuração do Jiraya, enviado como `Authorization: Bearer <token>`. Nunca no Git nem no chat.

## Estado técnico

- Migrations: 0010 nova (não aplicada no instalado). Mudanças de modelo seguintes exigem 0011+.
- Validação: 161 testes Django/SQLite, 56 Conta Azul, 18 verificações PostgreSQL descartáveis (`backend/verificar_postgresql.py`, inclui 0010 na ida/volta). Telas conferidas no navegador em banco descartável.
- Servidor local do usuário: aba "Servidor Manutec" com `manage.py runserver` em `http://127.0.0.1:8000/` (estava parado nesta sessão).

## Depois disso

Fase anterior continua: implantação em produção (hospedagem e acesso pendentes de decisão do usuário) e homologação com a base definitiva. Pendência menor: completude conta "Administradora definida" também para residências.

## Decisões preservadas

- Foco: base de clientes robusta; manutec-clientes é a fonte única de clientes (D-66 do Jiraya). Não mexer em `C:/dev/Jiraya`.
- Não enviar e-mails reais a clientes em testes. Nunca pedir ou ler senhas no chat. Não ler credenciais em `.venv/contaazul`. Preservar os backups `pre_0007`, `pre_0008`, `pre_reset_20261014` e `pre_0010_20261023`.
- Git: main/origin com `git -c safe.directory=C:/dev/manutec-clientes`. Commit/push rotineiros autorizados.
