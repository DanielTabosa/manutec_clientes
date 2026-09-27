> **CHECKPOINT LEGADO — NÃO USAR COMO CONTEXTO PADRÃO.**
> Para novas sessões, leia [AGENTS.md](AGENTS.md) e [SESSION_HANDOFF.md](SESSION_HANDOFF.md).
> Consulte [PROJECT_STATE.md](PROJECT_STATE.md) quando precisar do estado global.
> O conteúdo original abaixo foi preservado integralmente como histórico; suas instruções de retomada e pendências antigas podem estar superadas.

# Projeto Manutec Clientes

## 1. Objetivo do projeto

Criar uma aplicação web para centralizar e organizar os dados dos
clientes da Manutec Válvulas.

O sistema deverá permitir cadastrar, editar e pesquisar clientes;
consultar contatos, administradoras, responsáveis financeiros e
destinatários de faturamento; manter históricos importantes; e
futuramente permitir automações e recursos de Inteligência Artificial
(IA).

A primeira prioridade é:

**Banco de dados → Backend → Interface de Programação de Aplicações
(API) → Frontend**

IA e automações serão adicionadas posteriormente somente onde trouxerem
valor real.

## 2. Tecnologias definidas

-   PostgreSQL 18 --- banco de dados relacional
-   SQL --- definição e manipulação do banco
-   Python 3.12.14 + Django 5.2.17 LTS --- backend inicial implementado
-   Django REST Framework 3.16.1 --- API inicial de clientes implementada
-   psycopg 3.3.6 --- driver PostgreSQL; python-dotenv 1.2.3 --- configuração local
-   Frontend --- ainda será definido/implementado

A stack foi aprovada pelo usuário em 24/09/2026, já considerando as
integrações previstas. FastAPI foi avaliado como alternativa; a decisão
foi manter Django + Django REST Framework pelos recursos de gestão,
autenticação, permissões e painel administrativo, sem limitar a criação
de APIs para outros sistemas. Versões selecionadas e instaladas na retomada:
Python 3.12.14, Django 5.2.17 e DRF 3.16.1. Dependências exatas estão
registradas em `backend/requirements.lock.txt`.

## 3. Estrutura atual do projeto

``` text
manutec-clientes/
├── .gitignore
├── .venv/                     # ambiente local, não versionado
├── backend/
│   ├── .env                   # configuração local, não versionada
│   ├── .env.example
│   ├── README.md
│   ├── manage.py
│   ├── requirements.txt
│   ├── requirements.lock.txt
│   ├── config/                # settings, URLs, WSGI e settings de teste
│   └── clientes/              # modelo, API, admin, migração e testes
├── database/
│   ├── schema.sql
│   └── testar_relacionamentos.sql
└── CONTEXTO_PROJETO.md
```

## 4. Regras de negócio principais

Na maioria dos casos, o cliente da Manutec é um condomínio. A
administradora não é considerada o cliente. O condomínio continua sendo
a entidade principal mesmo quando uma administradora é responsável pelo
financeiro.

Cada cliente possui um `id` interno e permanente. O CNPJ não é usado
como Chave Primária (PK), porque pode mudar ao longo do tempo sem que o
cliente deixe de ser a mesma entidade.

## 5. CNPJ

O histórico de CNPJs é armazenado na tabela `historico_cnpj`.

Regras atualizadas: - armazenar 14 caracteres, sem máscara e em maiúsculas,
aceitando o formato numérico e o alfanumérico (12 caracteres A-Z/0-9 e
2 dígitos finais); - cada CNPJ deve
ser único; - um mesmo CNPJ não pode pertencer a clientes diferentes; -
`data_inicio` indica o início da utilização; - `data_fim = NULL` indica
o CNPJ atual.

O CNPJ atual será obtido pelo histórico, evitando duplicar essa
informação em `clientes`.

## 6. Contatos do condomínio

A tabela `contatos` armazena contatos diretamente ligados ao cliente,
como síndico, encarregado e supervisor.

Os relacionamentos usam `data_inicio` e `data_fim`. `data_fim = NULL`
significa que o contato está vigente.

Existe necessidade operacional de consultar o contato atual e até dois
anteriores. Os registros históricos não devem ser apagados
automaticamente; a aplicação poderá limitar a exibição aos dois
anteriores.

## 7. Administradoras

A tabela `administradoras` representa as administradoras como entidades
independentes.

Uma administradora pode administrar vários condomínios. Um condomínio
pode possuir uma administradora atual, ter tido outras anteriormente ou
não possuir administradora.

Não será criado registro fictício de "Sem administradora".

## 8. Histórico de administradoras

A tabela `cliente_administradora` registra a relação temporal entre
cliente e administradora.

-   `data_inicio` --- início da relação;
-   `data_fim` --- fim da relação;
-   `data_fim = NULL` --- administradora atual.

O histórico permite verificar qual administradora gerenciava determinado
condomínio em um período. Isso confirma a relação histórica, mas não
representa autorização automática para fornecer informações.

## 9. Contatos das administradoras

A tabela `contatos_administradora` armazena funcionários das
administradoras.

Exemplos: - Maria --- contas a pagar; - João --- supervisor.

Uma pessoa é cadastrada uma única vez dentro da administradora.

## 10. Responsabilidades

A tabela `responsabilidades` resolve a relação muitos-para-muitos (N:N)
entre contatos de administradoras e clientes.

Exemplos: - Maria → contas a pagar → Condomínio Boa Vista - Maria →
contas a pagar → Condomínio Jardim - João → supervisor → Condomínio Boa
Vista

A função pertence ao relacionamento, pois uma mesma pessoa pode exercer
responsabilidades diferentes dependendo do cliente.

Também são usados `data_inicio` e `data_fim`, sendo `data_fim = NULL`
uma responsabilidade atual.

## 11. Faturamento

Nota fiscal e boleto são sempre enviados juntos para o mesmo conjunto de
destinatários.

A tabela `destinatarios_faturamento` armazena esses destinatários.

Tipos inicialmente definidos: - `principal` - `copia`

Também são armazenados `data_inicio` e `data_fim`. `data_fim = NULL`
significa que o destinatário está vigente.

## 12. Tabelas atuais

O `schema.sql` possui 8 tabelas:

1.  `clientes`
2.  `historico_cnpj`
3.  `contatos`
4.  `administradoras`
5.  `cliente_administradora`
6.  `contatos_administradora`
7.  `responsabilidades`
8.  `destinatarios_faturamento`

## 13. Relacionamentos principais

``` text
clientes
├── historico_cnpj
├── contatos
├── destinatarios_faturamento
├── cliente_administradora ── administradoras
└── responsabilidades ── contatos_administradora
                          └── administradoras
```

## 14. Integridade dos dados

O schema utiliza Chaves Estrangeiras (FK) para proteger os
relacionamentos e restrições `CHECK` para impedir datas inconsistentes.

Exemplo:

``` sql
CHECK (data_fim IS NULL OR data_fim >= data_inicio)
```

Para destinatários de faturamento:

``` sql
CHECK (tipo_destinatario IN ('principal', 'copia'))
```

Índices únicos parciais adicionados e confirmados no banco:

- `uq_historico_cnpj_atual`: um CNPJ atual por cliente.
- `uq_cliente_administradora_atual`: uma administradora atual por cliente.

Ambos consideram somente registros com `data_fim IS NULL` e preservam
a possibilidade de manter históricos encerrados.

## 15. Decisões técnicas importantes

### CNPJ

Não usar CNPJ como Chave Primária (PK). Usar um `id` interno como
identidade permanente do cliente.

### Histórico

Padronizar relacionamentos históricos com `data_inicio` e `data_fim`.
Quando `data_fim IS NULL`, o relacionamento é atual.

### Dados formatados

CNPJ deve ser armazenado sem máscara, em maiúsculas, aceitando o formato
alfanumérico atual. CEP continua armazenado somente com números.
A aplicação será responsável pela formatação visual.

### Campo `atualizado_em`

`DEFAULT CURRENT_TIMESTAMP` define o valor inicial, mas não atualiza
automaticamente o campo quando o registro é alterado. Isso deverá
posteriormente ser tratado pela aplicação ou por um trigger do
PostgreSQL.

## 16. Estado atual do desenvolvimento

Concluído: - levantamento inicial das regras de negócio; - definição da
arquitetura inicial; - definição das entidades e relacionamentos; -
criação da estrutura local do projeto; - criação de
`database/schema.sql`; - escrita da primeira versão completa do
schema; - criação deste checkpoint.

O banco `manutec_clientes` foi criado e o `schema.sql` foi executado
via pgAdmin. O usuário confirmou a existência das 8 tabelas e dos
2 índices únicos parciais.

Revisão em 24/09/2026: adicionados índices únicos parciais para permitir
somente um CNPJ atual e uma administradora atual por cliente, mantendo
os registros históricos. PostgreSQL 18 está instalado e o serviço está
em execução. O banco escolhido para criação do zero é
`manutec_clientes`. A conexão via terminal exige autenticação;
as execuções estão sendo feitas pelo usuário no pgAdmin.

O usuário executou `database/testar_relacionamentos.sql` no pgAdmin e
confirmou a mensagem de sucesso. O script verificou:

- Inserções válidas nas 8 tabelas, incluindo uma administradora e um
  contato de administradora atendendo dois clientes.
- Bloqueio de dois CNPJs atuais para o mesmo cliente.
- Bloqueio do mesmo CNPJ em clientes diferentes.
- Bloqueio de dois vínculos atuais de administradora para o cliente.
- Bloqueio de datas inconsistentes em contatos.
- Bloqueio de tipo inválido de destinatário de faturamento.
- Proteção por chave estrangeira ao excluir cliente com relacionamentos.
- Criação de novos vínculos atuais após encerrar os anteriores.

As inserções fictícias foram desfeitas pelo ROLLBACK final do script;
as sequências dos IDs podem ter avançado. Não foram preparados dados
persistentes de demonstração. A confirmação dos testes veio do usuário;
o assistente não executou o script diretamente no banco.

Na retomada, foi implementada a primeira etapa do backend/API:

- Ambiente `.venv` criado a partir do Python 3.12.14 disponível no runtime
  do Codex. Não havia `python`/`py` no PATH. Para executar independentemente
  desse runtime, instalar Python e recriar o ambiente, conforme README.
- Projeto Django com configuração PostgreSQL por variáveis de ambiente.
- `.env` local criado com chave aleatória; senha PostgreSQL preenchida
  pelo usuário e conexão validada posteriormente.
  Não ler/exibir o conteúdo desse arquivo no chat após o usuário preenchê-lo.
- Modelo `Cliente` mapeado para `clientes` com `managed=False`; migração
  inicial registra o estado do modelo e não cria a tabela existente.
  As outras sete tabelas ainda precisam ser mapeadas.
- API `/api/v1/clientes/` com cadastro, listagem paginada, pesquisa por
  razão social/nome fantasia/cidade, consulta individual e edição.
- Login por sessão e permissões de visualizar/adicionar/alterar.
  Exclusão indisponível na API e no admin nesta etapa.
- Painel administrativo de clientes configurado. IDs e datas somente
  leitura; `atualizado_em` mantido nos salvamentos pelo Django.
- Horários locais America/Fortaleza (`USE_TZ=False`) nesta etapa para
  compatibilidade com TIMESTAMP sem fuso do schema existente.
- Validação de razão social, CEP de 8 dígitos e UF válida.
- README com configuração, migrações, criação do usuário e execução.

Verificações executadas pelo assistente: `manage.py check` sem problemas
e 7 testes da API aprovados em SQLite temporário. Esses testes cobrem
acesso anônimo, usuário sem permissão, leitor, pesquisa, cadastro/edição,
campos inválidos, preservação de ID/datas, exclusão indisponível e 404.
Não substituem a validação real no PostgreSQL.

Após o usuário preencher a senha no `.env`, a conexão PostgreSQL foi
validada: as oito tabelas existentes foram encontradas e a consulta ORM
funcionou. As migrações de auth, admin, contenttypes, sessions e o estado
do modelo Cliente foram aplicadas com sucesso. `migrate --check` confirmou
que não há migrações pendentes. As tabelas originais foram preservadas.

Cadastro e edição pela API também foram exercitados no PostgreSQL dentro
de uma transação desfeita ao final. Nenhum cliente fictício permaneceu;
o ID da sequência pode ter avançado. Posteriormente, o usuário criou o
administrador local, confirmou o acesso ao painel e confirmou cadastro e
edição de um cliente sem erro. O teste manual orientado usou um cliente
fictício (`TESTE — Condomínio Exemplo`); esse registro é persistente,
diferentemente do teste automático com rollback. Não removê-lo sem pedido.
Interface final e integrações ainda não implementadas. A pasta não era
repositório Git na verificação inicial.

### Arquitetura e integrações aprovadas

Objetivo do usuário: manter opções abertas para novas integrações e
crescimento. Prioridades próximas: Conta Azul, Auvo, envio conjunto de
boleto e nota por e-mail e WhatsApp. n8n fica para longo prazo.

Direção aprovada: começar com uma aplicação Django organizada em módulos,
com PostgreSQL e API em Django REST Framework. Primeiro entregar cadastro,
históricos e API; conectar os serviços gradualmente depois.

Preparar a arquitetura para:

- Associar o ID interno permanente do cliente aos identificadores dele
  em cada sistema externo, sem depender exclusivamente do CNPJ.
- Definir qual sistema prevalece em cada informação. Proposta inicial:
  Manutec para contatos e destinatários, Conta Azul para financeiro e
  Auvo para execução dos serviços. Detalhar campos, sentido da
  sincronização e tratamento de conflitos antes de cada integração.
- Executar sincronizações e envios em segundo plano, sem travar a tela,
  com registro de falhas e novas tentativas controladas. A tecnologia
  de fila/agendamento ainda não foi escolhida.
- Evitar duplicação de cadastros e envios em operações repetidas.
- Disponibilizar API documentada e com permissões, compartilhando as
  regras de negócio entre interface, integrações e futuro n8n.
- Manter o código de comunicação com cada fornecedor em seu módulo,
  permitindo adicionar ou substituir integrações gradualmente.

Pesquisa de documentação realizada em 24/09/2026 (revalidar recursos e
acesso da conta ao implementar):

| Serviço | Direção e pontos pendentes |
| --- | --- |
| Conta Azul | Integrar cadastros e dados financeiros via API/OAuth 2.0. A documentação consultada informa ausência de webhooks, exigindo consultas periódicas. Confirmar endpoints e permissões necessários. |
| Auvo | Integrar clientes e informações de tarefas/ordens de serviço pela API. Confirmar os eventos e operações necessários. |
| E-mail/Outlook | Microsoft Graph é a opção proposta se a conta usada for compatível; permite anexos e destinatários em cópia. O usuário aceita outro provedor se for mais adequado. Provedor final ainda não escolhido. |
| WhatsApp | Usar a plataforma oficial WhatsApp Business; definir conta, forma de contratação e fluxos de comunicação na etapa de integração. |
| n8n | Longo prazo: consumir nossa API e acionar operações autorizadas. Não é dependência da primeira entrega. |

Pendência importante: identificar a origem dos arquivos de boleto e nota
fiscal. Obter os documentos é uma etapa distinta de enviá-los. A página
geral da Conta Azul consultada indicava limitações para notas de serviço
(NFS-e); não presumir disponibilidade dos arquivos pela API. A aceitação
de um envio pelo provedor de e-mail também não comprova sua entrega.

Fontes consultadas:

- Django: https://www.djangoproject.com/start/
- Django REST Framework: https://www.django-rest-framework.org/tutorial/quickstart/
- Conta Azul: https://developers.contaazul.com/aboutapis
- Auvo: https://developer.auvo.com.br/quickstart
- Microsoft Graph: https://learn.microsoft.com/en-us/graph/api/user-sendmail?view=graph-rest-1.0
- WhatsApp (coleção da Meta): https://www.postman.com/meta/whatsapp-business-platform/documentation/wlk6lh4/whatsapp-cloud-api

## 17. Próximo passo

### Consultas universais e Git (25/09/2026)

- Regra do usuário: todo campo editável de CNPJ/CEP deve consultar API pública.
- Administradora: criação e edição consultam BrasilAPI, preenchendo razão
  social, nome fantasia, telefone e e-mail disponíveis. Endereço é mostrado
  para conferência; a tabela de administradoras ainda não tem endereço.
- Troca do CNPJ de cliente: consulta e exibe dados para conferência; salva
  apenas o vínculo, sem sobrescrever os dados cadastrais do cliente.
- CEP permanece consultando ViaCEP no cadastro e na edição de clientes.
- Um script de CNPJ é compartilhado pelos formulários; respeita campos
  presentes e alterações manuais durante a consulta. Consultas não salvam.
- 29 testes isolados aprovados.
- Git não existia antes desta solicitação; inicializado agora na branch main.
- Remoto: https://github.com/DanielTabosa/manutec_clientes.git (vazio na consulta inicial).
- Autor aprovado: DanielTabosa <DanielTabosa@users.noreply.github.com>.
- .env, .venv, caches, dumps e chaves excluídos. Nenhum dado do PostgreSQL
  será publicado; só código, schema, testes e documentação.
- No Windows, .git foi criado pelo usuário do sandbox. Git no usuário normal
  exige `git -c safe.directory=C:/dev/manutec-clientes ...` nesta sessão.
  O executor restrito apresentou falha de setup após git init; operações
  posteriores foram executadas com aprovação fora do sandbox. Tentativa de
  ajustar o proprietário da pasta foi negada; não houve alteração global de segurança.
- Primeiro commit e push: consultar registro ao final deste arquivo.


### Etapa mais recente: administradoras e vínculos (25/09/2026)

Após o usuário pedir continuidade, implementados:

- Administradora e ClienteAdministradora mapeados às tabelas existentes,
  managed=False. Migração 0005 aplicada sem recriar tabelas.
- Cadastro/edição/pesquisa de administradoras no painel e API. Razão social
  obrigatória; CNPJ opcional conforme schema (quando preenchido, normalizado
  e único); nome fantasia, telefone e e-mail opcionais. Não há consulta
  automática de CNPJ nesta tela de administradoras nesta etapa.
- No cliente: administradora atual, link "Vincular, trocar ou encerrar" e
  histórico somente leitura. Nenhuma entidade fictícia "Sem administradora".
- Serviço compartilhado entre API/painel, transação e bloqueio do cliente.
  Troca encerra o anterior no dia precedente; encerramento deixa sem atual.
  Aceita retorno à mesma empresa após período encerrado. Permite uma empresa
  atender vários clientes. Rejeita sobreposição ao último período, data
  futura, encerramento anterior ao início ou troca pela empresa já atual.
- API `/api/v1/administradoras/` e detalhe com GET/POST/PUT/PATCH conforme
  rota; `/api/v1/clientes/{id}/administradora/` GET atual/histórico e POST
  com acao=vincular|encerrar, data e administradora para vincular.
- Vínculos exigem change_cliente + view_administradora; consulta do vínculo
  exige view_cliente. Cadastro de empresas usa permissões próprias.
- Exclusão indisponível no painel/API. Histórico preservado.
- 28 testes isolados aprovados. Vínculo, troca e encerramento verificados
  também no PostgreSQL com rollback; nenhum dado temporário persistido.
- Servidor atualizado; lista/formulário de administradoras conferidos no
  navegador. Documentação no backend/README.md. Teste do usuário pendente.

Próximo passo: receber eventuais ajustes/teste do usuário nesta etapa e
implementar contatos das administradoras e responsabilidades por cliente;
depois destinatários de faturamento. Etapas abaixo são checkpoints anteriores.

### Retomada em 25/09/2026: contatos dos condomínios

Implementada a próxima etapa do checkpoint:

- Modelo Contato mapeado para a tabela existente `contatos`, managed=False.
  Migração 0004 aplicada, sem criar/recriar a tabela SQL.
- Painel de contatos com cadastro, edição, pesquisa e filtro de vigência.
- No cliente, links para adicionar contato e consultar seu histórico,
  além da listagem dos contatos em modo de consulta com link para edição.
- Nome, cliente e início obrigatórios; função, telefone e e-mail opcionais.
  Data final vazia significa vigente; encerramento não pode preceder início.
- Vários contatos atuais são permitidos. Não presumida exclusividade por
  função. Para substituir alguém, encerrar o registro antigo e cadastrar outro.
- Exclusão indisponível e cliente imutável após criação no painel/API.
  Correções de dados e datas continuam permitidas. Histórico completo é
  preservado; apresentação compacta de dois anteriores fica para a interface.
- API `/api/v1/contatos/` e `/api/v1/contatos/{id}/`: cadastro, consulta e
  edição, paginação, pesquisa, filtros `cliente=ID` e `vigente=true|false`.
  Permissões próprias view_contato, add_contato, change_contato.
- 23 testes isolados aprovados (18 anteriores + 5 de contatos), cobrindo
  cadastro/encerramento, histórico, datas, e-mail, permissões, filtros,
  cliente imutável e formulário administrativo.
- Cadastro e encerramento pela API validados no PostgreSQL com rollback;
  nenhum contato temporário foi deixado no banco. Servidor local iniciado.
- Lista e formulário de contato conferidos no navegador. Teste manual do
  usuário ainda pendente; detalhes de uso em backend/README.md.

Próxima etapa: receber o teste/ajustes do usuário nos contatos; depois
implementar administradoras e seus vínculos históricos. Ainda pendentes:
administradoras, cliente_administradora, contatos_administradora,
responsabilidades e destinatarios_faturamento. Não refazer etapas concluídas.

Os checkpoints abaixo são registros das etapas anteriores.

### Checkpoint final do dia: CEP e pausa solicitada

O usuário pediu CEP no início do endereço, preenchimento automático por
CEP e, depois disso, salvar tudo e encerrar por hoje. Implementação concluída:

- CEP antes de logradouro no cadastro e na edição do cliente.
- Consulta ViaCEP ao completar 8 números, com botão para consultar novamente.
- Aceita CEP com ou sem hífen no painel e persiste somente números.
- Preenche logradouro, bairro, cidade e UF; preserva número e complemento.
- Timeout e mensagens para CEP inválido/inexistente e serviço indisponível;
  permite completar endereço manualmente, inclusive CEPs gerais sem rua.
- Evita que respostas antigas de CEP/CNPJ sobrescrevam uma escolha mais
  recente de endereço. Dados do CNPJ não acionam consulta redundante de CEP.
- Permissão de adicionar ou alterar cliente exigida na consulta de CEP.
- 18 testes isolados aprovados; `check` sem problemas e nenhuma mudança de
  modelo pendente. Esta etapa de CEP não exigiu migração do banco.
- Servidor local atualizado; instruções de reinício em backend/README.md.
- Fonte: https://viacep.com.br/ (contrato público consultado nesta etapa).
- Consulta real no navegador validada com CEP 01001-000: rua, bairro,
  cidade e UF preenchidos; número e complemento de teste preservados.
  Nenhum cadastro foi salvo nesse teste; navegador devolvido à lista.

Na retomada: ler este checkpoint, iniciar o servidor se necessário,
receber eventuais ajustes do usuário ao fluxo CNPJ/CEP e seguir para os
contatos e demais relacionamentos ainda não implementados. Não repetir
a instalação, criação do banco, nem as etapas já concluídas.

As seções seguintes preservam detalhes da implantação de CNPJ.

### Alteração concluída: CNPJ obrigatório no cadastro

Por solicitação do usuário, o cadastro foi alterado para começar pelo CNPJ
e não permitir criar cliente sem vínculo de CNPJ. Implementado:

- CNPJ primeiro e obrigatório no formulário de adicionar cliente.
- Consulta automática à BrasilAPI após completar o campo, com razão social,
  nome fantasia e endereço editáveis para conferência. Timeout de 10 segundos,
  mensagens de erro e preenchimento manual se houver falha ou dados ausentes.
- Endereço obrigatório no cadastro: logradouro, número (aceita S/N), bairro,
  cidade, UF e CEP. Complemento e nome fantasia opcionais.
- Serviço `cadastrar_cliente` salva cliente e primeiro CNPJ na mesma transação,
  utilizado pelo painel e POST da API. Falhas/duplicidade desfazem tudo.
- Aceita máscara e CNPJ alfanumérico; normaliza antes de persistir.
  Não valida dígitos verificadores nem comprova situação cadastral.
- Migração 0003 aplicada: triggers diferidos PostgreSQL impedem novos clientes
  sem CNPJ atual e impedem remover o último CNPJ atual no histórico. O campo
  CNPJ permanece NOT NULL em historico_cnpj, sem duplicação em clientes.
- Verificação dos registros existentes não encontrou cliente sem CNPJ atual.
- 16 testes isolados aprovados. Comando `verificar_cadastro` validou triggers,
  cadastro e troca no PostgreSQL, desfazendo seus dados temporários.
- Consulta real e preenchimento no navegador validados com CNPJ público do
  Banco do Brasil; nenhum cadastro desse teste foi salvo. Formulário limpo
  deixado aberto para uso. Servidor local reiniciado com acesso à BrasilAPI.
- Documentação atualizada em backend/README.md. O antigo schema.sql sozinho
  não inclui os triggers da migração 0003: instalações novas exigem migrations.

Fontes consultadas nesta alteração:
- https://github.com/BrasilAPI/BrasilAPI/blob/main/pages/docs/doc/cnpj.json
- https://www.gov.br/receitafederal/pt-br/assuntos/noticias/2026/julho/receita-federal-gera-o-primeiro-cnpj-em-formato-alfanumerico

Próxima ação: usuário testar Adicionar cliente com o novo fluxo por CNPJ;
depois continuar os demais relacionamentos conforme abaixo. As notas de
validação numérica da etapa anterior abaixo foram substituídas pela regra
alfanumérica e cadastro obrigatório descritos acima.

1. Histórico de CNPJ implementado e disponível no formulário de cliente,
   no link "Cadastrar / trocar CNPJ", com histórico somente leitura abaixo.
   Aguardando teste manual do usuário. Modelo não gerenciado e migração
   0002 aplicados sem recriar a tabela existente. API GET/POST em
   `/api/v1/clientes/{id}/cnpj/`. Troca exige permissão de alterar cliente;
   consulta exige visualizar. Serviço compartilhado entre API e painel usa
   transação e bloqueio do cliente, preservando seu ID e encerrando o
   anterior no dia precedente ao início do novo. Datas devem ser posteriores
   ao último período e não futuras. CNPJ duplicado no histórico é recusado.
   Validação atual: 14 dígitos, sem máscara; não verifica dígitos verificadores
   nem situação cadastral. Evolução de formato de CNPJ requer avaliação futura.
   Total de 11 testes isolados aprovados, incluindo painel e permissões.
   Troca e preservação do histórico verificadas também no PostgreSQL com
   rollback dos dados temporários. Servidor local reiniciado com a atualização.
2. Mapear as demais tabelas e implementar históricos e regras
   compartilhadas, preservando as restrições existentes.
3. Evoluir documentação da API, interface e integrações por etapas;
   detalhar os fluxos antes de conectar cada serviço.

## 18. Instrução para continuar em outro chat

Ao iniciar uma nova conversa, fornecer este arquivo e informar:

> Quero continuar o projeto Manutec Clientes. Leia o
> `CONTEXTO_PROJETO.md` e continue exatamente do ponto registrado em
> "Próximo passo".

O arquivo deve ser atualizado conforme decisões importantes forem
tomadas ou novas etapas forem concluídas.

------------------------------------------------------------------------

**Checkpoint:** Consultas CNPJ/CEP padronizadas; 29 testes aprovados; Git inicializado e código publicado no GitHub\
**Data:** 25/09/2026


### Publicação no GitHub confirmada (25/09/2026)

Primeiro commit `fcc35b3` enviado com sucesso para origin/main no repositório
https://github.com/DanielTabosa/manutec_clientes . O histórico Git começa
neste ponto; não existiam commits das etapas anteriores. Este commit inclui
as etapas anteriores e a correção das consultas de CNPJ.

Consulta real de administradora conferida no navegador com CNPJ público:
razão social, nome fantasia e telefone preenchidos, endereço exibido;
nenhum cadastro de teste persistido. Seguir fazendo commits por etapa
concluída. Dados PostgreSQL permanecem locais; GitHub não é backup do banco.
