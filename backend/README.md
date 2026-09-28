# Backend Manutec Clientes

Cadastro, consulta e edicao de clientes, contatos diretos e administradoras,
com historicos de CNPJ e vinculos de administradora. Python 3.12, Django 5.2
LTS, DRF 3.16 e PostgreSQL 18. Este documento e um guia de instalacao/uso;
para continuidade, leia [AGENTS](../AGENTS.md) e [SESSION_HANDOFF](../SESSION_HANDOFF.md).
Estado global sob demanda em [PROJECT_STATE](../PROJECT_STATE.md).

## Ambiente local

Os comandos abaixo sao executados em PowerShell na raiz `C:\dev\manutec-clientes`.
O ambiente `.venv` ja foi criado nesta maquina com o Python 3.12.14
disponibilizado pelo Codex. Ele depende desse runtime; para uso independente
do Codex ou em outra maquina, instale Python 3.12 e recrie o ambiente com
`python -m venv .venv`.

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.lock.txt
```

`requirements.txt` define faixas; `requirements.lock.txt` registra as versoes
instaladas. Reavalie atualizacoes de seguranca antes de publicar.

O arquivo `backend/.env` local ja foi criado com uma chave aleatoria.
Preencha `POSTGRES_PASSWORD` nesse arquivo com a senha do usuario indicado
em `POSTGRES_USER`. Nao envie a senha no chat. Se houver `#` ou espacos na
senha, coloque o valor entre aspas duplas. `.env` esta ignorado no Git.
Em outra maquina, copie `.env.example` e gere uma nova chave aleatoria.

## Banco existente e migracoes

Os modelos `Cliente`, `HistoricoCNPJ`, `Contato`, `Administradora` e
`ClienteAdministradora`, `ContatoAdministradora` e `Responsabilidade` mapeiam sete tabelas com `managed=False`.
As migracoes de estado desses modelos nao recriam as tabelas; a migracao
0003 adiciona triggers de obrigatoriedade de CNPJ no PostgreSQL.
`destinatarios_faturamento` existe no schema SQL e ainda nao esta mapeada no Django.
As migracoes padrao do Django criam tabelas adicionais para usuarios,
permissoes, sessoes e administracao; as oito tabelas existentes permanecem.
Nao execute novamente `database/schema.sql` no banco existente.

Depois de preencher a senha, primeiro confira conexao e plano:

```powershell
.\.venv\Scripts\python.exe backend/manage.py check
.\.venv\Scripts\python.exe backend/manage.py migrate --plan
```

Com a conexao validada, aplique as migracoes e crie seu usuario local:

```powershell
.\.venv\Scripts\python.exe backend/manage.py migrate
.\.venv\Scripts\python.exe backend/manage.py createsuperuser
.\.venv\Scripts\python.exe backend/manage.py runserver 127.0.0.1:8000
```

Abra http://127.0.0.1:8000/admin/ para o painel administrativo ou
http://127.0.0.1:8000/api/v1/clientes/ para a API navegavel (login no canto
superior). Usuario comum precisa das permissoes de visualizar, adicionar
ou alterar clientes; acesso ao admin exige tambem `is_staff`.
Autenticacao de integracoes externas sera adicionada em etapa propria.

## API inicial

| Metodo | Caminho | Operacao |
| --- | --- | --- |
| GET | `/api/v1/clientes/` | Lista paginada, 25 clientes por pagina |
| GET | `/api/v1/clientes/?search=Fortaleza` | Pesquisa por razao social, nome fantasia ou cidade |
| GET | `/api/v1/clientes/{id}/` | Consulta um cliente |
| POST | `/api/v1/clientes/` | Cadastra um cliente |
| PUT/PATCH | `/api/v1/clientes/{id}/` | Edita um cliente |

Exemplo de corpo JSON para cadastro:

```json
{"cnpj": "12.345.678/0001-00", "razao_social": "Condominio Exemplo", "logradouro": "Rua Exemplo", "numero": "10", "bairro": "Centro", "cidade": "Fortaleza", "estado": "CE", "cep": "60000000"}
```

No cadastro, CNPJ, razao social e endereco (logradouro, numero, bairro,
cidade, estado e CEP) sao obrigatorios. Nome fantasia e complemento sao
opcionais. CEP deve conter 8 digitos sem mascara; estado
deve ser uma UF valida. ID e datas de auditoria sao somente leitura.
`atualizado_em` e atualizado nos salvamentos pelo Django; alteracoes SQL
diretas nao recebem essa atualizacao automaticamente. Nesta etapa usamos
horario local America/Fortaleza, compativel com TIMESTAMP sem fuso do schema.
Exclusao nao e disponibilizada na API nem no admin nesta etapa.
CNPJ: no formulario de um cliente salvo, clique em **Cadastrar / trocar
CNPJ**. O historico e exibido abaixo, somente para consulta. A troca usa
transacao e bloqueio do cliente, encerrando o anterior no dia precedente
ao inicio do novo. A data deve ser posterior ao ultimo periodo e nao
pode estar no futuro. CNPJ aceita 14 caracteres, numericos ou alfanumericos,
com dois digitos finais. Mascara e removida e letras sao convertidas para maiusculas;
nao ha validacao de digitos verificadores ou situacao cadastral.

`GET /api/v1/clientes/{id}/cnpj/` retorna `atual` e `historico`.
`POST` na mesma rota recebe `cnpj` e `data_inicio` (AAAA-MM-DD) e exige
permissao de alterar cliente. Consulta exige permissao de visualizar.
O modelo HistoricoCNPJ tambem usa `managed=False`; a migracao 0002
registra o estado sem recriar a tabela SQL existente.
Contatos diretos e vinculos historicos de administradoras tambem estao
implementados, conforme as secoes abaixo. Responsabilidades e configuração de destinatários estão implementadas; envio real de documentos continua pendente.

## Cadastro com consulta por CNPJ

Em Adicionar cliente, CNPJ e o primeiro campo. Ao completa-lo, o navegador
consulta o backend, que consulta a BrasilAPI com timeout de 10 segundos.
Razao social, nome fantasia e endereco sao preenchidos para conferencia.
Em caso de falha ou dados incompletos, o operador pode preencher manualmente;
CNPJ e endereco continuam obrigatorios. Isso nao comprova situacao cadastral.
O backend precisa ter acesso HTTPS a brasilapi.com.br.

Cliente e primeiro CNPJ sao salvos em uma transacao no painel e na API.
`data_inicio` e opcional na API (padrao: hoje). PUT/PATCH nao alteram CNPJ;
para isso use a rota especifica de troca. A migracao 0003 adiciona triggers
PostgreSQL adiados ate o fim da transacao: novos clientes devem ter CNPJ
atual e alteracoes no historico nao podem remover o ultimo vinculo atual.
Nao duplica CNPJ em clientes e nao recria as tabelas existentes. A regra
depende das migracoes: executar apenas schema.sql nao instala esses triggers.

Validacao PostgreSQL com rollback de todos os dados temporarios:

```powershell
.\.venv\Scripts\python.exe backend/manage.py verificar_cadastro
```

Fonte do contrato: https://github.com/BrasilAPI/BrasilAPI/blob/main/pages/docs/doc/cnpj.json

## Consulta por CEP

CEP aparece antes do logradouro tanto no cadastro quanto na edicao.
Ao digitar 8 numeros (com ou sem hifen), o endereco e consultado no ViaCEP.
O botao Consultar CEP permite repetir a consulta. Preenche logradouro,
bairro, cidade e UF, preservando numero e complemento. CEPs gerais podem
retornar campos vazios: complete manualmente. Erros e indisponibilidade
sao informados na tela. O CEP e salvo sem mascara.

O endereco ja retornado pelo CNPJ nao dispara outra consulta de CEP
automaticamente. Ao editar o CEP, vale a nova consulta, sem deixar uma
resposta antiga do CNPJ sobrescrever o endereco escolhido.
O servidor precisa de acesso HTTPS a viacep.com.br.
Fonte: https://viacep.com.br/

## Contatos dos condomínios

Em um cliente salvo, use **Adicionar contato** ou **Consultar contatos e
histórico**. Também existe o menu **Contatos dos condomínios** no painel.
Nome, cliente e data de início são obrigatórios; função, telefone e e-mail
são opcionais. Data de encerramento vazia indica contato vigente.
Para substituir uma pessoa, encerre o vínculo anterior e cadastre o novo.
Podem existir vários contatos atuais. Nenhum histórico é apagado
automaticamente; a lista permite filtrar atuais ou encerrados.

Exclusão não está disponível. O cliente de um contato salvo não pode ser
trocado no painel/API, para não transferir seu histórico. Dados de contato
e datas podem ser corrigidos. Encerramento anterior ao início é recusado.

API com paginação:

- `GET/POST /api/v1/contatos/`
- `GET/PUT/PATCH /api/v1/contatos/{id}/`
- `GET /api/v1/contatos/?cliente=4&vigente=true` (use `false` para encerrados)
- `GET /api/v1/contatos/?search=sindico`

POST recebe `cliente` (ID), `nome`, `data_inicio` (AAAA-MM-DD) e os demais
campos opcionais. Para encerrar, PATCH com `data_fim` na mesma representação.
Permissões específicas: `view_contato`, `add_contato`, `change_contato`.
Permissão sobre clientes, isoladamente, não concede acesso aos contatos.
A migração 0004 registra o modelo não gerenciado: não recria a tabela SQL.

## Administradoras e vínculos

Cadastre a empresa no menu **Administradoras** (razão social obrigatória;
CNPJ, nome fantasia, telefone e e-mail opcionais conforme o schema).
O CNPJ, quando informado, aceita máscara e é normalizado; duplicatas são
recusadas. Esta tela consulta automaticamente o CNPJ ao completar o campo, também na edição.

No cliente, use **Vincular, trocar ou encerrar** na seção Administradora.
Para vincular/trocar, selecione a empresa e a data de início. Na troca,
o vínculo anterior termina no dia precedente. Para encerrar, deixe a
empresa em branco e informe a data final. Não são aceitas datas futuras,
início sobreposto ao último período ou encerramento anterior ao início.
Sem vínculo atual, o cliente aparece como sem administradora, sem registro
fictício. Uma administradora pode atender vários clientes.

Histórico somente leitura no painel. As operações usam transação e bloqueio
do cliente. Exclusão não é disponibilizada. Permissões de alterar cliente
e visualizar administradora são necessárias para gerir vínculos.

- `GET/POST /api/v1/administradoras/`
- `GET/PUT/PATCH /api/v1/administradoras/{id}/`
- `GET /api/v1/clientes/{id}/administradora/`: atual e histórico.
- `POST` na mesma rota: `{"acao":"vincular","administradora":1,"data":"2026-09-25"}`
- Para encerrar: `{"acao":"encerrar","data":"2026-09-25"}`.

Cadastros de administradora usam permissões view/add/change_administradora.
Modelos não gerenciados; migração 0005 registra o estado sem recriar tabelas.

## Verificacao isolada

```powershell
.\.venv\Scripts\python.exe backend/manage.py test clientes --settings=config.test_settings
```

Estes testes usam SQLite temporario e validam a API, permissoes e validacoes.
Nao acessam `manutec_clientes` e nao comprovam compatibilidade real com
PostgreSQL. A verificacao nessa base depende da conexao local configurada.
O servidor de desenvolvimento e a configuracao local nao sao de producao.

## Consultas padronizadas de CNPJ e CEP

CNPJ consulta na criação do cliente, na criação/edição da administradora
(e preenche razão social, nome fantasia, telefone/e-mail disponíveis) e
na troca de CNPJ do cliente. Nesta última, os dados são apresentados para
conferência; somente o vínculo é salvo, preservando os dados atuais do cliente.
Administradoras não possuem endereço no schema: o endereço consultado é
apresentado para conferência, sem persistência nessa entidade.
CEP consulta nos formulários de criação e edição do cliente.
As consultas não gravam automaticamente e permitem correções antes de salvar.


## Contatos da administradora e responsabilidades

No painel, use **Contatos de administradoras** para cadastrar a pessoa uma vez na empresa. Em **Responsabilidades**, selecione o contato e o cliente, informe função e início; preencha o fim para encerrar. Pesquise por nome, cliente ou função e filtre atuais/encerrados. As referências ficam fixas após salvar. Telefone/e-mail são corrigidos no contato compartilhado.

- `GET/POST /api/v1/contatos-administradora/`; detalhe `GET/PUT/PATCH .../{id}/`.
- Filtros: `?administradora=ID&search=Ana`.
- `GET/POST /api/v1/responsabilidades/`; detalhe `GET/PUT/PATCH .../{id}/`.
- Filtros: `?cliente=ID&contato_administradora=ID&vigente=true&search=Financeiro` (`vigente=false` para encerrados).
- Cadastro: `{"contato_administradora":1,"cliente":1,"funcao":"Financeiro","data_inicio":"2026-01-01"}`.
- Encerramento por PATCH: `{"data_fim":"2026-09-26"}`. Datas futuras e períodos fora do vínculo da empresa são rejeitados.

Não há DELETE. Permissões view/add/change_contatoadministradora e view/add/change_responsabilidade controlam cada módulo. Autocomplete no painel exige visualizar a entidade referenciada. Troca de empresa mantém as permissões existentes (alterar cliente + visualizar administradora) e encerra responsabilidades como efeito da operação autorizada.

Trocar/encerrar a administradora encerra suas responsabilidades abertas daquele cliente na mesma data final, em uma transação. Datas que invalidem responsabilidades impedem a operação inteira. Sobreposição da mesma pessoa/cliente/função é rejeitada, com comparação de função sem espaços externos e sem distinção de maiúsculas. Homônimos e canais compartilhados são permitidos.

Migration 0006 registra os modelos não gerenciados e permite criar suas permissões via migrate, sem recriar tabelas. Aplicada ao banco instalado, sem alterar o conteúdo das oito tabelas de domínio. Os 37 testes passaram em SQLite; oito verificações adicionais passaram em PostgreSQL 18.4 isolado, incluindo restrições e concorrência. Os fluxos do painel também foram conferidos visualmente no Edge com dados fictícios. Validações novas estão na aplicação e não protegem SQL direto/bulk updates. Nenhum versionamento de telefone/e-mail, principal/alternativo ou destinatário automático foi acrescentado.


## Validação PostgreSQL reproduzível

Execute `.venv/Scripts/python.exe backend/verificar_postgresql.py` na raiz. O script usa a conexão configurada sem imprimir credenciais, exige permissão de criar banco, cria um banco aleatório com prefixo `manutec_validacao_`, instala schema e migrations apenas nele e o remove ao terminar. Não reaplica schema no banco instalado. São 11 verificações: as oito originais (restrições/FKs e trigger de CNPJ, datas/duplicidade/vínculos fixos, troca/retorno, rollback, três cenários de concorrência e painel/API/permissões) e três de destinatários (regras/constraints/histórico, edição concorrente e encerramento bloqueando seleção).

Para inspeção visual, `--keep` mantém o banco descartável cujo nome é mostrado. Aponte POSTGRES_DB apenas no processo do servidor temporário para esse nome e inicie `runserver 127.0.0.1:8765 --noreload`. O script prepara dois clientes e um usuário fictício exclusivo desse banco. `node backend/verificar_painel.cjs` usa Playwright disponível no runtime e Edge instalado; configure NODE_PATH para o diretório de pacotes do runtime quando necessário. QA_BASE_URL aceita servidor local (padrão porta 8765); QA_SCREENSHOT_DIR define a pasta de capturas (padrão temporária). Execute uma vez por banco novo. Encerre o servidor e remova somente esse banco descartável após a inspeção; `--keep` transfere essa limpeza ao operador. Não use as credenciais fictícias em outro ambiente.

Validação de 26–27/09/2026: PostgreSQL 18.4, oito verificações aprovadas, bloqueios concorrentes observados e capturas inspecionadas. A migration instalada criou as permissões dos dois modelos; nenhuma permissão foi concedida a usuários existentes. Na conclusão da etapa 0006, o banco instalado estava sem migrations pendentes. A migration 0007 foi aplicada em 28/09/2026, conforme a seção abaixo. Servidor e bancos descartáveis removidos.


## Destinatários de documentos e comunicações (implantação em 28/09/2026)

Implementados painel, API e serviços; migration 0007 validada em banco descartável e **aplicada ao banco instalado em 28/09/2026**. Aplicação usa 0007 para três tabelas novas e a coluna encerrado_em de contatos_administradora. Não reaplicar schema.sql e não converter automaticamente destinatarios_faturamento. Nesta implantação, o legado estava vazio (0 registros). Em outras instalações, conferir a contagem antes de aplicar e conciliar explicitamente contatos/categorias se houver registros. A nova versão do código requer essa migration para operar.

No cadastro de cliente/administradora, abrir **Destinatários e histórico**. Selecionar contatos existentes e categorias boleto, nota fiscal, laudo, comunicado e cobrança. No condomínio, escolher “Seguir a lista da administradora”, “Seguir a lista e adicionar destinatários” ou “Escolher os destinatários deste condomínio”; a escolha vale para todas as categorias. Os valores internos da API permanecem usar/complementar/substituir. A explicação abaixo do seletor acompanha a escolha. Marcar encerramento local retira o contato da empresa somente daquele condomínio, inclusive se herdado do padrão. Na listagem de contatos da administradora, a ação **Encerrar contato na empresa inteira** retira o contato de todos os destinatários; não encerra automaticamente responsabilidades/funções anteriores.

Rotas sob `/api/v1/`:

| Rota | Operação |
| --- | --- |
| `clientes/{id}/destinatarios/` | GET estado/efetivos; PUT configuração completa |
| `administradoras/{id}/destinatarios/` | GET/PUT padrão |
| As duas acima + `historico/` | GET revisões paginadas, 25 por página; últimos 25 encerramentos globais pertinentes |
| `contatos-administradora/{id}/encerrar/` | POST encerramento global imediato, idempotente |

PUT recebe `numero` da última revisão (0 na primeira), `vinculo_id` atual para cliente ou null sem empresa, `modo` (usar/complementar/substituir) e `itens`. Cada item tem exatamente um `contato_id` ou `contato_administradora_id` e booleanos `boleto`, `nota_fiscal`, `laudo`, `comunicado`, `cobranca`. Encerramento local usa `encerrado_local: true` e nenhuma categoria. Edição desatualizada ou vínculo trocado retorna 400, sem gravação parcial. Salvar sem mudanças não duplica revisão. Remover um item não apaga históricos; supressão local anterior é preservada. Não há reativação automática nem DELETE.

Permissões: leitura exige `view_configuracaodestinatarios`, `view_cliente` ou `view_administradora`, e `view_contatoadministradora`; para cliente também `view_contato` e `view_administradora`. Escrita exige adicionalmente `change_configuracaodestinatarios`. Encerramento global pela API exige `change_contatoadministradora`, `view_contatoadministradora` e `change_configuracaodestinatarios`; a ação do admin exige as duas change, além do acesso normal à listagem. Nenhuma concessão automática a usuários existentes. Histórico não possui rotas de escrita.

Sem e-mail é permitido. O módulo configura destinatários; não envia documentos por e-mail ou WhatsApp. Histórico mostra revisões locais e padrões das empresas vinculadas com origem identificada; não prova o conjunto efetivo de uma data passada, não versiona telefone/e-mail e não registra entregas.

Validação: `python backend/manage.py test clientes --settings=config.test_settings` executou 48 testes SQLite. `backend/verificar_postgresql.py` executou 11 verificações em banco descartável, incluindo legado preservado pela migration, checks/FKs e concorrência; o script remove o banco, exceto com `--keep`. Para inspeção, executar `backend/verificar_destinatarios_painel.cjs` com Node/Playwright/Edge contra servidor no banco descartável: `QA_BASE_URL` localhost e `QA_SCREENSHOT_DIR` para capturas. Remover o banco mantido e encerrar servidor após inspeção. SQLite não valida bloqueios/triggers PostgreSQL. Casos concorrentes são evidência limitada aos cenários exercitados.


### Verificação da implantação e recuperação local

Em 28/09/2026, o backup anterior à 0007 foi criado com `pg_dump --format=custom`, teve o catálogo conferido e foi restaurado com `pg_restore --exit-on-error --single-transaction` em banco temporário criado a partir de `template0`. Estrutura e resumos dos registros de todas as 18 tabelas preexistentes coincidiram; o banco temporário foi removido. Após a migration, os registros anteriores e concessões de permissões permaneceram iguais. As três tabelas novas estão vazias; a coluna encerrado_em está nula nos contatos anteriores, as sete restrições nomeadas estão validadas e as duas permissões do módulo existem sem novas concessões. Check passou, modelos sem diferenças e nenhuma migration pendente. Não foram inseridos dados fictícios no banco instalado.

Backup local: `.venv/backups/pre_0007_20260928/pre_0007.dump`; evidência e SHA-256 em `verification.json` na mesma pasta. Diretório com ACL restrita ao usuário local e SYSTEM, ignorado pelo Git. Preservar essa pasta antes de recriar/remover a `.venv`; o backup não está no remoto e contém dados sensíveis.

Para recuperação, validar o SHA-256 e restaurar primeiro em outro banco vazio usando PostgreSQL 18, `template0` e `pg_restore --exit-on-error --single-transaction --dbname=<banco_de_recuperacao> <backup>`, com autenticação local protegida. Conferir os dados antes de qualquer troca do banco da aplicação. O backup representa o estado anterior à 0007: para usar o código atual, aplicar a migration no banco recuperado após validação. Não restaurar sobre o banco em uso nem reverter a migration automaticamente; sua reversão remove os dados novos de destinatários. Alterações posteriores ao backup exigem avaliação antes de uma recuperação.


### Usabilidade do painel (28/09/2026)

No cadastro do cliente, as ações de CNPJ, contatos e vínculo da administradora ficam junto ao cabeçalho da respectiva tabela, respeitando as permissões existentes. Ao salvar um vínculo ou CNPJ, o retorno aponta para essa seção do cliente; ao adicionar contato a partir dela e usar Salvar, também retorna ao cliente. Os botões de continuar editando/adicionar outro mantêm seu comportamento. A posição da página é lembrada na mesma aba por até uma hora, com a seção como alternativa quando o armazenamento do navegador não estiver disponível.

Em destinatários, Selecionar todas marca/desmarca as cinco categorias da linha e indica seleção parcial. Parar de receber neste condomínio é uma ação separada: limpa e desabilita as categorias enquanto marcada. Isso não cria reativação de encerramentos já salvos; as regras do serviço permanecem iguais. As opções de seguir a lista mantêm as atualizações da administradora; contatos diretos continuam selecionáveis. Escolher os destinatários deste condomínio ignora a lista da empresa e usa as escolhas locais.

Validação desta alteração: 49 testes SQLite aprovados, check limpo e makemigrations --check sem diferenças. Edge/Playwright em SQLite separado confirmou ações junto às três tabelas, seleção/desmarcação, estado parcial, persistência, encerramento separado, explicação dos modos e retorno com rolagem após salvar vínculo. Capturas inspecionadas; nenhum teste gravou no PostgreSQL instalado. Não houve alteração de schema nem nova validação de concorrência PostgreSQL.


### Teste manual de autenticação Conta Azul (desenvolvimento)

Sonda independente do Django: `backend/contaazul_auth.py`. Não consulta banco, emite documentos ou envia e-mails. Preencher localmente `.venv/contaazul/credenciais.env` com CLIENT_ID, CLIENT_SECRET e REFRESH_TOKEN da mesma aplicação de desenvolvimento; ACCESS_TOKEN inicialmente vazio. Usar valores entre aspas simples se contiverem caracteres especiais. Não colar o campo Authorization: o script calcula o cabeçalho Basic a partir do ID/segredo.

Executar uma única vez, depois de preencher: `.\.venv\Scripts\python.exe backend/contaazul_auth.py`. A renovação consome/rotaciona o Refresh Token; o script salva os dois tokens novos por substituição do arquivo antes de anunciar sucesso. Não editar com uma cópia antiga aberta no editor após a execução. Sem tentativas automáticas, proxies de ambiente ou redirecionamentos HTTP. Sucesso significa autenticação, não comprova acesso aos PDFs nem que a conta conectada é de teste; as credenciais escolhidas determinam a conta.

O diretório local foi criado com ACL para usuário atual e SYSTEM e é ignorado pelo Git. Preservar com segurança antes de recriar .venv. Se ocorrer falha de gravação, verificar localmente `tokens-pendentes.env` e recuperar os valores completos antes de repetir; não compartilhar seu conteúdo. A existência desse arquivo bloqueia outra execução. Interrupções ou falhas de rede podem exigir nova autorização no portal. Esta é uma sonda manual, sem renovação agendada ou integração ao painel.

Validação sem rede/credenciais reais: `.\.venv\Scripts\python.exe -m unittest discover -s backend -p test_contaazul_auth.py` (seis testes). Referência: [renovação oficial](https://developers.contaazul.com/renewingaccesstoken).


#### Primeira autorização, quando só existe o exemplo de Refresh Token

`REFRESH_TOKEN_GERADO` no cURL do portal é um marcador, não um token. Authorization é Basic (ID/segredo codificados), não Refresh Token. Preencher somente CLIENT_ID e CLIENT_SECRET no arquivo local e fechar o editor desse arquivo. Executar `.\.venv\Scripts\python.exe backend/contaazul_auth.py --autorizar` em terminal interativo local.

O teste pede, com entrada oculta, a URL de autorização fornecida pelo portal. Confere se pertence à aplicação configurada, extrai a redirect_uri sem presumir www/barra final e gera novo state. Abre o navegador; usuário entra com a conta de teste e autoriza. Em seguida, colar no terminal o endereço completo de retorno. O teste valida destino/state, extrai o código e troca imediatamente pelos tokens. Não usar o código obtido antes de iniciar esse fluxo: ele não corresponde ao novo state. Não colar URLs/códigos no chat. URLs de retorno com query pré-configurada ou fragmento não são suportadas nesta sonda.

O código não é gravado; novos Access Token e Refresh Token são salvos no arquivo protegido pelo mesmo mecanismo da renovação. O arquivo não deve permanecer aberto com alterações antigas. O navegador padrão recebe o endereço de autorização; o endereço de retorno pode permanecer no histórico dele. O modo sem --autorizar continua sendo renovação. Oito testes simulados aprovados; autorização real ainda não executada pelo script. Referência: [troca inicial oficial](https://developers.contaazul.com/changecode).
