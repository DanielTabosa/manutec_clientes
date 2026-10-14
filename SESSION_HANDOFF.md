# Retomada — etapa 3 implementada; falta teste real pelo painel

## Plano aprovado em 14/10/2026 (meta: MVP em produção em 27/11/2026)

1. ✅ Preparação no painel, com histórico, retrato e prevenção de reenvio. Regras aprovadas.
2. ✅ Envio por SMTP: conta `financeiro@manutecvalvulas.com.br` (465 SSL) no `.env`. Teste chegou na caixa de entrada (confirmado pelo cPanel em 14/10). DMARC ausente: recomendação futura.
3. 🟡 Conta Azul no fluxo: implementada e validada com rede simulada. **Falta o teste real pelo painel**, com token válido e um boleto e um ZIP escolhidos pelo usuário. Exige aplicar a migration 0008 ou usar um banco descartável.
4. Implantação: hospedagem a definir pelo usuário, HTTPS, DEBUG desligado, segredos, backup e restauração. Decidir a renovação de token do Conta Azul em produção (hoje é manual).
5. Homologação com a base definitiva e treinamento.

## Estado técnico

- **Migration 0008** (preparação, envio e origem) **NÃO aplicada ao banco instalado.** Antes de aplicar: backup verificado e autorização do usuário. Foi refeita três vezes nesta sessão, sempre antes de qualquer aplicação permanente.
- `.env` local: SMTP configurado (senha pelo usuário) e `DJANGO_CONTAAZUL_AMBIENTE=producao` (somente GET).
- Conta Azul no painel: `contaazul_boleto.baixar_pdf` e `contaazul_nfse.ler_zip(..., com_pdf=True)` reaproveitados. As notas são filtradas pelo CNPJ atual do cliente e conferidas na API. HTTP 401 exige renovação manual.
- Validação: 64 testes Django/SQLite, 54 testes Conta Azul, 14 verificações PostgreSQL descartáveis (banco removido) e telas no Edge em `.venv/qa/etapa3`.
- Documentação: `docs/PREPARACAO_ENVIO_DOCUMENTOS.md` (seções de 14/10), `backend/README.md` e `PROJECT_STATE.md`.

## Ferramentas

- Node/Playwright: `C:/Users/didit/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe`, com NODE_PATH em `.../dependencies/node/node_modules`; usar o Edge.
- Verificação visual: `verificar_postgresql.py --keep` e `runserver` com `POSTGRES_DB=<descartável>`; remover o banco ao final.
- `agents/*.md` são papéis documentais, não executáveis.

## Decisões preservadas

- A base de clientes é de teste. CNPJs imprecisos impedem a importação de NFS-e, como esperado, até a base definitiva.
- Categorias independentes. Contato sem e-mail não recebe e-mail. Correções de destinatários ficam na tela própria.
- Nunca pedir ou ler senhas no chat. Não ler credenciais em `.venv/contaazul`. Sem renovação automática de token. Preservar o backup `.venv/backups/pre_0007_20260928/`.
- Git: main/origin com `git -c safe.directory=C:/dev/manutec-clientes`. Commit/push rotineiros autorizados.
