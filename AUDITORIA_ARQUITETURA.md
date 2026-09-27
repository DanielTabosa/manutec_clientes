# AUDITORIA — ARQUITETURA ORIGINAL × IMPLEMENTAÇÃO ATUAL

A arquitetura está **implementada no núcleo cadastral, mas ainda incompleta na gestão de pessoas, responsabilidades e faturamento**. Das oito tabelas previstas no SQL, **cinco possuem modelos e fluxos no Django**; três permanecem somente na estrutura SQL. Essa contagem não equivale a um percentual de conclusão.

Auditoria baseada na leitura do contexto, dois READMEs, schema, script SQL de testes, backend, migrations, testes, templates e JavaScript. **Não alterei arquivos, executei migrations nem fiz commits.** Não executei testes nesta auditoria nem confirmei o estado do banco instalado; “implementado” abaixo descreve funcionalidades presentes no código.

> Nota da exportação: o parágrafo acima descreve a execução da auditoria original. Este arquivo foi criado posteriormente, a pedido do usuário, para registrar integralmente o relatório.

### IMPLEMENTADO

- **Clientes:** ID interno permanente, cadastro, edição, endereço, pesquisa, paginação e permissões no painel/API.
- **CNPJ atual e histórico:** cadastro obrigatório junto com o cliente, troca transacional, encerramento do anterior e consulta de atual/histórico. A migration 0003 acrescenta proteção PostgreSQL contra cliente sem CNPJ atual.
- **Contatos dos condomínios:** nome, função, telefone, e-mail, vínculo com cliente e datas; cadastro, edição, encerramento e filtros de vigência. O cliente do contato não pode ser transferido pelo painel/API.
- **Administradoras:** cadastro independente, edição, pesquisa, telefone e e-mail.
- **Histórico de administradoras:** vincular, trocar, encerrar e retornar a uma administradora anterior; uma empresa atende vários clientes e o cliente pode ficar sem administradora.
- **Proteção dos históricos nos fluxos existentes:** exclusão indisponível no painel/API; históricos de CNPJ e administradora somente para consulta.
- **Consultas CNPJ/CEP:** preenchimento assistido nos formulários, com conferência e tratamento de falhas.
- **Testes:** 29 métodos de teste cobrindo API, painel, permissões e regras dos módulos implementados.

Evidências principais: [modelos](backend/clientes/models.py), [serviços](backend/clientes/services.py), [API](backend/clientes/views.py) e [testes](backend/clientes/tests.py).

### PARCIAL

- **Pessoa e vínculos:** `Contato` reúne pessoa e vínculo em um registro por cliente; não existe identidade compartilhada de pessoa entre condomínios.
- **Telefones/e-mails:** há um campo de cada por contato ou administradora, sem coleção de canais por pessoa.
- **Identificação do síndico:** possível pela função cadastrada, mas ela é texto livre e opcional; não há seleção inequívoca de “síndico atual”.
- **Preservação dos contatos:** registros encerrados permanecem, mas nome, função, telefone, e-mail e datas podem ser sobrescritos; não existe versionamento dessas alterações.
- **Consulta histórica:** contatos diretos têm histórico completo, mas a apresentação compacta dos dois anteriores ainda não existe.
- **Validação PostgreSQL:** há script SQL e comando específico de verificação, mas os 29 testes usam SQLite e não validam os triggers PostgreSQL.

### NÃO IMPLEMENTADO

As tabelas abaixo existem no [schema](database/schema.sql), mas não possuem modelos, API nem telas Django:

- **`contatos_administradora`:** pessoas da administradora.
- **`responsabilidades`:** pessoa responsável por cada cliente, função e histórico.
- **`destinatarios_faturamento`:** múltiplos e-mails, principal/cópia e vigência.

Também não existe regra estruturada de **contato principal e alternativo**, nem consulta confiável de todos os clientes sob responsabilidade de uma mesma pessoa.

### DIVERGÊNCIAS

| Diferença encontrada | Classificação |
|---|---|
| Cliente usa ID permanente e CNPJ separado em histórico. | **Evolução arquitetural intencional**, documentada e implementada; não é erro. |
| Instalação depende de `schema.sql` e migrations; os modelos são `managed=False`. O schema sozinho não inclui a obrigatoriedade de CNPJ atual. | **Evolução arquitetural intencional**, explicada no README. |
| README e checkpoints antigos dizem que sete tabelas não foram mapeadas ou que administradoras ainda estão pendentes. Atualmente faltam três. | **Documentação desatualizada**, embora checkpoints posteriores registrem a evolução. |
| O conceito de pessoa compartilhada não aparece como entidade própria; o schema adotou contatos diretamente ligados ao cliente. | **Precisa de decisão humana:** manter esse desenho ou unificar pessoas antes dos próximos módulos. Não há evidência de que seja defeito. |
| Contatos aceitam início futuro e ainda são marcados como vigentes quando `data_fim` está vazia. | **Possível problema:** segue a convenção documentada de vigência, mas pode apresentar alguém que ainda não assumiu como contato atual. |
| Endereço é obrigatório ao cadastrar, mas pode ser esvaziado na edição. | **Possível problema**, caso a intenção seja manter endereço obrigatório durante toda a vida do cadastro. |
| “Preservar histórico” mantém registros, mas permite sobrescrever dados de contatos antigos. | **Precisa de decisão humana:** correções são expressamente permitidas; histórico imutável de alterações seria outro requisito. |
| O script SQL anuncia sucesso sem forçar os triggers diferidos; seu segundo cliente fica sem CNPJ e tudo termina em rollback. | **Documentação/teste desatualizado:** continua útil para restrições originais, mas não comprova a regra posterior de CNPJ obrigatório. |

### 10 PERGUNTAS

| # | Pergunta | Situação e explicação |
|---|---|---|
| 1 | Qual é o CNPJ atual? | **RESPONDIDA HOJE** — a rota de CNPJ retorna explicitamente o registro atual e o histórico. |
| 2 | Qual é o endereço? | **RESPONDIDA HOJE** — os campos estão disponíveis no cadastro e na API. |
| 3 | Quem é o síndico atual? | **PARCIALMENTE** — é possível consultar contatos vigentes e sua função, mas sem padronização ou identificação inequívoca. |
| 4 | Qual é o telefone do síndico? | **PARCIALMENTE** — existe telefone no contato, porém é opcional e depende da identificação correta do síndico. |
| 5 | Para quais e-mails enviar boleto e nota? | **AINDA NÃO** — destinatários de faturamento existem somente no SQL. |
| 6 | Qual administradora cuida do condomínio? | **RESPONDIDA HOJE** — painel e API identificam a administradora atual ou sua ausência. |
| 7 | Quem responde pelo contas a pagar? | **PARCIALMENTE** — um contato direto pode ter essa função escrita, mas falta a responsabilidade formal de uma pessoa da administradora pelo cliente. |
| 8 | Quais condomínios determinada pessoa atende? | **AINDA NÃO** — falta identidade compartilhada e vínculo de responsabilidade; pesquisar nomes não resolve isso com segurança. |
| 9 | Quais eram os contatos anteriores? | **PARCIALMENTE** — contatos diretos encerrados são consultáveis; pessoas e responsabilidades das administradoras ainda não. |
| 10 | Quem é o contato alternativo? | **PARCIALMENTE** — vários contatos podem coexistir, mas nenhum campo determina prioridade ou substituição. |

### PRÓXIMA ETAPA

A próxima implementação lógica é **contatos das administradoras e responsabilidades por cliente**, aproveitando administradoras e vínculos já existentes.

Antes, cabe definir apenas a identidade das pessoas: cadastro por administradora, conforme o schema atual, ou pessoa compartilhada entre contextos. Essa etapa deve estabelecer função, vigência e prioridade de contato. Depois, implementar **destinatários de faturamento**, sem presumir que todo responsável financeiro deva receber documentos.
