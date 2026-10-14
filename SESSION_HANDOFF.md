# Retomada — interface própria completa (2 entregas); próxima: implantação

## Plano aprovado em 14/10/2026 (meta: MVP em produção em 27/11/2026)

1. ✅ Preparação no painel, com histórico, retrato e prevenção de reenvio.
2. ✅ Envio por SMTP: `financeiro@manutecvalvulas.com.br` (465 SSL), teste chegou na caixa de entrada. DMARC ausente: recomendação futura.
3. ✅ Conta Azul no fluxo: busca de boleto com escolha da parcela e NFS-e do ZIP. Teste real aprovado pelo usuário em 14/10. Consulta de CNPJ com fontes reserva.
3b. ✅ Interface própria (`backend/painel`):
   - ✅ 1ª entrega em 14/10 (meta era 21/10): login, início com lista de trabalho, clientes, ficha do cliente, envio de documentos e preparação completa.
   - ✅ 2ª entrega em 14/10 (meta era 31/10): cadastro e edição de cliente com consulta de CNPJ/CEP, troca de CNPJ, administradora, contatos, administradoras e configuração de destinatários. Responsabilidades seguem no admin.
   - Pendente, a pedido do usuário: discutir a paleta de cores (hoje navy + verde de confirmação).
4. Implantação: hospedagem a definir pelo usuário, HTTPS, DEBUG desligado, segredos, backup e restauração. Decidir a renovação de token do Conta Azul em produção (hoje é manual).
5. Homologação com a base definitiva e treinamento.

## Estado técnico

- Migration 0008 aplicada ao banco instalado (backup `.venv/backups/pre_0008_20261014/`). Mudanças de modelo exigem 0009+.
- `.env` local: SMTP configurado (senha pelo usuário) e `DJANGO_CONTAAZUL_AMBIENTE=producao` (somente GET). `config/test_settings.py` isola os testes dessas integrações.
- Lógica compartilhada entre admin e painel: `clientes/preparacao_fluxo.py` (preparação) e `clientes/destinatarios_fluxo.py` (destinatários). Cadastros do painel em `painel/cadastros.py`.
- Design: tokens em `painel/static/painel/app.css`. Revisão Impeccable em contexto único (processo proporcional); pendente uma fonte própria auto-hospedada, que exige autorização para baixar.
- Validação: 75 testes Django, 56 testes Conta Azul, 14 verificações PostgreSQL descartáveis, `backend/verificar_interface.cjs` e `backend/verificar_cadastros.cjs` (capturas em `.venv/qa/`).
- Servidor local do usuário: aba de terminal "Servidor Manutec" com `manage.py runserver` (autoreload) em `http://127.0.0.1:8000/`.

## Ferramentas

- Node/Playwright: `C:/Users/didit/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe`, com NODE_PATH em `.../dependencies/node/node_modules`; usar o Edge.
- Verificação visual: `verificar_postgresql.py --keep` e `runserver --noreload` com `POSTGRES_DB=<descartável>`. Reiniciar o servidor depois de editar código. Remover o banco ao final.
- Login do usuário no painel: `Daniel_Tabosa` (superusuário); senha definida por ele com `manage.py changepassword`.

## Decisões preservadas

- A base de clientes é de teste; a base definitiva será preenchida depois. Não enviar e-mails reais a clientes em testes.
- Categorias independentes. Contato sem e-mail não recebe e-mail. Bloqueio de reenvio com motivo e um envio por e-mail (aprovados).
- Nunca pedir ou ler senhas no chat. Não ler credenciais em `.venv/contaazul`. Sem renovação automática de token. Preservar os backups `pre_0007` e `pre_0008`.
- Git: main/origin com `git -c safe.directory=C:/dev/manutec-clientes`. Commit/push rotineiros autorizados.
