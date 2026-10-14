# Retomada — base de clientes em foco: painel, importação CSV e retaguarda prontos

## Plano aprovado em 14/10/2026 (meta: MVP em produção em 27/11/2026)

1. ✅ Preparação no painel, com histórico, retrato e prevenção de reenvio.
2. ✅ Envio por SMTP: `financeiro@manutecvalvulas.com.br` (465 SSL), teste chegou na caixa de entrada. DMARC ausente: recomendação futura.
3. ✅ Conta Azul no fluxo: busca de boleto com escolha da parcela e NFS-e do ZIP. Teste real aprovado pelo usuário em 14/10. Consulta de CNPJ com fontes reserva.
3b. ✅ Interface própria (`backend/painel`):
   - ✅ 1ª entrega em 14/10 (meta era 21/10): login, início com lista de trabalho, clientes, ficha do cliente, envio de documentos e preparação completa.
   - ✅ 2ª entrega em 14/10 (meta era 31/10): cadastro e edição de cliente com consulta de CNPJ/CEP, troca de CNPJ, administradora, contatos, administradoras e configuração de destinatários. Responsabilidades seguem no admin.
   - ✅ Redesenho em 14/10 com a identidade do site (direção D: azul profundo/azul Manutec/gelo, Inter auto-hospedada, logotipo recriado), mais transições, avisos flutuantes, busca global Ctrl+K, etapas fixas, PDF em painel lateral e tema da retaguarda. Chave de tema (claro / sistema / escuro) na barra superior e no login, lembrada no navegador (`localStorage['tema']`), pedida pelo usuário em 14/10. Se o usuário não gostar, a reserva combinada é a direção B (teal `#0E9384` + âmbar, menu `#0B3B3C`, Plus Jakarta Sans): trocar só os tokens em `painel/static/painel/app.css`.
4. ⏸ Implantação **interrompida pelo usuário em 14/10** antes de qualquer mudança; retomar só quando ele pedir. Pendente decisão dele: hospedagem (VPS recomendado; cPanel só com Python App + PostgreSQL; ou PC do escritório) e acesso (internet ou só escritório). Também a renovação de token do Conta Azul (hoje manual).
   - Antes da implantação, sugerido: envio real de uma preparação completa (boleto + nota) para um contato com o e-mail do próprio usuário, ainda não feito.
5. Homologação com a base definitiva e treinamento. **Agora com importação CSV** (`/importar/`): o usuário pode carregar a base definitiva em lote (administradoras → clientes → contatos); o que faltar aparece como pendência ("Cadastro x/5").
   - Pendente: conferir os contratos ativos com dados reais (token do Conta Azul expirado em 14/10; renovação manual com `contaazul_auth.py --producao`).

## Estado técnico

- Migration 0008 aplicada ao banco instalado (backup `.venv/backups/pre_0008_20261014/`). Mudanças de modelo exigem 0009+.
- `.env` local: SMTP configurado (senha pelo usuário) e `DJANGO_CONTAAZUL_AMBIENTE=producao` (somente GET). `config/test_settings.py` isola os testes dessas integrações.
- Lógica compartilhada entre admin e painel: `clientes/preparacao_fluxo.py` (preparação) e `clientes/destinatarios_fluxo.py` (destinatários). Cadastros do painel em `painel/cadastros.py`.
- Design: tokens em `painel/static/painel/app.css` (direção D); fonte Inter em `painel/static/painel/fontes/`; tema do admin em `painel/static/painel/admin-tema.css` e `backend/templates/admin/base_site.html`.
- Validação: 87 testes Django, 56 testes Conta Azul, 14 verificações PostgreSQL descartáveis, `backend/verificar_interface.cjs` e `backend/verificar_cadastros.cjs` (capturas em `.venv/qa/`).
- Servidor local do usuário: aba de terminal "Servidor Manutec" com `manage.py runserver` (autoreload) em `http://127.0.0.1:8000/`.

## Ferramentas

- Node/Playwright: `C:/Users/didit/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe`, com NODE_PATH em `.../dependencies/node/node_modules`; usar o Edge.
- Verificação visual: `verificar_postgresql.py --keep` e `runserver --noreload` com `POSTGRES_DB=<descartável>`. Reiniciar o servidor depois de editar código. Remover o banco ao final.
- Login do usuário no painel: `Daniel_Tabosa` (superusuário); senha definida por ele com `manage.py changepassword`.

## Decisões preservadas

- A base de clientes é de teste; a base definitiva será preenchida depois. Não enviar e-mails reais a clientes em testes.
- Categorias independentes. Contato sem e-mail não recebe e-mail. Bloqueio de reenvio com motivo e um envio por e-mail (aprovados).
- Foco do sistema (usuário, 14/10): base de dados de clientes robusta; o envio é complemento. Ficha e início priorizam cadastro, administradoras e contratos.
- Importação CSV (usuário, 14/10): cliente exige razão social e CNPJ; o resto é opcional e vira pendência. O cadastro manual continua exigindo o endereço. Nada existente é sobrescrito.
- Voltar atrás (usuário, 14/10): voltar para rascunho se nenhum e-mail saiu; cancelar até a operação terminar (algum e-mail não aceito). Aceitos continuam contando para o bloqueio de reenvio.
- Nunca pedir ou ler senhas no chat. Não ler credenciais em `.venv/contaazul`. Sem renovação automática de token. Preservar os backups `pre_0007` e `pre_0008`.
- Git: main/origin com `git -c safe.directory=C:/dev/manutec-clientes`. Commit/push rotineiros autorizados.
