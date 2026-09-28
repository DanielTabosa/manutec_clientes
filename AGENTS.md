# Instruções permanentes

- Trabalhe incrementalmente; preserve funcionalidades e dados existentes. Não altere regras de negócio sem decisão do usuário.
- Priorize simplicidade, integridade dos dados e manutenção. Não crie abstrações desnecessárias nem implemente funcionalidades futuras antecipadamente.
- Não leia/exponha `.env`, credenciais ou dados sensíveis sem necessidade explícita; nunca os inclua em respostas ou commits.
- Execute testes relacionados às alterações; diferencie validação SQLite de PostgreSQL. Em tarefas só documentais, confira conteúdo, links e diff, sem executar migrations ou gravar no banco.
- Sincronize os documentos afetados após mudanças relevantes. Ao final de cada sessão relevante, substitua o conteúdo de `SESSION_HANDOFF.md`; não acumule histórico nele.
- Ao concluir cada etapa, revisar o diff, executar as validações pertinentes, fazer commit e push para o remoto configurado. Autorização permanente do usuário; não pedir nova confirmação para essas operações rotineiras. Nunca incluir credenciais ou dados sensíveis. Se houver falha ou conflito, preservar o trabalho e informar; não usar force push sem autorização específica.

## Processo proporcional

Preferência expressa do usuário: adequar o processo à complexidade e ao risco da tarefa, inclusive ao usar Superpowers. Fazer leituras pontuais, planos curtos e testes pertinentes; evitar releituras, planejamento extenso e revisões repetidas sem necessidade. Tarefas simples ficam com o agente principal; usar subagentes apenas com benefício real de isolamento ou paralelismo. Preservar as verificações necessárias, a integridade dos dados e a rotina de commit/push.

## Economia de contexto

1. Leia este `AGENTS.md`.
2. Leia `SESSION_HANDOFF.md` no início de uma nova sessão.
3. Identifique a tarefa solicitada.
4. Leia somente código e documentação necessários à tarefa.
5. Consulte `PROJECT_STATE.md` quando precisar do estado global.
6. Consulte `docs/ARQUITETURA.md` ou `docs/REGRAS_NEGOCIO.md` somente quando a tarefa depender deles.
7. Consulte `docs/HISTORICO.md` somente para recuperar explicitamente uma decisão antiga.

Não carregue todo o projeto, documentação ou histórico preventivamente. O código comprova o que está implementado; decisões novas do usuário orientam mudanças, sem torná-las automaticamente implementadas. `contexto_projeto.md` é legado; a auditoria é evidência datada.

## Especialistas sob demanda

Tarefas simples ficam com o agente principal. Em tarefas complexas, consulte `agents/ORQUESTRADOR.md` se precisar coordenar dependências e apenas os papéis pertinentes: `REQUISITOS` para regras/ambiguidades; `BANCO_DADOS` para modelo/integridade; `BACKEND` para Django/API; `FRONTEND` para interface; `QA` para validação. Todos são arquivos `.md` em `agents/`.

Consulte `agents/SEGURANCA.md` somente para autenticação, autorização, credenciais, dados sensíveis, exposição externa, integrações ou segurança; `agents/DEVOPS.md` somente para ambientes, infraestrutura, Docker, deploy, CI/CD ou Git/release quando necessário.

Esses arquivos descrevem responsabilidades e não são carregados automaticamente. Não consulte todos preventivamente. Consulte/delegue somente aos papéis necessários; use subagentes apenas quando houver benefício real de isolamento ou paralelismo, com escopo e resultado definidos.
