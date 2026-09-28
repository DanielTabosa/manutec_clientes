# Arquitetura vigente

## Estrutura e fronteiras

Aplicação Django com PostgreSQL e API DRF. Hoje o domínio está no app `backend/clientes`; `backend/config` configura URLs, sessão, permissões e ambiente. O painel Django é a interface operacional, complementado por templates e JavaScript de consulta CNPJ/CEP. Não há frontend próprio, fila, automações ou integrações financeiras implementadas.

`models.py` mapeia o domínio; `services.py` concentra cadastro com CNPJ, troca de CNPJ e troca/encerramento de administradora; API e painel reutilizam esses serviços. Contatos usam validações de modelo/serializer e formulários do admin. BrasilAPI/ViaCEP ficam em `consulta.py`; consultas auxiliam o preenchimento, não salvam nem comprovam situação cadastral.

## Entidades e relacionamentos

| Entidade | Relação e estado |
| --- | --- |
| Cliente | Principal; ID interno permanente, cadastro e endereço; implementado |
| HistoricoCNPJ | N registros para um cliente; um atual; implementado |
| Contato | N contatos diretos por cliente; reúne pessoa e vínculo temporal; implementado |
| Administradora | Empresa independente, atende vários clientes; implementada |
| ClienteAdministradora | Relação temporal cliente/empresa; no máximo uma atual por cliente; implementada |
| ContatoAdministradora | N pessoas por administradora; modelo/API/painel implementados |
| Responsabilidade | Liga contato de administradora a cliente, com função e período; modelo/API/painel implementados |
| DestinatarioFaturamento | SQL legado com e-mail e principal/cópia; sem Django. Não representa as regras novas de destinatários |

Direção aprovada em 26/09/2026: **não criar uma entidade universal PESSOA neste momento**. Manter contatos diretos como estão. O módulo implementado usa `ADMINISTRADORA → CONTATO_ADMINISTRADORA → RESPONSABILIDADE → CLIENTE`: uma pessoa cadastrada uma vez dentro da administradora pode atender vários condomínios. A função pertence à responsabilidade. Critérios aprovados e limites de validação em [contatos de administradora](CONTATOS_ADMINISTRADORA.md).

## Persistência e integridade

- `database/schema.sql` cria oito tabelas de domínio, PKs internas, FKs, checks de datas e índices únicos parciais para CNPJ/administradora atuais. Django mapeia sete delas com `managed=False`.
- Migrations 0001/0002/0004/0005/0006 registram modelos não gerenciados; não recriam as tabelas. A 0003 instala triggers diferidos PostgreSQL para exigir CNPJ atual. Instalação nova: schema uma única vez + migrations; detalhes operacionais no [README do backend](../backend/README.md).
- CNPJ do cliente não é duplicado em `clientes`. Trocas usam transação e bloqueio do cliente; encerram o vínculo anterior antes de criar o próximo. Ausência de administradora é ausência de vínculo atual, não empresa fictícia.
- Datas temporais seguem início/fim; `data_fim IS NULL` representa atual na implementação. Limitações de contatos futuros e sobrescrita estão em [PROJECT_STATE.md](../PROJECT_STATE.md), não devem ser corrigidas silenciosamente.
- Exclusões indisponíveis no painel/API; FKs protegem relações. Isso não equivale a um banco imutável ou trilha completa de versões.
- `criado_em`/`atualizado_em` de cliente e administradora são mantidos pelo Django; SQL direto não renova automaticamente a atualização. TIMESTAMP sem fuso, America/Fortaleza, `USE_TZ=False`.

Responsabilidades usam validação de modelo e bloqueio do cliente ao salvar; o admin mantém o bloqueio desde a validação do formulário. API de edição recarrega o registro sob bloqueio. Trocas de administradora usam o mesmo bloqueio e encerram responsabilidades abertas atomicamente, rejeitando datas que invalidariam históricos. Essas regras são da aplicação, não novos triggers: SQL direto e bulk updates podem contorná-las. Migration 0006 é de estado; nenhuma alteração física nas tabelas existentes. Concorrência validada em PostgreSQL 18.4 isolado: duplicidade simultânea e cadastro versus troca nas duas ordens, com bloqueio observado via pg_blocking_pids. Migration 0006 aplicada no banco instalado.

## Acesso e evolução

API autenticada por sessão; permissões view/add/change por modelo e verificações específicas nos vínculos; admin exige acesso de equipe. Configuração destinada a desenvolvimento local; autenticação de integrações e produção dependem de etapas próprias.

Manter Django organizado em módulos à medida que necessário. Integrações aprovadas como direção: Conta Azul, Auvo, e-mail e WhatsApp oficial, n8n depois. Associar IDs externos ao ID permanente, separar adaptadores por fornecedor e compartilhar regras com API/interface; processamento em segundo plano, idempotência e tratamento de falhas serão definidos nessa etapa. Não construir essa infraestrutura antecipadamente. O sistema ainda não obtém nem envia boleto/nota. Origem dos documentos, autoridade de dados por campo, autenticação, filas e provedor de e-mail permanecem por definir.

## Destinatários implementados e implantados

O [módulo de destinatários](DESTINATARIOS_COMUNICACOES.md) usa três modelos gerenciados: configuração, revisão e item. Mantém contatos e tabelas legadas não gerenciadas. A migration 0007 cria as tabelas e adiciona fisicamente encerrado_em a contatos_administradora; foi validada em PostgreSQL isolado e aplicada ao banco instalado em 28/09/2026, após backup com restauração verificada. A tabela destinatarios_faturamento permanece preservada.

Serviços em destinatarios.py centralizam validação, versões e resolução dos padrões; destinatarios_admin.py e destinatarios_api.py os compartilham. Alterações por cliente bloqueiam Cliente e depois Administradora quando necessário; padrão/encerramento global bloqueiam Administradora. Histórico protege configurações anteriores nos fluxos de painel/API, sem reconstrução integral de contatos/entregas passadas. Contatos diretos encerrados e trocas de administradora registram revisões das configurações afetadas. Regras entre tabelas continuam dependendo dos serviços; não se aplicam automaticamente a SQL direto/bulk.
