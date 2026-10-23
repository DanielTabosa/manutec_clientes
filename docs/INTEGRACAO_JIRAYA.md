# Integração com o Jiraya — contrato da API de leitura

**Situação: contrato vigente (v1).** Aprovado pelo usuário em 23/10/2026, junto com as decisões de pessoa física e endereços registradas em [regras de negócio](REGRAS_NEGOCIO.md). Implementado em `backend/clientes/integracao.py` (rotas em `backend/config/urls.py`). Mudanças posteriores seguem a seção [Versionamento](#versionamento).

## Contexto e decisão

Decisão do usuário em 24/10/2026 (D-66 do Jiraya): o **manutec-clientes é a fonte única de clientes**. O Jiraya nunca cadastra nem altera cliente; só consulta por esta API e guarda localmente o **id permanente** do cliente (e o id do endereço de atendimento) para ligar equipamentos e ordens de serviço. Não há banco compartilhado. No futuro os sistemas serão unidos, por isso os ids daqui são a chave.

Fluxo esperado no Jiraya:

1. O operador digita parte do nome, da fantasia ou do documento → o Jiraya chama a **busca** e mostra até 10 sugestões.
2. Ao escolher uma sugestão → o Jiraya chama o **detalhe** e grava `cliente.id` e o `endereco.id` escolhido.
3. Periodicamente (ou ao abrir uma OS) → o Jiraya usa **alterações** ou compara `atualizado_em` para atualizar o que exibe.

## Conexão e autenticação

- URL base: `https://<servidor-do-manutec-clientes>/api/integracao/v1/` (em desenvolvimento, `http://127.0.0.1:8000/api/integracao/v1/`). Em produção, somente HTTPS.
- Cabeçalho obrigatório em toda chamada: `Authorization: Bearer <token>`.
- O token é um segredo de serviço (sistema a sistema), sem usuário nem sessão. No manutec-clientes fica na variável de ambiente `DJANGO_INTEGRACAO_JIRAYA_TOKEN` (mínimo de 32 caracteres); no Jiraya, na configuração equivalente dele. Nunca no repositório, em URL ou em log.
- Comparação em tempo constante. Variável vazia ou ausente = integração desligada (toda chamada recebe 401).
- O token **só** vale para as rotas deste documento e **só** para leitura (`GET`/`HEAD`). Não dá acesso ao painel, ao `/admin/`, a `/api/v1/` nem a nenhuma escrita. Inversamente, sessão de usuário do painel não acessa estas rotas.
- Troca do token: gerar um novo, atualizar a variável aqui e a configuração do Jiraya, reiniciar ambos. Durante a troca as chamadas com o token antigo recebem 401.

## Convenções

- JSON UTF-8. Nomes de campo em português, `snake_case`, sem acento.
- Datas e horas em ISO 8601 com fuso de Fortaleza: `2026-10-24T10:15:30-03:00`; datas puras como `2026-10-24`. Quando houver fração de segundo, ela vem junto (`2026-10-24T10:15:30.123456-03:00`); o Jiraya deve guardar o valor exatamente como recebido. Em parâmetros de URL, codificar o valor (o `+` de um deslocamento positivo vira espaço se não for codificado).
- Campo opcional sem valor vem como `null` (nunca omitido).
- Documento sem máscara: CNPJ com 14 caracteres (já preparado para o CNPJ alfanumérico), CPF com 11 dígitos. A busca aceita com ou sem máscara.
- Ids são inteiros permanentes; nunca são reaproveitados. Cliente e endereço não são apagados: deixam de valer pela situação `ativo: false`.
- O Jiraya deve **ignorar campos desconhecidos** (permite acrescentar campos sem nova versão).

## Rotas

### 1. Busca para sugestões

`GET /api/integracao/v1/clientes/?busca=<texto>&limite=10&pagina=1&situacao=ativo`

| Parâmetro | Regra |
| --- | --- |
| `busca` | Obrigatório, mínimo 2 caracteres. Procura em nome (razão social ou nome da pessoa), nome fantasia e documento (atual e anteriores, comparando só letras e números). Sem diferenciar maiúsculas e acentos. |
| `limite` | Opcional, padrão 10, máximo 20. |
| `pagina` | Opcional, padrão 1. |
| `situacao` | Opcional: `ativo` (padrão), `inativo` ou `todos`. |

Ordenação: primeiro quem começa com o texto buscado, depois os demais, por nome e id.

```json
{
  "resultados": [
    {
      "id": 412,
      "tipo_pessoa": "PJ",
      "documento": {"tipo": "CNPJ", "numero": "12345678000190"},
      "nome": "CONDOMINIO EDIFICIO SOLAR DAS PALMEIRAS",
      "nome_fantasia": "Solar das Palmeiras",
      "ativo": true,
      "cidade": "Fortaleza",
      "estado": "CE",
      "atualizado_em": "2026-10-24T10:15:30-03:00"
    }
  ],
  "pagina": 1,
  "limite": 10,
  "total": 1,
  "proxima": null
}
```

`cidade` e `estado` são os do endereço principal, só para distinguir homônimos na lista de sugestões. `proxima` é a URL completa da página seguinte ou `null`.

### 2. Detalhe do cliente

`GET /api/integracao/v1/clientes/{id}/`

Devolve o cliente, inclusive inativo (o Jiraya pode ter OS antigas apontando para ele).

```json
{
  "id": 412,
  "tipo_pessoa": "PJ",
  "documento": {"tipo": "CNPJ", "numero": "12345678000190"},
  "nome": "CONDOMINIO EDIFICIO SOLAR DAS PALMEIRAS",
  "nome_fantasia": "Solar das Palmeiras",
  "ativo": true,
  "enderecos": [
    {
      "id": 980,
      "descricao": "Matriz",
      "principal": true,
      "ativo": true,
      "logradouro": "Rua das Flores",
      "numero": "100",
      "complemento": null,
      "bairro": "Aldeota",
      "cidade": "Fortaleza",
      "estado": "CE",
      "cep": "60150000"
    }
  ],
  "contatos": [
    {
      "id": 77,
      "nome": "Maria Souza",
      "funcao": "Síndica",
      "telefone": "85999990000",
      "email": "maria@exemplo.com.br"
    }
  ],
  "criado_em": "2026-10-14T09:00:00-03:00",
  "atualizado_em": "2026-10-24T10:15:30-03:00"
}
```

- Pessoa física: `tipo_pessoa` = `"PF"`, `documento.tipo` = `"CPF"`, `nome` = nome completo, `nome_fantasia` = `null`.
- `documento` é sempre o documento **atual**. O histórico de CNPJ não é exposto nesta versão.
- `enderecos`: todos os endereços de atendimento, inclusive inativos (`ativo: false`), principal primeiro. Endereço inativo não deve ser oferecido para OS nova, mas continua válido para as antigas. Bloco, torre ou apartamento **não** são endereço: ficam no complemento ou na OS do Jiraya.
- `contatos`: somente os contatos vigentes do condomínio/cliente (sem os encerrados e sem os contatos da administradora).
- Um cliente importado por CSV pode ainda não ter endereço: `enderecos` vem `[]`.

### 3. Alterações desde um momento

`GET /api/integracao/v1/clientes/alteracoes/?desde=2026-10-24T10:00:00-03:00&limite=100`

Lista, em ordem crescente de `atualizado_em` e `id`, os clientes (ativos e inativos) cujo `atualizado_em` é posterior a `desde`. Mesmo formato de item da busca. `limite` padrão 100, máximo 200.

Paginação por cursor, estável mesmo com alterações acontecendo durante a leitura: a resposta traz `proxima` com `desde` e `apos_id` do último item; o Jiraya segue `proxima` até vir `null` e guarda o `atualizado_em` do último item para a próxima rodada.

```json
{
  "resultados": [{"id": 412, "tipo_pessoa": "PJ", "...": "..."}],
  "limite": 100,
  "proxima": "https://.../api/integracao/v1/clientes/alteracoes/?desde=2026-10-24T10%3A15%3A30-03%3A00&apos_id=412&limite=100"
}
```

### Como o Jiraya detecta mudanças

`atualizado_em` do cliente muda sempre que mudar **qualquer coisa que o detalhe devolve**: nome, fantasia, situação, documento atual (troca de CNPJ), qualquer endereço (inclusão, edição, desativação, troca do principal) ou qualquer contato (inclusão, edição, encerramento). Assim basta comparar `atualizado_em` para saber se o detalhe guardado está velho.

Limite conhecido: alteração feita por SQL direto no banco não renova `atualizado_em` (já é assim hoje). Os fluxos do painel, da API e da importação CSV renovam.

## Erros

Formato único:

```json
{"erro": {"codigo": "parametro_invalido", "mensagem": "Informe ao menos 2 caracteres em busca.", "campo": "busca"}}
```

| HTTP | `codigo` | Quando |
| --- | --- | --- |
| 400 | `parametro_invalido` | Parâmetro ausente, curto, fora do limite ou data inválida (`campo` indica qual). |
| 401 | `nao_autenticado` | Cabeçalho ausente, token errado ou integração desligada. Resposta com `WWW-Authenticate: Bearer`. |
| 404 | `nao_encontrado` | Cliente inexistente ou rota desconhecida dentro do prefixo. |
| 405 | `metodo_nao_permitido` | Qualquer método além de `GET`/`HEAD`. |
| 500 | `erro_interno` | Falha inesperada; o Jiraya pode tentar de novo depois. |

O Jiraya deve tratar 401 como configuração errada (não repetir em laço) e 5xx/falha de rede como temporários, mantendo os dados que já tem.

## Versionamento

- Versão no caminho: `/api/integracao/v1/`.
- Dentro da v1 só entram mudanças compatíveis: campos novos, valores novos em `situacao`, rotas novas.
- Remover ou renomear campo, mudar tipo ou significado → nova versão (`/v2/`), com a v1 mantida em paralelo até o Jiraya migrar, combinado entre as partes.
- Este documento é a referência; o histórico de mudanças do contrato fica no fim dele.

## Fora desta versão

Escrita de qualquer tipo, administradora, contratos, histórico de CNPJ, contatos encerrados, destinatários de documentos e equipamentos (que ficam no Jiraya). Webhooks/avisos ativos para o Jiraya também ficam para depois; a detecção é por consulta.

## Histórico do contrato

- 23/10/2026 — proposta inicial (v1).
- 23/10/2026 — aprovada pelo usuário e implementada; esclarecida a fração de segundo em `atualizado_em`.
