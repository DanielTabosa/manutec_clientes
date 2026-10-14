# Retomada — base zerada e contratos cadastrados no sistema

## Plano aprovado em 14/10/2026 (meta: MVP em produção em 27/11/2026)

1. ✅ Preparação no painel, com histórico, retrato e prevenção de reenvio.
2. ✅ Envio por SMTP: `financeiro@manutecvalvulas.com.br` (465 SSL), teste chegou na caixa de entrada. DMARC ausente: recomendação futura.
3. ✅ Conta Azul no fluxo: boleto com escolha da parcela e NFS-e do ZIP; consulta de CNPJ com fontes reserva.
3b. ✅ Interface própria (`backend/painel`), redesenho com a identidade do site (direção D), início focado na base, importação CSV e retaguarda com o mesmo design.
3c. ✅ 14/10: banco instalado zerado (usuários mantidos) e contratos cadastrados no sistema (tipos editáveis, situação ativo/suspenso/inativo, vários por cliente), com "Ver todos" no topo dos quadros do início. Detalhes em `PROJECT_STATE.md`.
4. ⏸ Implantação **interrompida pelo usuário em 14/10**; retomar só quando ele pedir. Pendente decisão dele: hospedagem (VPS recomendado; cPanel só com Python App + PostgreSQL; ou PC do escritório) e acesso (internet ou só escritório). Renovação de token do Conta Azul segue manual.
   - Sugerido antes: envio real de uma preparação completa para um contato com o e-mail do próprio usuário.
5. Homologação com a base definitiva: o usuário vai cadastrar ou importar os dados reais (administradoras → clientes → contatos → contratos).
   - **Aguardando o usuário:** a lista de tipos de contrato da Manutec. Ele pode cadastrá-los em Contratos › Tipos de contrato ou mandar a lista.

## Estado técnico

- Banco instalado sem dados de teste. Backup de antes do reset: `.venv/backups/pre_reset_20261014/` (verificado).
- Migration 0009 aplicada ao banco instalado. Mudanças de modelo exigem 0010+.
- Contratos: modelos em `clientes/contratos_models.py`, telas em `painel/contratos.py`. A conferência com o Conta Azul reaproveita `clientes/contratos.py`.
- `.env` local: SMTP configurado e `DJANGO_CONTAAZUL_AMBIENTE=producao` (somente GET). `config/test_settings.py` isola os testes dessas integrações.
- Validação: 150 testes Django, 15 verificações PostgreSQL descartáveis, scripts Playwright `backend/verificar_*.cjs` (o mais recente: `verificar_contratos.cjs`).
- Servidor local do usuário: aba de terminal "Servidor Manutec" com `manage.py runserver` em `http://127.0.0.1:8000/`.

## Ferramentas

- Node/Playwright: `C:/Users/didit/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe`, com NODE_PATH em `.../dependencies/node/node_modules`; usar o Edge.
- Verificação visual: `verificar_postgresql.py --keep` e `runserver --noreload` com `POSTGRES_DB=<descartável>`. Reiniciar o servidor depois de editar código. Remover o banco ao final.
- Login do usuário no painel: `Daniel_Tabosa` (superusuário); senha definida por ele com `manage.py changepassword`.

## Decisões preservadas

- Foco do sistema (usuário, 14/10): base de dados de clientes robusta; o envio é complemento.
- Contratos (usuário, 14/10): cadastrados aqui, vários por cliente; Conta Azul só como conferência opcional, sem gravar.
- Importação CSV: cliente exige razão social e CNPJ; o resto é opcional e vira pendência. Nada existente é sobrescrito.
- Voltar atrás: voltar para rascunho se nenhum e-mail saiu; cancelar até a operação terminar.
- Não enviar e-mails reais a clientes em testes. Nunca pedir ou ler senhas no chat. Não ler credenciais em `.venv/contaazul`. Sem renovação automática de token. Preservar os backups `pre_0007`, `pre_0008` e `pre_reset_20261014`.
- Git: main/origin com `git -c safe.directory=C:/dev/manutec-clientes`. Commit/push rotineiros autorizados.
