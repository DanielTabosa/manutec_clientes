# Backend Manutec Clientes

Primeira etapa: cadastro, consulta, pesquisa e edicao dos dados basicos de
clientes. Python 3.12, Django 5.2 LTS, DRF 3.16 e PostgreSQL 18.

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

O modelo `Cliente` mapeia a tabela `clientes` com `managed=False`.
A migracao inicial registra o modelo no Django, mas nao cria, altera ou
exclui essa tabela. As outras sete tabelas ainda nao estao mapeadas.
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
Os demais relacionamentos historicos serao implementados posteriormente.

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
