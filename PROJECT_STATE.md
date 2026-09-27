# Estado global — Manutec Clientes

Referência: 27/09/2026. Entrega atual validada por 48 testes SQLite, 11 verificações PostgreSQL 18.4 (incluindo concorrência) e inspeção visual no Edge com banco isolado. Migration 0006 aplicada ao banco instalado, com dados de domínio preservados. Não é um diário. Retomada operacional: [SESSION_HANDOFF.md](SESSION_HANDOFF.md).

## Objetivo e etapa macro

Centralizar clientes, contatos, administradoras, responsabilidades e destinatários da Manutec, preservando históricos. Contatos de administradora e responsabilidades implementados no painel/API após aprovação das regras pelo usuário. Configuração de destinatários implementada e validada em ambiente isolado; implantação da migration 0007 é a próxima etapa. Migration 0006 aplicada; validação PostgreSQL e visual concluída. Banco instalado permanece na 0006; migration 0007 criada e ainda não aplicada. Consulte [a especificação](docs/CONTATOS_ADMINISTRADORA.md).

## Stack e arquitetura

- Python 3.12.14; Django 5.2.17 LTS; DRF 3.16.1; PostgreSQL 18; psycopg 3.3.6; python-dotenv 1.2.3. Dependências: `backend/requirements.lock.txt`.
- Aplicação Django, atualmente concentrada em `clientes`, com painel admin, API e serviços compartilhados para cadastro/CNPJ/vínculos de administradora; frontend próprio ainda não definido.
- Sete modelos `managed=False`: tabelas de domínio criadas pelo SQL. Instalação nova exige schema uma vez e migrations complementares; nunca reaplicar schema em banco existente.
- ID interno permanente; CNPJ separado em histórico. Datas locais America/Fortaleza, `USE_TZ=False`, compatíveis com TIMESTAMP sem fuso.
- Autenticação por sessão e permissões por modelo. Sem exclusão no painel/API. Configuração de desenvolvimento local.
- Direção vigente: **não criar PESSOA universal agora**. Desenho implementado: administradora → contato da administradora → responsabilidade → cliente; implementado no Django.

## Módulos e banco

O schema contém oito tabelas de domínio; sua existência na instalação foi registrada em checkpoints anteriores. Django também utiliza tabelas de autenticação, permissões, sessões, admin e controle de migrations.

| Tabela | Estado no backend |
| --- | --- |
| `clientes` | Cadastro, edição, endereço, pesquisa e permissões |
| `historico_cnpj` | Atual/histórico, troca transacional e obrigatoriedade via migration 0003 |
| `contatos` | Contatos diretos, edição, encerramento, pesquisa e filtro de vigência |
| `administradoras` | Cadastro, edição, pesquisa, telefone/e-mail e CNPJ opcional |
| `cliente_administradora` | Atual/histórico; vincular, trocar, encerrar e retornar |
| `contatos_administradora` | Cadastro/edição, pesquisa, filtro por empresa, painel/API |
| `responsabilidades` | Cadastro/edição/encerramento, períodos, filtros, painel/API e encerramento na troca da empresa |
| `destinatarios_faturamento` | SQL legado preservado; não usado pelo módulo novo |
| Configuração/revisão/item de destinatários | Três tabelas gerenciadas na migration 0007; painel/API implementados, implantação pendente |

Consultas BrasilAPI/ViaCEP implementadas nos formulários pertinentes. Parcial: identidade de contatos, telefone/e-mail únicos por registro, função livre, histórico editável de contatos e consulta aos anteriores. Pendente: prioridade/alternativo estruturado, apresentação compacta de dois anteriores, frontend próprio e integrações operacionais.

## Endpoints principais

Prefixo `/api/v1/`; sem DELETE:

| Rotas | Operações |
| --- | --- |
| `clientes/`, `contatos/`, `administradoras/` | GET lista paginada (25), POST cadastro; pesquisa `search` |
| As mesmas com `{id}/` | GET detalhe, PUT/PATCH edição |
| `clientes/{id}/cnpj/` | GET atual/histórico, POST troca |
| `clientes/{id}/administradora/` | GET atual/histórico, POST vincular/encerrar |
| `contatos/?cliente=ID&vigente=true` | Filtro por cliente e vigência; `false` para encerrados |

Novas rotas `/api/v1/contatos-administradora/` e `/api/v1/responsabilidades/`: GET/POST, detalhe GET/PUT/PATCH, sem DELETE. Filtros e exemplos no README do backend.

Painel `/admin/`; login da API `/api-auth/`. Exemplos e permissões: [backend/README.md](backend/README.md).

## Testes e migrations

- 37 testes anteriores em `backend/clientes/tests.py`: cadastros, históricos, permissões, validações, consultas simuladas e painel. SQLite em memória com `config.test_settings`; não valida triggers/concorrência PostgreSQL. Todos executados e aprovados nesta tarefa.
- `database/testar_relacionamentos.sql`: restrições originais nas oito tabelas; rollback, mas sequências podem avançar. Não força os triggers diferidos e deixa o segundo cliente sem CNPJ antes do rollback; não comprova a obrigatoriedade posterior.
- `verificar_cadastro`: verificação PostgreSQL de cadastro/CNPJ com inserções temporárias e rollback; não é consulta somente leitura.
- Migrations existentes: 0001 Cliente; 0002 HistoricoCNPJ; 0003 triggers PostgreSQL; 0004 Contato; 0005 Administradora/ClienteAdministradora; 0006 ContatoAdministradora/Responsabilidade (aplicada no banco instalado). Modelos não gerenciados dependem do schema externo.

Validação da entrega de destinatários: 48 testes SQLite (37 anteriores + 11 novos em test_destinatarios.py), 11 verificações PostgreSQL descartáveis e fluxo visual Edge aprovados. Migration 0007: três novas tabelas e encerrado_em no contato da administradora; aplicação ao banco instalado pendente. Preservação do destinatário legado foi verificada em banco isolado, sem consultar registros instalados.

## Pendências conhecidas — não corrigidas

1. Contato direto combina pessoa e vínculo; mantido, sem PESSOA universal nesta etapa.
2. Início futuro de contato é aceito; `data_fim IS NULL` basta para ser considerado vigente.
3. Endereço obrigatório na criação pode ser esvaziado na edição; decidir se a exigência deve continuar após o cadastro.
4. Contatos, inclusive encerrados, permitem correções/sobrescrita; decidir eventual versionamento sem confundir preservação de registros com auditoria imutável.
5. Módulo de destinatários implementado e validado isoladamente; aplicar migration 0007 ao banco instalado após verificar legado e preparar implantação. Desenho e limites registrados em [destinatários de comunicações](docs/DESTINATARIOS_COMUNICACOES.md); implantação pendente. Encerramento de contato da administradora aprovado tanto por condomínio quanto globalmente na empresa. Por contato e condomínio, boletos, notas fiscais, laudos, comunicados e cobranças podem ser selecionados independentemente ou em conjunto; substituída a obrigatoriedade de boleto/nota juntos. Decisões de 27/09 registradas em docs/REGRAS_NEGOCIO.md: seleção de contatos existentes do cliente e/ou administradora, padrões da empresa com atualização automática e acréscimo/substituição por cliente; saída dos destinatários da empresa anterior na troca. Contatos sem e-mail podem ser selecionados, considerando telefone para WhatsApp futuro; contatos encerrados deixam de receber, com histórico preservado. O padrão da administradora é único para todas as categorias. Usar, complementar ou substituir esse padrão é uma escolha por cliente, sem substituição separada por categoria; mudou o padrão, a mudança vale para todas as categorias nos clientes que o utilizam. A seleção das categorias recebidas por cada contato permanece independente. Alterações de destinatários, categorias e configuração do padrão passam a valer imediatamente ao salvar, preservando a configuração anterior no histórico. Agendamento de mudanças fica fora desta etapa. Todos são tratados igualmente como destinatários, sem distinção de principal/copia ou Para/Cópia no cadastro. Essa decisão substitui a classificação anterior; não define a forma técnica de entrega dos futuros envios. Implementação de configuração concluída; envio de documentos não implementado. Contatos de administradora/responsabilidades já validados em PostgreSQL isolado.
6. Principal/alternativo e função estruturada adiados por decisão aprovada; função livre não identifica inequivocamente o síndico.

Limites conhecidos: CNPJ sem verificação de dígitos/situação cadastral; SQL direto não atualiza automaticamente `atualizado_em`; administradora não armazena endereço. Não remover o cliente fictício persistente do teste manual sem pedido.

## Integrações futuras aprovadas como direção

Conta Azul, Auvo e envio de documentos e comunicações por e-mail e WhatsApp, conforme categorias selecionadas por contato e condomínio; n8n no longo prazo; IA somente onde agregar valor. Nada disso está implementado. Prever IDs externos associados ao ID do cliente, idempotência, processamento em segundo plano e falhas/repetições controladas quando essas etapas forem autorizadas.

Pendentes: origem dos arquivos, contratos/autenticação, campos e sentido de sincronização, conflitos, provedor de e-mail e tecnologia de fila. Manutec para contatos/destinatários, Conta Azul para financeiro e Auvo para serviços é proposta de autoridade de dados, não decisão final de campos. Microsoft Graph é opção, WhatsApp oficial é a direção. Aceitação de envio não prova entrega.

Detalhes estruturais: [arquitetura](docs/ARQUITETURA.md). Regras consolidadas: [regras](docs/REGRAS_NEGOCIO.md). [Auditoria](AUDITORIA_ARQUITETURA.md) preservada como evidência anterior à decisão de não unificar PESSOA agora.
