# Histórico selecionado — consulta excepcional

Não usar como contexto padrão nem roteiro de retomada. Estado atual em [PROJECT_STATE.md](../PROJECT_STATE.md); próximo passo em [SESSION_HANDOFF.md](../SESSION_HANDOFF.md). Síntese dos checkpoints com valor histórico; o [contexto legado](../contexto_projeto.md) conserva integralmente os registros originais, inclusive instruções superadas.

## 24/09/2026 — base e decisões

- Django + DRF escolhidos após avaliar FastAPI, pela gestão, autenticação, permissões e painel, mantendo possibilidade de integrações.
- ID interno permanente substituiu a ideia de CNPJ como identidade; CNPJ passou a histórico separado. SQL criou oito tabelas e índices parciais para um CNPJ e uma administradora atuais por cliente.
- Usuário confirmou criação do banco `manutec_clientes` e execução do script de relacionamentos no pgAdmin. Dados do script foram revertidos; sequências podem ter avançado. Essa confirmação histórica não é validação atual.
- Backend iniciou com Cliente não gerenciado, sessão/permissões e API. Migrations Django complementaram o banco existente sem recriar tabelas de domínio.
- Histórico de CNPJ veio depois; a regra inicial exclusivamente numérica foi superada por normalização alfanumérica. Cadastro com CNPJ obrigatório e migration 0003 acrescentaram proteção PostgreSQL.
- `.venv` foi criada usando runtime Python do Codex; portabilidade exige recriação com Python instalado. Houve teste manual persistente de cliente fictício; não removê-lo sem pedido.

## 24–25/09/2026 — entregas incrementais

- Consultas CNPJ/CEP e formulários assistidos; contatos diretos com encerramento e preservação dos registros; administradoras e vínculos temporais; consultas de CNPJ padronizadas também na administradora e na troca do cliente.
- Checkpoints registram crescimento de 7 para 11, 16, 18, 23, 28 e 29 testes SQLite aprovados. Também relatam validações PostgreSQL com rollback e verificações no navegador; não são execução desta reorganização. Testes manuais finais de contatos/administradoras ainda aguardavam retorno do usuário.
- Git inicializado em `main`; primeiro commit publicado: `fcc35b3`, repositório `https://github.com/DanielTabosa/manutec_clientes`. Autor aprovado: DanielTabosa. Publicação de código não é backup do PostgreSQL; dados/credenciais permaneceram locais.
- No Windows houve problema de propriedade/setup do executor. Foi usado `git -c safe.directory=C:/dev/manutec-clientes ...` por comando; não houve mudança global de segurança. Esse registro não instrui alterar permissões preventivamente.

## Integrações estudadas — referências históricas

Em 24/09/2026 foram consultadas documentações de [Conta Azul](https://developers.contaazul.com/aboutapis), [Auvo](https://developer.auvo.com.br/quickstart), [Microsoft Graph](https://learn.microsoft.com/en-us/graph/api/user-sendmail?view=graph-rest-1.0) e [WhatsApp oficial](https://www.postman.com/meta/whatsapp-business-platform/documentation/wlk6lh4/whatsapp-cloud-api). Naquela pesquisa foram registradas ausência de webhooks na Conta Azul e limitações para documentos NFS-e; revalidar contratos ao implementar, sem tratar essas observações como fatos atuais. Graph era opção de e-mail; provedor e fila não foram escolhidos. n8n ficou para o longo prazo.

## 26/09/2026 — auditoria e governança

A [auditoria](../AUDITORIA_ARQUITETURA.md) identificou cinco tabelas com fluxos Django e três somente no SQL, além de limitações de vigência, endereço e histórico editável. Foi preservada sem reescrita. Posteriormente, o usuário definiu não criar PESSOA universal agora, usando contatos por administradora e responsabilidades por cliente. Essa decisão resolve a alternativa de identidade levantada na auditoria, sem implementar o módulo.

Instruções permanentes, estado global, retomada, regras e arquitetura foram separados para reduzir releitura. O contexto antigo permanece apenas como evidência; novas sessões seguem AGENTS e handoff. Nenhuma funcionalidade, regra aplicada, migration ou dado PostgreSQL foi alterado nesta reorganização.
