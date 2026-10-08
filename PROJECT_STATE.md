# Estado global — Manutec Clientes

Referência: 28/09/2026. Entrega atual validada por 49 testes SQLite, 11 verificações PostgreSQL 18.4 (incluindo concorrência) e inspeção visual no Edge com banco isolado. Migration 0007 aplicada ao banco instalado em 28/09, após backup com restauração verificada; dados preexistentes preservados. Não é um diário. Retomada operacional: [SESSION_HANDOFF.md](SESSION_HANDOFF.md).

## Objetivo e etapa macro

Centralizar clientes, contatos, administradoras, responsabilidades e destinatários da Manutec, preservando históricos. Contatos de administradora e responsabilidades implementados no painel/API após aprovação das regras pelo usuário. Configuração de destinatários implementada, validada em ambiente isolado e implantada no banco instalado pela migration 0007. Nenhuma migration pendente; envio real de documentos ainda não implementado. Consulte [a especificação](docs/CONTATOS_ADMINISTRADORA.md).

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
| Configuração/revisão/item de destinatários | Três tabelas gerenciadas na migration 0007; painel/API implementados e migration aplicada em 28/09/2026 |

Consultas BrasilAPI/ViaCEP implementadas nos formulários pertinentes. Parcial: identidade de contatos, telefone/e-mail únicos por registro, função livre, histórico editável de contatos e consulta aos anteriores. Pendente: prioridade/alternativo estruturado, apresentação compacta de dois anteriores, frontend próprio e integrações operacionais.

Painel ajustado em 28/09: nomes explicativos dos modos de destinatários, seleção de todas as categorias por contato, ações junto às tabelas e retorno ao ponto do cadastro após salvar vínculo/CNPJ ou adicionar contato. 49 testes SQLite e fluxo Edge isolado aprovados; contratos e regras preservados.

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

Validação da entrega de destinatários: 48 testes SQLite (37 anteriores + 11 novos em test_destinatarios.py), 11 verificações PostgreSQL descartáveis e fluxo visual Edge aprovados. Migration 0007: três novas tabelas e encerrado_em no contato da administradora; aplicada ao banco instalado em 28/09/2026. Legado instalado vazio (0 registros), sem conversão necessária. Backup restaurado e comparado em banco temporário; registros das 18 tabelas preexistentes e concessões de permissões preservados. Três tabelas novas vazias, sete restrições esperadas validadas; check e makemigrations --check limpos. Banco temporário removido.

## Pendências conhecidas — não corrigidas

1. Contato direto combina pessoa e vínculo; mantido, sem PESSOA universal nesta etapa.
2. Início futuro de contato é aceito; `data_fim IS NULL` basta para ser considerado vigente.
3. Endereço obrigatório na criação pode ser esvaziado na edição; decidir se a exigência deve continuar após o cadastro.
4. Contatos, inclusive encerrados, permitem correções/sobrescrita; decidir eventual versionamento sem confundir preservação de registros com auditoria imutável.
5. Módulo de destinatários implementado e implantado pela migration 0007 em 28/09/2026; envio real continua pendente. Desenho e limites registrados em [destinatários de comunicações](docs/DESTINATARIOS_COMUNICACOES.md); implantação concluída. Encerramento de contato da administradora aprovado tanto por condomínio quanto globalmente na empresa. Por contato e condomínio, boletos, notas fiscais, laudos, comunicados e cobranças podem ser selecionados independentemente ou em conjunto; substituída a obrigatoriedade de boleto/nota juntos. Decisões de 27/09 registradas em docs/REGRAS_NEGOCIO.md: seleção de contatos existentes do cliente e/ou administradora, padrões da empresa com atualização automática e acréscimo/substituição por cliente; saída dos destinatários da empresa anterior na troca. Contatos sem e-mail podem ser selecionados, considerando telefone para WhatsApp futuro; contatos encerrados deixam de receber, com histórico preservado. O padrão da administradora é único para todas as categorias. Usar, complementar ou substituir esse padrão é uma escolha por cliente, sem substituição separada por categoria; mudou o padrão, a mudança vale para todas as categorias nos clientes que o utilizam. A seleção das categorias recebidas por cada contato permanece independente. Alterações de destinatários, categorias e configuração do padrão passam a valer imediatamente ao salvar, preservando a configuração anterior no histórico. Agendamento de mudanças fica fora desta etapa. Todos são tratados igualmente como destinatários, sem distinção de principal/copia ou Para/Cópia no cadastro. Essa decisão substitui a classificação anterior; não define a forma técnica de entrega dos futuros envios. Implementação de configuração concluída; envio de documentos não implementado. Contatos de administradora/responsabilidades já validados em PostgreSQL isolado.
6. Principal/alternativo e função estruturada adiados por decisão aprovada; função livre não identifica inequivocamente o síndico.

Limites conhecidos: CNPJ sem verificação de dígitos/situação cadastral; SQL direto não atualiza automaticamente `atualizado_em`; administradora não armazena endereço. Não remover o cliente fictício persistente do teste manual sem pedido.

## Integrações futuras aprovadas como direção

Conta Azul, Auvo e envio de documentos e comunicações por e-mail e WhatsApp, conforme categorias selecionadas por contato e condomínio; n8n no longo prazo; IA somente onde agregar valor. Integrações ao painel e envio ainda não implementados. Sondas manuais de autenticação e consulta Conta Azul disponíveis; autenticação/renovação concluídas segundo o usuário; consulta NFS-e retornou HTTP 500, consulta financeira isolada confirmou HTTP 200 com zero itens em 28/09/2026. Usuário confirmou conta de desenvolvimento vazia e autorizou preparar acesso à conta real da Manutec apenas para consultas; preparação/conexão real concluídas e consultas em produção bem-sucedidas, conforme seção de produção abaixo. A causa do erro fiscal em desenvolvimento e a obtenção dos arquivos continuam pendentes. Prever IDs externos associados ao ID do cliente, idempotência, processamento em segundo plano e falhas/repetições controladas quando essas etapas forem autorizadas.

Definido em 28/09: NFS-e e boletos emitidos dentro do Conta Azul; preferência por extração via API, com arquivos locais como alternativa. E-mail do domínio próprio administrado pelo cPanel. Pesquisa confirmou endpoint público de consulta de NFS-e, cujo contrato não fornece arquivo/link; cobrança retorna URL/status. Download manual e direto pela API de um boleto em produção confirmados em 06/10/2026; arquivos de NFS-e ainda não comprovados. Botão de anexação e SMTP foram recomendados, não implementados. Decisões, propostas e ponto de retomada em [preparação do envio](docs/PREPARACAO_ENVIO_DOCUMENTOS.md). Pendentes: disponibilidade dos arquivos na API, contratos/autenticação, campos e sentido de sincronização, conflitos, dados do provedor SMTP e tecnologia de fila. Manutec para contatos/destinatários, Conta Azul para financeiro e Auvo para serviços é proposta de autoridade de dados, não decisão final de campos. O caminho proposto para o e-mail atual é SMTP; WhatsApp oficial segue como direção futura. Aceitação de envio não prova entrega.

Detalhes estruturais: [arquitetura](docs/ARQUITETURA.md). Regras consolidadas: [regras](docs/REGRAS_NEGOCIO.md). [Auditoria](AUDITORIA_ARQUITETURA.md) preservada como evidência anterior à decisão de não unificar PESSOA agora.

## Preparacao de producao Conta Azul — retomada

Aplicacao de producao cadastrada e callback https://manutecvalvulas.com.br/contaazul/callback/ publicado pelo usuario via cPanel; pagina exibida segundo ele. CLIENT_ID e CLIENT_SECRET preenchidos pelo usuario em .venv/contaazul/producao/credenciais.env (ignorado no Git, ACL usuario/SYSTEM). Sondas agora aceitam --producao para selecionar esse arquivo; sem a opcao, preservam desenvolvimento. Tokens pendentes ficam na pasta do ambiente selecionado. Usuario executou a autorizacao de producao e apresentou mensagem de sucesso, com tokens salvos localmente. Em seguida executou a sonda com --producao --inicio 2026-09-01 --fim 2026-09-15: sucesso, 10 NFS-e na primeira pagina, 10 contas a receber na primeira pagina e link presente na primeira cobranca consultada. Contagens sao da pagina, nao totais do periodo. Nessa primeira consulta, link nao aberto e arquivos ainda nao comprovados; download de boleto foi validado posteriormente, conforme estado atual documentado. Nenhum documento baixado, alterado ou enviado. Evidencia: saida do terminal compartilhada pelo usuario; assistente nao repetiu chamadas nem leu credenciais. 17 testes com rede simulada aprovados; sem banco SQLite/PostgreSQL, migrations, commit ou push. Selecao de arquivo nao comprova empresa: conferir Manutec no navegador antes de autorizar.

### Inspecao limitada do link de cobranca

Verificacao do link autorizada pelo usuario e executada pelo assistente: sonda temporaria .venv/contaazul/producao/verificar_link.py obteve uma cobranca existente no periodo 01–15/09/2026. Destino HTTPS faturas.contaazul.com com fragmento. GET publico separado, sem Authorization/cookies/proxy e sem seguir redirects: HTTP 200, text/html, sem assinatura PDF, zero links .pdf no HTML inicial, dois scripts, zero formularios. Isso confirma pagina HTML acessivel, nao PDF nem ausencia de login apos carregar JavaScript. Nenhuma resposta/URL sensivel persistida; token carregado internamente sem exposicao. Para abrir a pagina, a sonda repetiu os tres GETs financeiros com --abrir e chamou navegador padrao; abertura reportada com sucesso. Total desta investigacao: seis GETs financeiros e um GET publico pela sonda, alem do carregamento normal do navegador. Nenhuma emissao, alteracao, pagamento, envio ou download de arquivo solicitado. Inspecao visual automatizada bloqueada: cua.getState falhou duas vezes com trusted Node process exited unexpectedly; nao houve leitura visual da pagina. Usuario informou que a pagina aberta exibe "Por favor, tente novamente. Nao foi possivel obter os dados" e que o botao retorna ao mesmo erro. Diagnostico adicional autorizado: tres GETs financeiros pelo modo --status da sonda temporaria, sem reabrir link, retornaram status QUITADO e uma unica solicitacao de cobranca na primeira parcela. Portanto a amostra esta quitada; nao ha evidencia de que esse status cause o erro da pagina. Nenhum PDF obtido. Na retomada de 06/10/2026, usuario informou vencimento e valor de uma amostra em aberto. A consulta inicial retornou 401; apos renovacao manual confirmada, a API retornou cinco recebiveis PENDING no dia, com uma unica correspondencia por valor. A parcela possui duas solicitacoes: REGISTRADO e CANCELADO. Foi aberta somente a URL da unica REGISTRADO; usuario confirmou que o boleto apareceu. GET publico previo retornou HTTP 200, text/html, sem assinatura PDF. Assim, o link retornado pela API funcionou para essa amostra. Usuario confirmou depois que a pagina abre outro link para baixar o boleto e que concluiu o download, escolhendo o local no dialogo de salvar. Usuario forneceu o caminho local e o assistente validou o arquivo em leitura: 98.897 bytes, assinatura e marcador de fim de PDF presentes; pypdf em modo estrito leu uma pagina sem criptografia, com dimensoes e fluxo de conteudo validos, zero avisos. PDF estruturalmente valido; dados financeiros e autenticidade bancaria nao inspecionados. Confirmada obtencao manual de PDF pelo fluxo iniciado no link da API. Download direto pela API publica posteriormente comprovado, sem navegador. Novo script backend/contaazul_boleto.py seleciona uma unica conta por data/valor e a unica cobranca REGISTRADO, usa GET /imprimir e salva sem sobrescrever em pasta protegida ignorada pelo Git. 29 testes simulados aprovados; PDF real de uma pagina validado estruturalmente, com texto normalizado igual ao manual. Integracao ao painel e envio pendentes; detalhes e comando em backend/README.md. A causa do erro da amostra quitada permanece indeterminada. Nao criar, reemitir, cancelar ou enviar cobrancas. Documentacao oficial do GET confirma url e status, sem promessa de PDF: https://developers.contaazul.com/docs/charge-apis-openapi/v1. A sonda temporaria anterior fez nove GETs financeiros e um GET publico. A investigacao do link na retomada fez 13 GETs financeiros (um 401 e doze 200), um GET publico e abertura no navegador. O teste posterior do novo script fez mais cinco GETs, incluindo o download direto do PDF; total da retomada: 18 GETs financeiros e um publico, alem do uso do navegador. Nenhuma causa raiz concluida; nao presumir token invalido ou indisponibilidade geral.

NFS-e: referência local de importação de ZIP avaliada em 06/10/2026, somente por leitura. Etapa aprovada e implementada em backend/contaazul_nfse.py: confere pares PDF/XML com a API sem associar automaticamente aos clientes nem gravar no banco. Em 07/10, 45 testes simulados passaram; ZIP real com 139 pares aptos localmente e preservado. Após renovação manual, conferência remota concluída: 136 notas reconhecidas e três pendentes com status CANCELAMENTO_MANUAL, sem mudanças no ZIP/cadastros/documentos. Ajustes necessários e limites em docs/PREPARACAO_ENVIO_DOCUMENTOS.md. A avaliação inicial foi somente documental; ZIP real foi indicado e lido na implementação posterior.

Prévia de associação NFS-e/clientes concluída em 07/10/2026: script local confere ZIP/API e consulta PostgreSQL em READ ONLY, sem persistir vínculos. Relatório protegido fora do Git: uma sugestão, 135 notas sem cadastro (110 CNPJs distintos), três notas não conferidas. Cadastro local tem três clientes; não presumir base de clientes completa. 54 testes simulados passaram. Usuário esclareceu depois que esses clientes são cadastros de teste, possivelmente imprecisos. Alinhamento e lista de faltantes adiados até a base definitiva; não inferir necessidade de importação a partir desse resultado.

Decisão de 07/10/2026: continuar pelo desenho do fluxo cliente → anexos classificados → conferência dos anexos por destinatário → confirmação. Desenho registrado em [preparação do envio](docs/PREPARACAO_ENVIO_DOCUMENTOS.md), já aprovado para protótipo, com implementação pausada a pedido do usuário. Demonstração proposta com cliente/contatos/arquivos fictícios e resultado simulado; sem acesso à base instalada, associação automática, integração de envio ou alterações de regras.

Pausa em 07/10/2026: iniciado somente o roteiro local backend/verificar_prototipo_documentos.cjs. A primeira execução falhou por ausência do HTML; interface ainda não criada. Retomada detalhada em SESSION_HANDOFF.md. Nenhum banco ou envio utilizado nesta etapa.
