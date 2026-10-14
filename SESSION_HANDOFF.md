# Retomada — etapa 2 (SMTP) implementada; falta teste real com a conta do cPanel

## Plano aprovado em 14/10/2026 (meta: MVP em produção em 27/11/2026)

1. ✅ Preparação no painel, com histórico, retrato na confirmação e prevenção de reenvio. Regras aprovadas pelo usuário em 14/10.
2. 🟡 Envio por SMTP: implementado e validado com servidor simulado. **Pendente:** o usuário coletar os dados do cPanel, preencher `backend/.env` (variáveis `DJANGO_EMAIL_*`, modelo em `.env.example`) e rodar `python backend/manage.py testar_smtp --para <endereço dele>`. Orientação de onde encontrar os dados no cPanel foi dada em 14/10.
3. Busca de boleto (`contaazul_boleto.py`) e NFS-e (ZIP) dentro do fluxo, com associação conferida pelo usuário.
4. Implantação: hospedagem a definir pelo usuário, HTTPS, DEBUG desligado, segredos, backup e restauração.
5. Homologação com a base definitiva e treinamento.

## Estado técnico

- **Migration 0008** (preparação + campos de envio) **NÃO aplicada ao banco instalado.** Antes de aplicar: backup verificado e autorização do usuário.
- Envio:
  - Síncrono, um e-mail por destinatário.
  - Status por destinatário: pendente, aceito, falha ou indeterminado.
  - Marcação "em envio" antes da saída, para evitar duplicidade; só as falhas são repetidas.
  - Indeterminado só é repetido com confirmação explícita.
  - Permissão `enviar_preparacaoenvio`.
- Validação:
  - 60 testes SQLite.
  - 14 verificações PostgreSQL em banco descartável (já removido).
  - Fluxo Edge `backend/verificar_preparacao_painel.cjs`, com screenshots em `.venv/qa/envio`.
- Resto de QA: um `.log` de e-mail fictício em `.venv/qa/emails` (ignorado pelo Git). A remoção foi barrada pela checagem de segurança; o usuário pode apagar.
- Documentação: `docs/PREPARACAO_ENVIO_DOCUMENTOS.md` (seções de 14/10), `backend/README.md` e `PROJECT_STATE.md`.

## Ferramentas

- Node/Playwright: `C:/Users/didit/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe`, com NODE_PATH em `.../dependencies/node/node_modules`; usar o Edge.
- Verificação visual: `verificar_postgresql.py --keep` e `runserver` com `POSTGRES_DB=<banco descartável>` e `DJANGO_EMAIL_BACKEND=django.core.mail.backends.filebased.EmailBackend`; remover o banco ao final.
- `agents/*.md` são papéis documentais, não executáveis.

## Decisões preservadas

- A base de clientes é de teste. Associação/alinhamento só com a base definitiva.
- Categorias independentes. Contato sem e-mail não recebe e-mail. Correções de destinatários ficam na tela própria.
- Nunca pedir ou ler senhas no chat. Não ler credenciais em `.venv/contaazul`. Preservar o backup `.venv/backups/pre_0007_20260928/`.
- Git: main/origin com `git -c safe.directory=C:/dev/manutec-clientes`. Commit/push rotineiros autorizados.
