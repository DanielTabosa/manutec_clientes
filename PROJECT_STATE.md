# Estado global — Manutec Clientes

Referência: 28/09/2026. Entrega atual validada por 49 testes SQLite, 11 verificações PostgreSQL 18.4 (incluindo concorrência) e inspeção visual no Edge com banco isolado. Migration 0007 aplicada ao banco instalado em 28/09, após backup com restauração verificada; dados preexistentes preservados. Não é um diário. Retomada operacional: [SESSION_HANDOFF.md](SESSION_HANDOFF.md).

## Objetivo e etapa macro

Centralizar clientes, contatos, administradoras, responsabilidades e destinatários da Manutec, preservando históricos. Contatos de administradora e responsabilidades implementados no painel/API após aprovação das regras pelo usuário. Configuração de destinatários implementada, validada em ambiente isolado e implantada no banco instalado pela migration 0007. Nenhuma migration pendente; envio real de documentos ainda não implementado. Consulte [a especificação](docs/CONTATOS_ADMINISTRADORA.md).

## Stack e arquitetura

- Python 3.12.14; Django 5.2.17 LTS; DRF 3.16.1; PostgreSQL 18; psycopg 3.3.6; python-dotenv 1.2.3. Dependências: `backend/requirements.lock.txt`.
- Aplicação Django com o app `clientes` (domínio, admin de retaguarda, API e serviços) e o app `painel` (interface própria de operação, desde 14/10/2026).
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
| Preparação de envio (preparação/documento/destinatário/item) | Quatro tabelas na migration 0008, painel implementado em 14/10/2026; 0008 aplicada ao banco instalado em 14/10/2026, após backup verificado |

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

Protótipo concluído em 14/10/2026: [docs/prototipos/documentos/index.html](docs/prototipos/documentos/index.html), HTML único sem recursos externos, com cliente/contatos/PDFs fictícios, quatro etapas (cliente → anexos → destinatários → revisão) e ação Simular preparação. Roteiro backend/verificar_prototipo_documentos.cjs aprovado no Edge (Playwright): categorias independentes, contato sem e-mail impedido, confirmação obrigatória, retorno à revisão, remoção, PDF inválido, visualização, mobile 390 px e zero requisições HTTP. Tokens de design em três camadas no próprio arquivo (base para o frontend futuro). Sem banco, API, envio ou alteração de regras.

Etapa 1 do plano até produção (meta MVP 27/11/2026) concluída em 14/10/2026: preparação de envio no painel, com histórico, retrato na confirmação e prevenção de reenvio; nenhum envio real. 55 testes SQLite e 13 verificações PostgreSQL descartáveis aprovados; fluxo Edge inspecionado. Detalhes e regras adotadas em [preparação do envio](docs/PREPARACAO_ENVIO_DOCUMENTOS.md). Próxima etapa: SMTP.

Etapa 2 (SMTP) implementada em 14/10/2026: envio pelo painel com status por destinatário, sem duplicidade e com repetição apenas das falhas. Conta real configurada; teste SMTP aceito pelo servidor em 14/10/2026. 60 testes SQLite e 14 verificações PostgreSQL descartáveis aprovados. Migration 0008 ainda não aplicada ao banco instalado.

Etapa 3 implementada em 14/10/2026: no rascunho de preparação, busca de boleto no Conta Azul (vencimento e valor) e importação de NFS-e do ZIP (somente notas do CNPJ atual do cliente, conferidas como EMITIDA na API). Validada com rede simulada; falta um teste real pelo painel. 64 testes Django, 54 testes Conta Azul e 14 verificações PostgreSQL descartáveis aprovados. Migration 0008 ainda não aplicada ao banco instalado.

**Migration 0008 aplicada ao banco instalado em 14/10/2026**, com autorização do usuário. Antes, backup `pg_dump` em `.venv/backups/pre_0008_20261014/pre_0008.dump` (71.055 bytes; SHA-256 em `verification.json`), restaurado em banco temporário com contagens idênticas nas 21 tabelas (208 registros); temporário removido. Depois de aplicar: quatro tabelas novas vazias, nenhuma tabela de domínio alterada (só `auth_permission` +4, `django_content_type` +4 e `django_migrations` +1, como esperado), 7 constraints `prep_*` mais o índice único parcial de documento, e `makemigrations --check` limpo.

Correções de 14/10/2026 após o primeiro teste real: busca de boleto com escolha da parcela (lista todas as contas em aberto do vencimento, com as prováveis do cliente primeiro) e consulta de CNPJ com fontes reserva (BrasilAPI → Minha Receita → CNPJ.ws). 66 testes Django e 56 Conta Azul aprovados. Detalhes em [preparação do envio](docs/PREPARACAO_ENVIO_DOCUMENTOS.md).

## Interface própria de operação — 14/10/2026

Pedida pelo usuário em 14/10/2026, depois de aprovar o teste real da etapa 3 (boleto da parcela e cadastro com consulta de CNPJ funcionaram). Entregue a primeira parte, prevista para 21/10.

- **App `painel`** (Django server-rendered, sem SPA nem recursos externos), na raiz do site: `/entrar/`, `/` (início), `/clientes/`, `/clientes/<id>/`, `/preparacoes/`, `/preparacoes/<id>/`. O admin continua em `/admin/` como retaguarda, com link no menu para equipe.
- **Telas:**
  - Login próprio.
  - Início como lista de trabalho: envios com pendência e rascunhos em aberto, com links diretos, mais as preparações recentes.
  - Clientes com busca por nome, CNPJ ou cidade, CNPJ e administradora atuais, e "Preparar envio" em cada linha.
  - Ficha do cliente: quem recebe documentos (destinatários efetivos), cadastro, contatos vigentes e preparações.
  - Envio de documentos com filtro por situação.
  - Tela de preparação completa (anexos, Conta Azul, destinatários, confirmação, envio).
- **Lógica única:** `clientes/preparacao_fluxo.py` concentra ações, permissões e contexto da preparação, usados pelo admin e pela interface. Não houve mudança de regra.
- **Permissões:** as mesmas do modelo. Anônimo vai para o login; sem permissão recebe 403. Itens de menu e botões aparecem conforme a permissão.
- **Design:** tokens em três camadas em `painel/static/painel/app.css` (navy institucional, verde só para confirmar e enviar, fontes do sistema), modo claro/escuro automático, foco visível, tabelas que viram cartões no celular, menu em gaveta abaixo de 900 px e proteção contra clique duplo nos formulários.
- **Revisão Impeccable (critique),** feita em contexto único pela preferência de processo proporcional do projeto. O detector não apontou problemas (sem leitura do CSS, que é carregado por tag Django). Corrigido:
  - Cartões de números genéricos trocados por lista de trabalho.
  - Fonte monoespaçada usada como enfeite em e-mails.
  - Seleção, cursor, caixas de marcação e rolagem sem cor da paleta.
  - Pendente: fonte própria auto-hospedada, que depende de autorização para baixar o arquivo da fonte.
- **Segunda entrega (até 31/10):** cadastro e edição de cliente com consulta de CNPJ/CEP, contatos, administradoras e configuração de destinatários na interface própria. Até lá, "Novo cliente", "Editar cadastro" e "Configurar" abrem o admin.

Validação: 70 testes Django/SQLite (4 novos da interface: login e anônimo, permissões, lista/busca/ficha, fluxo completo pela interface). `backend/verificar_interface.cjs` (Playwright/Edge) em banco PostgreSQL descartável com dados fictícios: desktop, celular sem rolagem horizontal e modo escuro, com capturas inspecionadas. O banco foi removido. Nenhuma migration nova.

### Segunda entrega da interface — 14/10/2026

Aprovada pelo usuário depois de ver a primeira; a discussão da paleta de cores ficou para depois, a pedido dele. Entregue antes da meta de 31/10.

- **Clientes:** cadastro novo com consulta automática de CNPJ e CEP (`/clientes/novo/`), edição do cadastro, troca de CNPJ com histórico e vínculo/troca/encerramento de administradora. Contatos do condomínio: novo e edição; o encerramento é pela data de encerramento e retira o contato dos destinatários, com histórico preservado.
- **Administradoras:** lista com busca, ficha (contatos com as categorias do padrão e condomínios administrados), cadastro e edição, contatos novos e editados, e encerramento global de contato com confirmação.
- **Destinatários:** configuração por condomínio e padrão da administradora (`/clientes/<id>/destinatarios/`, `/administradoras/<id>/destinatarios/`), com modo, categorias por contato, "todas", parada local, resultado efetivo, padrão herdado e histórico. No celular, cada contato vira um cartão.
- **Reaproveitamento sem mudança de regra:** mesmos formulários (`clientes/forms.py`), serviços (`cadastrar_cliente`, `trocar_cnpj`, `alterar_administradora`, `encerrar_global`) e scripts de consulta (`cadastro.js`, `cep.js`). A tela de destinatários foi extraída para `clientes/destinatarios_fluxo.py`, usada também pelo admin. Consultas de CNPJ/CEP têm rotas próprias do painel (`/consultas/cnpj/`, `/consultas/cep/`), sem exigir acesso de equipe ao admin.
- Rótulos dos campos de cliente acentuados na interface (o modelo não tem `verbose_name`; nenhuma migration).
- Fora desta entrega: responsabilidades (função de contato da administradora por condomínio) continuam no admin.

Validação: 75 testes Django/SQLite (5 novos de cadastros: cliente/CNPJ/administradora, contatos e encerramento, destinatários com conflito de revisão, administradoras e encerramento global, consultas e permissões), 56 testes Conta Azul e detector Impeccable sem apontamentos. `backend/verificar_cadastros.cjs` (Playwright/Edge) em banco descartável: novo cliente com consulta real de CNPJ público, erros de validação, contato, destinatários, administradoras; celular sem rolagem horizontal. O banco foi removido.

### Redesenho com a identidade do site — 14/10/2026

O usuário pediu crítica de design (`/design:design-critique`) e uma interface moderna e fluida, porque não gostava da paleta anterior. Ele indicou o site manutecvalvulas.com.br como referência, com a opção B (teal) como reserva, e autorizou todas as sugestões, incluindo baixar a fonte.

- **Direção D, identidade Manutec:** cores extraídas do site. Azul profundo `#0E2A5C` no menu, azul Manutec `#1F5FBF` nas ações, azul claro `#5E9CE9` no modo escuro, fundo gelo `#F1F3F5`, verde do site `#23A455` só para estados concluídos (`#1B8A47` nos botões, por contraste). Logotipo recriado em HTML/SVG (MANU + válvula + EC, VÁLVULAS, faixa preta SOLUÇÕES HIDRÁULICAS), sem copiar imagem. Fonte Inter variável auto-hospedada (`painel/static/painel/fontes/`, licença OFL incluída).
- **Fluidez:**
  - Transições entre páginas (View Transitions no Edge/Chrome).
  - Avisos flutuantes que fecham sozinhos (erros ficam).
  - Busca global na barra superior (`/busca/`, Ctrl+K ou "/") em clientes, administradoras e preparações, respeitando permissões.
  - Barra de etapas fixa na preparação, com destaque da etapa visível, e botões "Continuar".
  - PDF em painel lateral: a rota de documento permite enquadramento só no próprio sistema (`X-Frame-Options: SAMEORIGIN`).
  - Arrastar arquivos, carregamento nos botões e caixas de marcação redesenhadas.
- **Retaguarda (Django admin)** com a mesma identidade: `backend/templates/admin/base_site.html` e `painel/static/painel/admin-tema.css`, com link "Voltar para o sistema". `TEMPLATES.DIRS` passou a incluir `backend/templates`.
- **Sem mudança de regra,** banco ou migration.

Validação: 76 testes Django (novo: busca global com permissões), 56 Conta Azul, detector Impeccable sem apontamentos e `manage.py check` limpo. Playwright/Edge em banco descartável: `verificar_interface.cjs` e `verificar_cadastros.cjs` aprovados, mais capturas da janela visível (preparação no topo e rolada, painel de PDF, busca, admin, modo escuro, celular). O banco foi removido.

### Ficha do cliente com foco no cadastro e regra de voltar atrás — 14/10/2026

O usuário reforçou que o foco do sistema é uma **base de dados de clientes robusta**; o envio é um complemento. A ficha do cliente foi invertida: à esquerda, o cadastro completo (indicador de completude: CNPJ, endereço, administradora, contato com e-mail e destinatários; dados em duas colunas; CNPJs e administradoras anteriores; observações), os contatos do condomínio em tabela (função, e-mail, telefone, início e contatos encerrados no histórico) e os responsáveis na administradora. À direita, quem recebe documentos e o envio. "Editar cadastro" passou a ser a ação principal.

Regra nova de voltar atrás (voltar para rascunho ou cancelar até o fim da operação) em [preparação do envio](docs/PREPARACAO_ENVIO_DOCUMENTOS.md). 80 testes Django aprovados e verificação no Edge (desktop e celular) em banco descartável.

### Painel da base de clientes, importação CSV e retaguarda — 14/10/2026

Pedido do usuário: o início deve focar em clientes, administradoras e contratos ativos, com o envio depois. Ele quer importar cadastros em lote por CSV, sem cadastrar um a um, e a retaguarda com o mesmo design do sistema.

- **Início:**
  - Clientes cadastrados com a completude agregada (% completos e cinco pendências clicáveis, que filtram a lista de clientes) e os cadastrados recentemente com nota "Cadastro x/5".
  - Administradoras (total, condomínios vinculados, sem contato com e-mail e as principais).
  - Contratos ativos do Conta Azul.
  - Por último, o envio de documentos.
- **Lista de clientes:** filtro por pendência e coluna "Cadastro x/5". Completude em lote em `painel/completude.py`, por consultas agregadas. "Quem recebe documentos" é aproximado em lote (revisão mais recente do condomínio ou do padrão da administradora); a ficha usa o cálculo exato.
- **Contratos ativos** (`clientes/contratos.py`):
  - `GET /v1/contratos` somente leitura, status ATIVO, até 10 páginas de 50, cache de 15 minutos (erros por 2 minutos) e botão de atualizar.
  - Cruzamento com a base pelo CNPJ atual e, sem documento, pelo nome normalizado (único). Contratos sem cadastro têm botão "Cadastrar" com razão social e CNPJ pré-preenchidos.
  - Autorização expirada vira um aviso, sem travar a tela.
  - **Conferido com dados reais em 14/10, depois que o usuário renovou o token:** o contrato traz só `cliente.id` e `cliente.nome`, então o CNPJ vem de `GET /v1/pessoas` (585 pessoas, com documento, e-mail e telefone), no mesmo cache. Resultado: 102 contratos ativos, todos com CNPJ; com a base de teste (3 clientes), 1 cruzado por CNPJ e 101 sem cadastro, cada um com "Cadastrar" pré-preenchido com nome e CNPJ. A consulta leva cerca de 11 s sem cache, então o quadro carrega em segundo plano (`/contratos/resumo/`) e o início abre na hora.
- **Importação CSV** (`painel/importacao.py`, telas em `painel/importar.py`, menu "Importar CSV"):
  - Tipos: clientes, contatos dos condomínios, administradoras e contatos das administradoras. Cada tipo exige a permissão de adicionar correspondente.
  - Lê UTF-8 ou Windows-1252, com separador ; , ou tabulação; até 2 MB e 5.000 linhas.
  - Reconhece colunas por sinônimos, sem acento nem caixa (ex.: "Condomínio", "Município"), e a prévia permite reassociar as colunas.
  - A prévia não grava nada. Ela mostra por linha Novo, Já existe (ignorado, nada é sobrescrito) ou Erro, com as observações.
  - A gravação refaz a análise e usa uma transação por linha. O resultado lista o que não entrou.
  - **Regras:**
    - Cliente exige razão social e CNPJ (o banco já exige CNPJ), e o CNPJ com zeros à esquerda cortados pelo Excel é completado.
    - Endereço e demais campos são opcionais na importação e viram pendência; o cadastro manual continua exigindo o endereço (`cadastrar_cliente(exigir_endereco=False)` só na importação).
    - CEP e UF inválidos são ignorados com aviso.
    - A coluna Administradora vincula o cliente, e a administradora é criada se não existir.
    - Contato localiza o condomínio pelo CNPJ atual ou pelo nome exato; e-mail inválido é descartado com aviso.
    - São ignorados contato repetido vigente (mesmo nome no condomínio) e administradora repetida (CNPJ ou razão social).
  - Há um modelo CSV para baixar em cada tipo.
- **Retaguarda (Django admin)** com o design do sistema: logotipo, menu lateral em azul profundo com item ativo destacado, cartões arredondados, tabelas, campos e botões iguais aos da interface, modo escuro e link "Voltar para o sistema". Só CSS e o `base_site.html`.

Validação: 87 testes Django (7 novos: importação de clientes com pendências e administradora, leitura cp1252 e reconhecimento de colunas, reassociação, contatos e contatos de administradora, permissões, modelo e descarte, painel e contratos com simulação e 401), 56 Conta Azul, 14 verificações PostgreSQL descartáveis e detector sem apontamentos. `backend/verificar_importacao.cjs` (Playwright/Edge, banco descartável): início, importação ponta a ponta (2 novos, 1 existente, 1 erro), filtro de pendência, retaguarda, modo escuro e celular. O banco foi removido.

