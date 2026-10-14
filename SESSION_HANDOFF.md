# Retomada — etapa 1 concluída; próxima: SMTP (etapa 2)

## Plano aprovado em 14/10/2026 (meta: MVP em produção em 27/11/2026)

1. ✅ Preparação de envio no painel, com histórico, retrato na confirmação e prevenção de reenvio. Concluída em 14/10.
2. Envio por SMTP: remetente, registro de aceitação/falha e envio de teste para endereço do próprio usuário. **Depende do usuário:** dados SMTP da conta do domínio no cPanel (servidor, porta, TLS, remetente). As credenciais vão para o `.env`, nunca para o chat.
3. Busca de boleto (`contaazul_boleto.py`) e NFS-e (ZIP) dentro do fluxo, com associação conferida pelo usuário.
4. Implantação: hospedagem a definir pelo usuário, HTTPS, DEBUG desligado, segredos, backup e restauração.
5. Homologação com a base definitiva e treinamento.

Fora do MVP: WhatsApp, Auvo, n8n, IA e frontend separado.

## Estado da etapa 1

- Código: `backend/clientes/preparacao_models.py`, `preparacao.py`, `preparacao_admin.py`, template `admin/clientes/preparacao.html`, `static/clientes/preparacao.{css,js}`, link "Preparar envio de documentos" no cadastro do cliente.
- **Migration 0008 criada e NÃO aplicada ao banco instalado.** Antes de aplicar: backup verificado, como na 0007, e autorização do usuário.
- Regras adotadas como padrão, aguardando confirmação do usuário:
  - Bloqueio do mesmo PDF (SHA-256) ao mesmo e-mail já confirmado; reenvio só com motivo registrado.
  - Um envio por e-mail, mesmo quando há vários contatos com o mesmo endereço.
  - Cancelar e remover preservam registros e arquivos.
  - Detalhes em `docs/PREPARACAO_ENVIO_DOCUMENTOS.md`.
- Validação:
  - 55 testes SQLite.
  - 13 verificações PostgreSQL em banco descartável (já removido).
  - Fluxo Edge `backend/verificar_preparacao_painel.cjs`, com screenshots em `.venv/qa/preparacao2` (ignorado).
- Arquivos PDF em `DJANGO_ARQUIVOS_PRIVADOS` (padrão `backend/privado/`, ignorado pelo Git).

## Ferramentas

- Node/Playwright: `C:/Users/didit/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe`, com NODE_PATH em `.../dependencies/node/node_modules`; usar o Edge (channel msedge).
- Verificação visual do painel: `verificar_postgresql.py --keep` e `runserver` com `POSTGRES_DB=<banco descartável>`; remover o banco ao final.
- `agents/*.md` são papéis documentais e não são executáveis. Não existe `.claude/agents/`.

## Decisões preservadas

- A base de clientes é de teste. Associação/alinhamento só com a base definitiva.
- Categorias independentes. Contato sem e-mail não recebe e-mail. Correções de destinatários ficam na tela própria.
- Não ler credenciais em `.venv/contaazul`. HTTP 401 exige renovação manual. Preservar o backup `.venv/backups/pre_0007_20260928/`.
- Git: main/origin com `git -c safe.directory=C:/dev/manutec-clientes`. Commit/push rotineiros autorizados.
