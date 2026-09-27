# Regras de negócio consolidadas

Estas regras registram decisões vigentes. Contatos de administradoras e responsabilidades estão implementados no Django; configuração de destinatários implementada no código e validada em ambiente isolado; implantação da migration 0007 e envio real continuam pendentes. Estado de entrega e problemas ficam em [PROJECT_STATE.md](../PROJECT_STATE.md).

## Cliente, CNPJ e endereço

- O cliente é normalmente o condomínio; a administradora não o substitui. O cliente mantém ID interno permanente mesmo se trocar de CNPJ.
- Todo novo cliente deve possuir CNPJ atual, salvo junto com o cadastro. CNPJ é armazenado somente no histórico, sem máscara, em maiúsculas, com 12 caracteres A–Z/0–9 e dois dígitos finais. Deve ser único no histórico; a operação atual não permite reutilizar CNPJ já registrado, nem no mesmo cliente.
- A troca preserva o cliente e o histórico: início posterior ao último período e não futuro; vínculo anterior termina no dia precedente. Não sobrescreve automaticamente os dados cadastrais.
- Cadastro exige razão social, logradouro, número (aceita S/N), bairro, cidade, UF válida e CEP de oito números. Nome fantasia e complemento são opcionais. A exigência de manter o endereço preenchido após a criação não está consolidada.
- Campos editáveis de CNPJ/CEP nos formulários devem oferecer consulta pública. O operador confere e pode completar/corrigir os dados; falha de consulta permite preenchimento manual. Consultar não salva automaticamente nem comprova situação cadastral.

## Contatos e históricos

- Contato direto pertence a um cliente; nome e início são obrigatórios; função, telefone e e-mail são opcionais. Vários contatos atuais são permitidos, sem exclusividade presumida por função.
- Para substituir pessoa, encerrar o contato anterior e cadastrar outro. Não transferir um contato salvo para outro cliente. Correções de dados/datas são permitidas.
- `data_fim` vazia indica atual; encerramento não pode preceder início. Registros históricos não devem ser apagados automaticamente; consultar atual e até dois anteriores é uma necessidade de apresentação, não limite de armazenamento.
- Não excluir cadastros pelos fluxos atuais do painel/API. Preservar períodos não implica versionar cada correção.

## Administradoras e responsabilidades

- Administradora é independente e pode atender vários condomínios. Cliente pode ter uma administradora atual, anteriores ou nenhuma; não criar registro fictício de “Sem administradora”.
- Razão social da administradora é obrigatória; CNPJ, nome fantasia, telefone e e-mail opcionais. CNPJ informado deve ser normalizado e único entre administradoras.
- Troca de administradora encerra a anterior no dia precedente; novo início deve ser posterior ao último período. Encerramento não precede início; essas operações não aceitam datas futuras. Retorno à mesma empresa é permitido após período encerrado.
- Relação histórica com uma administradora não autoriza automaticamente acesso a informações.
- Direção para contatos de administradora: cadastrar a pessoa uma vez dentro da empresa e associá-la a vários clientes mediante responsabilidades. A função pertence à relação com cada cliente; responsabilidades possuem início/fim. Não criar PESSOA universal nesta etapa.

- Decisão de 26/09/2026, implementada no Django: trocar ou encerrar a administradora encerra automaticamente as responsabilidades abertas daquela empresa para o cliente na mesma data final do vínculo (dia anterior ao novo início, em uma troca). Preservar o histórico, responsabilidades já encerradas e vínculos de outros clientes. Executar em conjunto, sem gravação parcial; rejeitar a operação se produzir fim anterior ao início de uma responsabilidade.

- Decisão de 26/09/2026, implementada no Django: o período da responsabilidade deve estar inteiramente contido em um único vínculo do cliente com a administradora do contato. Não aceitar início ou fim futuros; responsabilidade aberta exige vínculo aberto. Retornos da empresa são períodos separados. Validar também correções de datas e alterações do vínculo para manter essa integridade. Não altera a regra atual de contatos diretos.

- Contatos são reutilizados dentro da administradora. Nome, telefone ou e-mail iguais não provam identidade e não geram bloqueio/fusão automática.
- Não permitir sobreposição de períodos para o mesmo contato, cliente e função (comparação sem espaços externos e sem distinção de maiúsculas). Funções e pessoas diferentes são permitidas. Função permanece livre; principal/alternativo fica para outra etapa.
- Correções de telefone/e-mail se refletem em todos os vínculos, inclusive históricos, sem versionamento desses dados. Substituir uma pessoa exige encerrar sua responsabilidade e cadastrar outra. Administradora do contato e contato/cliente da responsabilidade não são transferíveis após salvar.

## Destinatários de documentos e comunicações

- O vínculo do contato com o condomínio, no escopo definido pelo usuário, destina-se exclusivamente ao recebimento de boletos, notas fiscais, laudos, comunicados e cobranças. Para cada contato naquele condomínio, selecionar cada categoria independentemente, isolada ou em qualquer combinação. Não presumir que a seleção de uma categoria habilite as demais. Esta decisão substitui a regra anterior de envio obrigatório de boleto e nota fiscal juntos ao mesmo conjunto de destinatários; não altera as regras dos demais cadastros.
- Um cliente pode ter múltiplos destinatários, selecionados entre contatos existentes, sem cadastro avulso de nome/e-mail. Todos são tratados igualmente como destinatários, sem distinção de principal/copia ou Para/Cópia no cadastro. Essa decisão substitui a classificação anterior; não define a forma técnica de entrega dos futuros envios. A vigência segue a decisão de efeito imediato abaixo.
- Não presumir que um contato ou responsável financeiro seja automaticamente destinatário de faturamento. O conjunto de envio deve ser cadastrado explicitamente.

### Decisões de 27/09/2026 — implementadas, implantação pendente

- Destinatários podem ser contatos do próprio cliente, da administradora ou de ambos simultaneamente.
- Selecionar somente contatos já cadastrados. Para um novo e-mail de envio, cadastrar primeiro um novo contato; não manter e-mail avulso no faturamento.
- A administradora pode definir contatos padrão de faturamento para todos os seus clientes vinculados, inclusive um contato com e-mail único para esse fim. Essa definição deve ser explícita; não inferir destinatários pela função do contato.
- Por cliente, permitir usar os padrões da administradora, acrescentar contatos específicos ou substituir os padrões por contatos específicos, conforme solicitação do cliente ou da administradora. Os destinatários do próprio cliente podem receber em conjunto.
- O padrão da administradora é único para todas as categorias. Usar, complementar ou substituir esse padrão é uma escolha por cliente, sem substituição separada por categoria; mudou o padrão, a mudança vale para todas as categorias nos clientes que o utilizam. A seleção das categorias recebidas por cada contato permanece independente.
- Alterações nos contatos padrão se refletem automaticamente em todos os clientes que utilizam esse padrão, inclusive quando há contatos específicos adicionais. Clientes que substituem o padrão usam sua seleção específica.
- Na troca de administradora, os destinatários da empresa anterior deixam automaticamente de receber o faturamento daquele cliente. Os destinatários do próprio cliente permanecem.
- A ausência de e-mail não impede selecionar um contato como destinatário de faturamento: ele pode possuir telefone para futuro envio por WhatsApp. Essa decisão não implementa o canal WhatsApp nem exige e-mail para o cadastro de destinatários.
- Contatos encerrados deixam automaticamente de receber documentos e comunicações; preservar o histórico. Para contatos da administradora, permitir encerrar a participação apenas em um condomínio ou encerrar o contato na empresa inteira, retirando-o de todos os destinatários. O encerramento local também se aplica a contatos herdados do padrão, sem afetar outros condomínios.
- Alterações de destinatários, categorias e configuração do padrão passam a valer imediatamente ao salvar, preservando a configuração anterior no histórico. Agendamento de mudanças fica fora desta etapa.
- Configuração implementada no painel/API e validada em ambiente isolado. Migration 0007 ainda não aplicada ao banco instalado; não há envio real de documentos.

As questões de negócio levantadas nesta rodada foram respondidas. O [desenho técnico e plano incremental](DESTINATARIOS_COMUNICACOES.md) foi elaborado com base nos modelos e schema existentes; foi implementado com os limites e resultados registrados no documento. Principal/alternativo de responsabilidades permanece adiado.

## Dez perguntas operacionais

1. Qual é o CNPJ atual do condomínio?
2. Qual é o endereço?
3. Quem é o síndico atual?
4. Qual é o telefone do síndico?
5. Para quais e-mails devem ser enviados boleto e nota fiscal?
6. Qual administradora cuida do condomínio?
7. Quem é o responsável pelo contas a pagar?
8. Quais condomínios estão sob responsabilidade de determinada pessoa?
9. Quais eram os contatos anteriores?
10. Quem é o contato alternativo caso o principal não responda?

Essas perguntas são objetivos operacionais; não significam que todas já sejam respondidas. A avaliação da entrega está na [auditoria preservada](../AUDITORIA_ARQUITETURA.md).
