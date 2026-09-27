# Contatos de administradora e responsabilidades — critérios de aceitação

Data: 26/09/2026. Todas as decisões abaixo foram aprovadas pelo usuário. Implementação no Django concluída; 37 testes passaram em SQLite. Validação concluída em 27/09/2026: oito verificações PostgreSQL isoladas, inspeção visual no Edge e migration 0006 aplicada no banco instalado.

Referências: [regras vigentes](REGRAS_NEGOCIO.md), [entidades](ARQUITETURA.md#entidades-e-relacionamentos) e [estado do projeto](../PROJECT_STATE.md).

## Evidência atual

`database/schema.sql` já contém contatos_administradora (empresa, nome, telefone, e-mail e criação) e responsabilidades (contato, cliente, função, início e fim). Há chaves estrangeiras e restrição de fim não anterior ao início. Não há unicidade de pessoas/responsabilidades, prioridade ou validação do período contra o vínculo cliente/administradora.

Modelos, API e painel implementam as duas entidades. A troca/encerramento da administradora encerra responsabilidades abertas na mesma transação. Validações de contenção temporal e sobreposição ficam na aplicação, sob bloqueio do cliente em PostgreSQL; SQL direto e operações bulk podem contorná-las. A migration 0006 registra modelos não gerenciados e não recria tabelas.

## Critérios sustentados pelas decisões vigentes

1. Cadastrar um contato dentro de uma administradora e reutilizar seu ID em responsabilidades de vários clientes, sem cadastrar novamente a pessoa para cada condomínio e sem criar PESSOA universal.
2. Registrar a função na responsabilidade: o mesmo contato pode exercer funções diferentes em clientes diferentes.
3. Cada responsabilidade associa um contato a um cliente e possui início e fim opcional. Rejeitar fim anterior ao início, conforme a restrição SQL existente.
4. Preservar registros encerrados e permitir consultar os anteriores, sem exclusão automática nem limite de dois registros armazenados.
5. Não cadastrar destinatários de faturamento automaticamente ao criar contatos ou responsabilidades.
6. Preservar contatos diretos e funcionalidades existentes. O módulo de destinatários fica para a etapa seguinte.
7. Decisão aprovada pelo usuário em 26/09/2026: trocar ou encerrar a administradora encerra automaticamente as responsabilidades abertas da empresa anterior para aquele cliente, na mesma data final do vínculo, preservando o histórico. Na troca, essa data é o dia anterior ao início da nova empresa; no encerramento, é a data informada. Outros clientes e responsabilidades já encerradas permanecem intactos. A operação deve ser atômica e rejeitada integralmente se o encerramento resultar em fim anterior ao início de alguma responsabilidade.

8. Decisão aprovada pelo usuário em 26/09/2026: o período inteiro da responsabilidade deve estar contido em um único período de vínculo do cliente com a administradora do contato. Início e fim informados não podem ser futuros. Responsabilidade aberta exige vínculo aberto; um retorno da administradora não autoriza atravessar o intervalo sem vínculo. Aplicar também às correções de datas, preservando a validade das responsabilidades existentes ao alterar o vínculo da empresa. Esta decisão não altera contatos diretos.

Exemplo: Ana é cadastrada uma vez na administradora Alfa e vinculada ao condomínio Sol como responsável financeiro e ao condomínio Mar como gerente. Encerrar sua responsabilidade no Sol preserva o histórico e não encerra sua responsabilidade no Mar.

## Entrega operacional aprovada e implementada

- Painel Django e API permitem cadastrar, consultar e corrigir contatos; cadastrar, consultar e encerrar responsabilidades, sem exclusão. Nome e administradora são obrigatórios; telefone e e-mail opcionais, conforme o schema. Função e início são obrigatórios.
- Consultar contatos por administradora/nome e responsabilidades por cliente, contato e situação, permitindo responder quais condomínios uma pessoa atende e quem exerce determinada função.
- Manter as permissões por modelo já usadas no projeto; detalhar e testar consultas e mutações no desenho técnico. Vínculo histórico não concede acesso automaticamente.
- Correção de telefone/e-mail altera o cadastro compartilhado mostrado em todos os vínculos, inclusive históricos; não cria versões dos dados da pessoa. Trocar a pessoa exige outro contato e encerramento/criação de responsabilidades. Não transferir o contato salvo entre administradoras nem trocar contato/cliente de uma responsabilidade já salva.

## Decisões complementares aprovadas

| Tema | Decisão | Consequência |
| --- | --- | --- |
| Duplicidade de pessoas | Selecionar/reutilizar contato existente; não presumir identidade por nome, telefone ou e-mail iguais | Homônimos e canais compartilhados continuam possíveis; nenhuma fusão automática |
| Duplicidade de responsabilidades | Impedir sobreposição para o mesmo contato, cliente e função, incluindo períodos encerrados; permitir funções diferentes e pessoas diferentes | Comparação com espaços externos removidos e casefold; concorrência PostgreSQL testada em banco isolado |
| Função e prioridade | Manter função livre e múltiplos responsáveis, deixando principal/alternativo e função estruturada para decisão posterior | Não garante identificação inequívoca de síndico nem contato alternativo nesta entrega |
| Correções e histórico | Adotar correção compartilhada e relações fixas descritas acima; rejeitar correções que violem períodos ou sobreposição | Preserva vínculos, mas não oferece auditoria imutável dos dados pessoais |

As quatro decisões complementares foram aprovadas após explicação ao usuário. Principal/alternativo e funções estruturadas permanecem fora desta entrega.

## Validação e limites

- SQLite: cadastros, reutilização entre clientes, campos obrigatórios, datas, filtros, permissões, preservação dos encerrados, ausência de exclusão e regressão dos fluxos existentes.
- PostgreSQL: restrições reais, migrations incrementais e concorrência nas operações de atribuição/troca que forem aprovadas; SQLite não comprova esses pontos.
- Cenários adicionais: retorno da mesma administradora em novo período, troca retroativa anterior ao início de uma responsabilidade, duplicidade concorrente e correção de dados compartilhados.
- Executados 37 testes em SQLite descartável, incluindo os 29 anteriores; todos passaram. `makemigrations --check --dry-run` sem diferenças. Oito verificações PostgreSQL passaram, incluindo três cenários concorrentes. Fluxos visuais conferidos no Edge em banco isolado. Migration 0006 aplicada no banco instalado; conteúdo das oito tabelas de domínio comparado antes/depois e preservado. Nunca reaplicar schema em banco existente.
