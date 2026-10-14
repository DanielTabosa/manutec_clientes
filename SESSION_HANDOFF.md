# Retomada — protótipo de documentos entregue; plano até produção proposto

## Sessão de 14/10/2026

O usuário relatou prazo estourado e pediu para adiantar o projeto, usar as skills /design e /ui-ux-pro-max no frontend (Impeccable quando fizer sentido) e estimar a entrega em produção.

Entregue: `docs/prototipos/documentos/index.html`, um HTML único sem recursos externos e com dados fictícios. Fluxo: cliente → anexos → destinatários → revisão → "Simular preparação". O roteiro `backend/verificar_prototipo_documentos.cjs` passou no Edge, e os screenshots desktop e mobile foram inspecionados (ficam em `.venv/qa/prototipo`, ignorado). Os tokens de design em três camadas estão no `<style>` do protótipo: navy institucional, verde só para confirmação, fontes do sistema, modo escuro e foco visível. A Impeccable não foi usada, porque não compensava num protótipo de uma tela; reavaliar no frontend real. Não houve banco, API, envio nem mudança de regra.

Comando de validação (Node do Codex):
`NODE_PATH=C:/Users/didit/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules C:/Users/didit/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe backend/verificar_prototipo_documentos.cjs` (QA_SCREENSHOT_DIR opcional, sob `.venv`).

## Agents

Os arquivos `agents/*.md` (ORQUESTRADOR, REQUISITOS, BANCO_DADOS, BACKEND, FRONTEND, QA, SEGURANCA, DEVOPS) descrevem papéis e não são executáveis. Não existe `.claude/agents/`. O orquestrador declara não iniciar agentes. A execução é feita pelo agente principal, consultando o papel pertinente. Criar subagentes reais foi proposto, mas não autorizado.

## Plano proposto até produção (aguarda aprovação do usuário)

Estimativa entregue ao usuário: **MVP em produção em 27/11/2026**, ou **06/11/2026** com escopo reduzido (envio por e-mail com anexos manuais, sem buscar no Conta Azul). As datas dependem das entradas do usuário: dados SMTP do cPanel, hospedagem/servidor do Django e base definitiva de clientes.

1. Fluxo real de preparação no painel Django: modelo de lote/envio com histórico, migration, permissões, prevenção de reenvio, testes SQLite e PostgreSQL.
2. Envio por SMTP: remetente, registro de aceitação/falha e envio de teste para endereço do próprio usuário.
3. Busca de boleto (`contaazul_boleto.py`) e NFS-e (ZIP) dentro do fluxo, com associação conferida pelo usuário.
4. Implantação: hospedagem a definir, HTTPS, DEBUG desligado, segredos, backup e restauração.
5. Homologação com a base definitiva e treinamento.

Fora do MVP: WhatsApp, Auvo, n8n, IA e frontend separado (SPA).

## Decisões preservadas

- A base atual de clientes é de teste. Associação/alinhamento só com a base definitiva; não reutilizar a prévia de 07/10.
- Cinco categorias independentes. Contato sem e-mail não recebe e-mail, e o cadastro é mantido. Correções de destinatários ficam na tela própria.
- Envio real, SMTP, associação persistida e integração ao painel não estão implementados nem autorizados.
- Evidências Conta Azul (boleto, NFS-e, prévia) e cuidados com credenciais/backup: ver `PROJECT_STATE.md` e `docs/PREPARACAO_ENVIO_DOCUMENTOS.md`. Não ler credenciais em `.venv/contaazul`. HTTP 401 exige renovação manual.
- Git: branch main, remoto origin; usar `git -c safe.directory=C:/dev/manutec-clientes`.
