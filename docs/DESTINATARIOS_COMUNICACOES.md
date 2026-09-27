# Destinatários de documentos e comunicações — implementação e desenho

Referência: 27/09/2026. Implementado no código e validado em ambiente isolado, com base nas [regras aprovadas](REGRAS_NEGOCIO.md). Migration 0007 criada, ainda não aplicada ao banco instalado. O desenho abaixo registra a estrutura adotada; a tabela legada não foi convertida.

## Entrega e limites verificados

- Modelos gerenciados em destinatarios_models.py; serviços em destinatarios.py; painel/API em módulos próprios. Encerramento global usa encerrado_em no modelo legado, criado fisicamente pela migration 0007. Contato direto encerrado registra revisão; troca da empresa registra revisão quando há configuração do cliente.
- GET/PUT de configuração por cliente/administradora, histórico paginado e POST de encerramento global. Detalhes e permissões no [README do backend](../backend/README.md).
- 48 testes SQLite aprovados (37 anteriores e 11 novos). PostgreSQL descartável: 11 verificações aprovadas, incluindo preservação de destinatário legado através da migration, restrições reais, edição concorrente e seleção bloqueada pelo encerramento global. Os três testes concorrentes anteriores também passaram. Nem todos os cenários previstos abaixo foram exercitados concorrentemente.
- Edge confirmou contato sem e-mail, duas categorias, encerramento local, preservação de outro cliente e propagação de alteração do padrão. Capturas inspecionadas. Servidor e banco descartável removidos.
- Histórico reúne revisões do cliente e dos padrões das empresas vinculadas, identificando sua origem, mais os últimos 25 encerramentos globais pertinentes. Não reconstrói automaticamente o conjunto efetivo em uma data passada: uma revisão de empresa exibida não comprova adoção pelo cliente naquele momento. Não há versionamento dos dados pessoais dos contatos ou histórico de envios.
- Limites: SQL direto/bulk contorna validações de pertencimento/encerramento; sem reativação local automática; padrão só reflete contatos globalmente ativos. Integrações e envio continuam fora da entrega. Banco instalado permanece na migration 0006 até implantação da 0007.


## Escopo da primeira entrega

Configurar e consultar quem recebe boletos, notas fiscais, laudos, comunicados e cobranças por condomínio. Usar contatos existentes do condomínio e da administradora, inclusive simultaneamente. Cada contato pode receber qualquer combinação das cinco categorias. Não exigir e-mail nem distinguir principal/cópia. Não construir envio, fila, integrações, provedor de e-mail ou WhatsApp nesta entrega.

Usar, complementar ou substituir o padrão da administradora é uma escolha única por condomínio, válida para todas as categorias. Isso não seleciona automaticamente todas as categorias para cada contato: a seleção individual permanece. Alterações têm efeito imediato ao salvar e preservam a configuração anterior; sem agendamento.

## Evidência no código atual

- `backend/clientes/models.py`: Contato pertence ao cliente e possui data_fim; ContatoAdministradora pertence à empresa e não possui encerramento próprio. Responsabilidade possui cliente, função livre e início/fim.
- `backend/clientes/services.py`: alterar_administradora bloqueia o cliente e encerra responsabilidades na mesma transação. A data de negócio do vínculo pode ser passada; não deve ser confundida com o instante de alteração da configuração de destinatários.
- `database/schema.sql`: destinatarios_faturamento guarda nome/e-mail avulsos, exige e-mail e principal/copia e não referencia contatos. Não há modelo Django para essa tabela.
- Painel Django e API já existem. Os sete modelos atuais de domínio são managed=False; não transformar essas tabelas em gerenciadas nem reaplicar o schema.

## Persistência adotada

Manter os cadastros atuais. Para a nova configuração, usar três tabelas gerenciadas pelo Django, criadas pela migration incremental 0007. Não usar PESSOA universal, GenericForeignKey, novas funções estruturadas ou um catálogo editável de categorias.

| Registro proposto | Conteúdo e finalidade |
| --- | --- |
| ConfiguracaoDestinatarios | Exatamente um titular: cliente ou administradora. Um registro por titular, usado também como referência estável para suas revisões. |
| RevisaoDestinatarios | Configuração, número sequencial, registrado_em e autor; modo usar/complementar/substituir e referência ao vínculo ClienteAdministradora quando a configuração for de cliente com administradora. Revisões anteriores ficam somente para consulta. |
| ItemDestinatario | Revisão, exatamente um contato direto ou contato de administradora, indicação de encerramento local quando aplicável e cinco indicadores booleanos: boleto, nota fiscal, laudo, comunicado e cobrança. |

Categorias fixas em cinco campos evitam uma tabela de catálogo e relações extras para um conjunto pequeno já decidido. Referenciar o contato, sem copiar nome, e-mail ou telefone para a configuração operacional. Não criar tipo principal/copia.

A revisão mais recente, ordenada pelo número, representa o estado salvo. Uma alteração efetiva cria uma revisão completa com seus itens na mesma transação; salvar sem mudança não cria histórico vazio. Histórico registra seleção, categorias, modo e vínculo, não entrega de mensagens nem versões de dados cadastrais do contato. Correções de nome/telefone/e-mail mantêm a semântica atual dos cadastros.

### Integridade

- Banco: FKs protegidas; titular exclusivo cliente/administradora; unicidade por titular e por configuração/número da revisão; contato exclusivo em cada item; unicidade de cada contato na revisão; pelo menos uma categoria selecionada por item de recebimento; item de encerramento local possui contato de administradora e nenhuma categoria.
- Aplicação: contato direto pertence ao cliente; contato de administradora pertence à empresa do padrão ou à empresa do vínculo atual do cliente; vínculo pertence ao cliente da configuração; campos de modo/vínculo só cabem no escopo de cliente. Contato encerrado não entra no resultado efetivo.
- Remover um item de uma nova revisão não apaga a revisão anterior. Uma configuração sem destinatários deve ser apresentada explicitamente, sem destinatário fictício ou preenchimento automático. Essa possibilidade técnica não significa aprovação para enviar documentos sem destinatários.
- As condições entre várias tabelas exigem validação transacional; FKs isoladas não comprovam pertencimento. Documentar esse limite para SQL direto/bulk.

## Resolução do conjunto atual

1. Ler a configuração atual do condomínio e seu vínculo atual com a administradora.
2. Manter os contatos diretos selecionados e elegíveis do próprio condomínio.
3. Se o modo for usar padrão, obter os itens da revisão atual do padrão da empresa. Se for complementar, somar os itens específicos. Se for substituir, usar somente os específicos da empresa.
4. Aplicar as categorias selecionadas em cada item. Unificar ocorrências do mesmo contato pela união das categorias, sem fundir pessoas por nome, e-mail ou telefone.
5. Excluir os contatos encerrados globalmente, os encerramentos locais daquele condomínio e os itens da administradora cujo vínculo já terminou. O encerramento local prevalece sobre o padrão e sobre a seleção específica, sem alterar outros condomínios. Exibir a origem de cada destinatário: condomínio, padrão ou específico.

O padrão é consultado por referência, sem copiar seus itens para cada condomínio. Assim, uma mudança atinge imediatamente os clientes que o usam; quem substitui o padrão mantém sua seleção específica. Não criar responsabilidades fictícias para distribuir o padrão a todos os clientes.

As seleções específicas da administradora devem ficar associadas ao período ClienteAdministradora, para que o retorno futuro da mesma empresa não reative uma seleção antiga silenciosamente. A troca preserva os destinatários diretos e inicia a configuração da nova empresa pelo padrão; a tela permite complementar ou substituir com os contatos informados para o novo vínculo.

## Transações e histórico

Serviços compartilhados por painel e API devem salvar revisão/itens atomicamente. Edição do condomínio e troca da administradora usam o bloqueio de Cliente já existente. Alteração do padrão bloqueia Administradora. Operações que precisarem dos dois devem seguir sempre a ordem Cliente, depois Administradora; alteração de padrão não deve bloquear cada cliente em cascata. Validar essa ordem com os caminhos efetivamente implementados.

Usar número de revisão como controle de edição: se outro operador já alterou a configuração, rejeitar gravação desatualizada e pedir recarregamento. O instante da revisão é atribuído pelo servidor após adquirir os bloqueios; não aceitar data escolhida pelo operador. Manter o padrão local atual de timestamps do projeto.

Troca/encerramento da administradora e encerramento de contato precisam integrar a atualização de elegibilidade e o registro histórico, tanto no painel quanto na API, sem depender apenas de log do admin. Histórico do condomínio deve mostrar também alterações no padrão herdado, por referência às revisões da empresa, sem duplicar registros para todos os clientes. Diferenciar data do vínculo comercial e momento em que a alteração foi registrada; não prometer reconstrução de dados cadastrais sobrescritos ou entregas passadas.

## Telas no painel existente

- No condomínio, acesso **Destinatários**: contatos do condomínio; administradora atual; escolha única entre usar, complementar ou substituir padrão; contatos específicos quando pertinentes; cinco caixas de categoria por contato editável.
- Mostrar os contatos herdados do padrão com categorias somente para leitura na tela do condomínio. Editar o padrão no cadastro da administradora.
- Na administradora, acesso **Destinatários padrão**: seleção dos contatos da empresa e das categorias; indicação de quantos clientes usam ou complementam o padrão, para tornar o alcance da alteração visível.
- Em ambas, mostrar resumo do conjunto resultante e histórico somente para consulta. Salvar aplica imediatamente. Não oferecer agendamento ou principal/cópia.
- Exibir telefone e e-mail disponíveis; ausência de e-mail não bloqueia o cadastro. A tela configura destinatários e não oferece botão de envio nesta etapa.

## API e permissões

Adicionar recursos de configuração sob clientes e administradoras, com leitura da configuração, gravação completa com número da revisão conhecida, resultado efetivo e histórico paginado. Rotas finais estão no README do backend. Serviços de domínio comuns evitam diferenças entre API e painel. Preservar rotas existentes e ausência de DELETE.

Usar permissões explícitas de leitura/alteração da nova configuração, além das permissões dos cadastros necessários para consultar contatos e titular; não conceder permissões automaticamente aos usuários existentes. Histórico não admite edição/exclusão pelos fluxos públicos. A matriz implementada e seus testes estão no README do backend e em test_destinatarios.py.

## Compatibilidade e sequência de entrega

1. Implementar o desenho abaixo com os dois alcances de encerramento aprovados; fixar contratos de API e matriz de permissões junto aos serviços.
2. Implementar novas tabelas, serviços e testes unitários; preparar migrations em ambiente isolado. Não alterar a tabela antiga por antecipação.
3. Integrar painel, API e operações de encerramento/troca, com testes de regressão e de histórico. Atualizar documentação operacional.
4. Validar PostgreSQL descartável, inclusive concorrência, e conferir as telas. Só depois preparar aplicação ao banco instalado, com plano de preservação e reversão.

A tabela destinatarios_faturamento deve permanecer preservada. Antes da transição, verificar se contém registros, inicialmente apenas por contagem. Se houver dados, não criar contatos nem inferir categorias automaticamente: preparar conciliação explícita, pois nomes opcionais/e-mails antigos não identificam necessariamente um contato e não indicam suas categorias. Não exibir dados sensíveis desnecessariamente. O desenho foi elaborado sem consulta ao banco instalado.

Novas tabelas gerenciadas coexistem com as atuais managed=False. Instalações novas continuam criando o schema legado uma vez e executando as migrations incrementais; instalações existentes não reaplicam schema.sql. Não reescrever migrations já aplicadas.

## Validação prevista

SQLite: combinações de categorias, titular/contato exclusivo, contatos sem e-mail, três modos, atualização herdada, preservação dos destinatários diretos, isolamento entre clientes, retorno da mesma administradora, histórico e gravação desatualizada; painel/API e permissões. Não afirmar que SQLite comprova bloqueios PostgreSQL.

PostgreSQL isolado: aplicar migrations sobre o schema existente; preservar registros anteriores, inclusive destinatários legados; validar FKs/checks/índices; rollback sem revisão parcial; edição concorrente, padrão versus configuração, encerramento versus seleção e troca de administradora versus seleção. Verificar bloqueios e resultados, não apenas ausência de exceções.

Visual: conferir seleção isolada e conjunta, modos globais, contatos herdados, ausência de e-mail, encerramentos, mudança imediata e histórico. Os cenários efetivamente executados estão descritos em Entrega e limites verificados; os demais permanecem como ampliação futura da cobertura.

## Encerramento da administradora — decisão adicional aprovada

O usuário aprovou ambos: encerrar a participação do contato em um condomínio e encerrar o contato na empresa inteira, retirando-o de todos os destinatários.

- Global: propor encerrado_em opcional em ContatoAdministradora, atribuído pelo servidor. Registros anteriores permanecem com NULL. A criação física da coluna exige migration explícita porque o modelo é managed=False; somente AddField de estado não basta. O encerramento desabilita o contato como destinatário em todos os clientes e padrões sem apagar referências históricas.
- Local: registrar na revisão do condomínio um item de encerramento para o contato da administradora, associado ao vínculo atual. Ele suprime todas as categorias daquele contato naquele condomínio, mesmo que o contato venha do padrão. Essa exceção é por contato inteiro, não uma substituição de padrão por categoria. Na consulta, aplicar a supressão após reunir padrão e seleção específica. Novas revisões preservam a supressão; não oferecer reativação implícita. Em outro período da administradora, não reutilizar silenciosamente essa configuração antiga.
- A ação local não encerra o cadastro global nem afeta outros condomínios. A ação global não depende de copiar encerramentos para todos os clientes: a consulta considera encerrado_em, e o histórico apresenta esse evento com seu instante.
- Encerrar uma Responsabilidade com função livre não equivale automaticamente a encerrar a comunicação: podem existir várias responsabilidades. Manter a ação de destinatários distinta do fluxo antigo; não alterar automaticamente funções/responsabilidades por inferência. As telas devem explicitar o alcance das ações.

Incluir testes para encerramento local de contato herdado do padrão, permanência nos outros clientes e encerramento global, inclusive concorrência com alteração do padrão e nova seleção. O serviço global bloqueia a administradora, revalida o estado e registra o encerramento atomicamente. O histórico da configuração continua referenciando o contato e seu evento de encerramento; não se trata de histórico de mensagens enviadas.
