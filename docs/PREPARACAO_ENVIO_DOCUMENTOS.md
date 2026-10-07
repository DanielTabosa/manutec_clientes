# Preparação do envio de documentos

Estado atual em 06/10/2026: download de um PDF de boleto existente comprovado diretamente pela API pública. Integração ao painel, anexos e envio ainda não implementados. Evidências anteriores estão preservadas abaixo como contexto datado.

## Base de teste e desenho do fluxo — decisão de 07/10/2026

**Decisão do usuário:** os clientes atualmente cadastrados são reais, mas foram inseridos apenas para testes e podem conter dados imprecisos. A associação com documentos só será validada quando a base definitiva estiver preenchida. Não usar a prévia anterior para concluir que faltam 110 clientes, preparar importação, corrigir cadastros ou sugerir envios reais. Scripts e relatório anteriores ficam preservados como evidência técnica; sem novas execuções de alinhamento nesta fase.

O usuário autorizou registrar essa decisão e desenhar o fluxo abaixo com exemplos fictícios. **Desenho proposto para aprovação, ainda não implementado:**

1. **Escolher o cliente:** iniciar a preparação no contexto de um cliente, mostrando claramente quem é o destinatário dos documentos. Na demonstração, usar um cliente inteiramente fictício, sem consultar/alterar a base de teste instalada.
2. **Anexar e classificar:** adicionar PDF de boleto e/ou nota fiscal; mostrar nome, categoria, opção de visualizar/remover e referência do documento. Boleto e nota são independentes, sem obrigatoriedade de enviar ambos. A primeira demonstração usa arquivos fictícios locais; download Conta Azul e importação de ZIP já existentes continuam rotinas separadas.
3. **Conferir por destinatário:** apresentar nome, e-mail e exatamente os anexos que cada contato receberia, conforme categorias/configuração vigente. Reutilizar as regras de destinatários já aprovadas, incluindo exclusão de contatos encerrados. Ausência de e-mail deve aparecer como impedimento para aquele envio por e-mail, sem apagar ou desmarcar o contato no cadastro. Correções da configuração pertencem à tela de destinatários; não introduzir alterações silenciosas durante a preparação.
4. **Revisar e confirmar:** mostrar cliente, assunto/texto e anexos por destinatário antes da ação final. Na demonstração, ação **Simular preparação**, com resultado claramente simulado e nenhuma mensagem enviada. Envio real, persistência de rascunhos/histórico e configuração SMTP ficam para etapa posterior aprovada.

Exemplo fictício de conferência:

| Contato | Categorias configuradas | Anexos apresentados |
| --- | --- | --- |
| Ana | Boleto e nota fiscal | Boleto de exemplo + nota de exemplo |
| Bruno | Boleto | Somente boleto de exemplo |
| Carla | Nota fiscal | Somente nota de exemplo |

A interface deve distinguir arquivo anexado de documento corretamente identificado: o usuário confere o conteúdo antes da confirmação. A associação automática por CNPJ fica adiada conforme decisão acima. Antes do envio real, definir remetente/SMTP, permissão de envio, tratamento de contatos com o mesmo e-mail, prevenção de duplicidade/reenvio e registro de aceitação/falha; não assumir que aceitação pelo provedor prova entrega.

Próximo passo proposto: protótipo visual navegável desse fluxo, com cliente/contatos/PDFs fictícios, sem banco, API Conta Azul ou envio. Aguardar aprovação do desenho antes de implementar. Esta etapa foi somente documental; conteúdo, links relativos e diff conferidos, sem migrations, gravações em banco ou testes SQLite/PostgreSQL.

## Download direto de boleto validado — 06/10/2026

`backend/contaazul_boleto.py` adapta a rotina de `C:/dev/manutec-faturamento/src/faturamento/boletos.py`, consultada apenas para leitura. Usa o [GET oficial de PDF da cobrança](https://developers.contaazul.com/docs/charge-apis-openapi/v1/imprimircobrancapdf), terminado em `/cobranca/{id_cobranca}/imprimir`. A investigação anterior do link da cobrança não havia identificado essa operação; a disponibilidade do PDF de boleto agora está comprovada nesta amostra.

Comando, na raiz do projeto:

```powershell
.\.venv\Scripts\python.exe backend/contaazul_boleto.py --producao --vencimento 2026-10-13 --valor 1500.00
```

Seleciona uma única conta PENDING por vencimento exato e valor total, consulta todas as solicitações dessa parcela (máximo 10) e exige exatamente uma cobrança REGISTRADO. Uma página cheia de 10 recebíveis, zero/mais de uma correspondência, ausência/ambiguidade de cobrança ou IDs inválidos interrompem a execução. Não é download em lote nem associação definitiva de clientes; data/valor só servem para a amostra inequívoca. Máximo de 13 GETs; nesta amostra foram cinco. Sem renovação automática ou repetição, redirects ou envio de token a outro domínio.

Salva em `.venv/contaazul/<ambiente>/downloads/boleto-AAAAMMDD.pdf` (desenvolvimento sem subpasta de ambiente). Na produção desta amostra: `.venv/contaazul/producao/downloads/boleto-20261013.pdf`, ignorado pelo Git, dentro do diretório protegido já existente. Arquivo existente bloqueia antes da rede. Grava temporário e publica por hard link exclusivo no mesmo volume, preservando destino concorrente; limpa temporário em falhas. Limites: JSON 1 MiB e PDF 10 MiB; tipo de conteúdo, assinatura PDF e marcador final conferidos. O comando não modifica cobranças nem o banco.

Validação: 29 testes da integração com rede simulada (12 novos de download), ajuda e diff conferidos. Nenhum teste SQLite/PostgreSQL ou migration pertinente a esta rotina isolada. Download real autorizado: um PDF de 98.897 bytes, uma página, sem criptografia, zero avisos em `pypdf` estrito. Texto normalizado igual ao PDF manual; valor/vencimento presentes. Hashes diferentes, portanto não são idênticos byte a byte; causa da diferença não investigada. Comparação feita em memória, sem expor texto ou identificadores. PDF não incluído no Git. Projeto de referência preservado.

Integração ao painel, associação por cliente, anexação/envio e PDF/XML de NFS-e continuam pendentes. Conclusão segue a autorização de commit/push das instruções atuais do projeto, reapresentadas em 07/10/2026.

## Prévia de associação de NFS-e aos clientes — 07/10/2026

`backend/contaazul_previa_clientes.py` reaproveita a conferência do ZIP/API e propõe clientes apenas para notas reconhecidas. O CNPJ do tomador deve corresponder a exatamente um registro atual (`data_fim` nula) no histórico de CNPJs do cadastro. O ID permanente do cliente é a sugestão; nenhuma associação é persistida. Nome semelhante não é critério. CPF sem regra local, CNPJ antigo, ausência e duplicidade ficam pendentes. Este critério é conservador para a prévia, não uma nova regra de importação/envio.

```powershell
.\.venv\Scripts\python.exe backend/contaazul_previa_clientes.py --producao --competencia 2026-10 --zip "C:\Users\didit\Downloads\NFSe-10-2026 (2).zip"
```

Consulta somente os CNPJs necessários no PostgreSQL configurado pelo Django, em transação `READ ONLY`, com parâmetros e timeout de 10 segundos. Recusa outro banco/transação já ativa; não usa SQLite como substituto. Configuração local é carregada internamente, sem exibir credenciais. Nenhuma migration, atualização cadastral ou envio.

Única gravação: CSV protegido em `.venv/contaazul/producao/previas/clientes-nfse-202610.csv` (no ambiente de desenvolvimento, sob `.venv/contaazul/previas`). Fora do Git; não sobrescreve, inclusive em concorrência. Contém índice do par, número da nota, cliente sugerido (ID/nome), situação/motivo, sem CNPJ ou valor. Células são protegidas contra interpretação como fórmula. Console só mostra contagens e caminho. O relatório existente bloqueia nova execução antes da API/banco; preservar antes de gerar outra prévia.

Resultado real: 139 linhas, sendo uma sugestão, 135 notas sem cadastro (110 CNPJs distintos) e três documentos não conferidos por status CANCELAMENTO_MANUAL. Cadastro local possui três clientes, três CNPJs atuais e um histórico encerrado. Somente a linha sugerida tem cliente preenchido. ZIP preservado por hash; nenhum vínculo gravado. É prévia de NFS-e, não associação de boletos nem vínculo definitivo entre todos os documentos.

Validação: 54 testes Conta Azul com dados fictícios (nove novos de prévia), ajuda, leitura do CSV e diff. PostgreSQL instalado usado exclusivamente em consultas/transações de leitura; não houve teste de escrita/rollback ou suite SQLite nesta etapa. Essa proposta foi adiada pelo usuário: a base atual é somente de teste e pode ser imprecisa. O resultado não serve para diagnosticar falta de clientes na base definitiva ou preparar importação; ver decisão atual acima.

## Conferência local de NFS-e — 07/10/2026

Implementado `backend/contaazul_nfse.py`: lê ZIP existente, sem extrair, renomear, copiar ou modificar arquivos. Pareia PDF/XML pelo nome-base, recusa duplicidades e exige número da NFS-e, DPS/RPS, documento do tomador e valor. Compara com a listagem pública do Conta Azul: status EMITIDA e correspondência única com todos os campos iguais. Não associa ao cadastro do projeto, não consulta contratos e não grava no banco. Dados financeiros usam Decimal.

```powershell
.\.venv\Scripts\python.exe backend/contaazul_nfse.py --producao --competencia 2026-10 --zip "C:\Users\didit\Downloads\NFSe-10-2026 (2).zip"
```

O comando sempre faz apenas conferência; não existe modo de importação. Ambiente padrão é desenvolvimento; `--producao` não recua para outro ambiente. Saída por índices anônimos dos pares, contagens e motivos; sem nomes, documentos, valores ou números de notas. Retornos: 0 = ao menos uma nota e todos os pares conferidos; 2 = pendências/nenhum par reconhecido; 1 = falha técnica ou consulta incompleta. Em caso de falha da API, não apresenta correspondências parciais como concluídas.

Limites: ZIP compactado e soma descompactada até 100 MiB; até 2.000 entradas; XML 2 MiB/PDF 10 MiB por arquivo. XML UTF-8 sem DTD/entidades declaradas, caminhos únicos para campos essenciais; formatos reconhecidos: NFSe do namespace nacional e Nfse no namespace ABRASF com estrutura infNFSe/DPS, observada no ZIP fornecido. Outros formatos ficam pendentes. PDF conferido somente por assinatura, marcador final e nome do par; conteúdo textual do PDF, assinatura digital e autenticidade fiscal não são validados.

A [listagem oficial de NFS-e](https://developers.contaazul.com/open-api-docs/open-api-invoice/v1/obternotasfiscaisservicoporfiltro) é consultada em janelas consecutivas de até 15 datas inclusivas. Até 10 páginas de 50 registros por janela (máximo 30 GETs/mês); página cheia ao atingir limite interrompe, sem aceitar resultado truncado. JSON limitado a 2 MiB por resposta; sem redirects, renovação ou repetição automática. HTTP 401 exige renovação manual do mesmo ambiente.

Validação: 45 testes da integração passaram (16 novos de NFS-e), com ZIPs fictícios e rede simulada. ZIP real informado pelo usuário: 139 pares aptos localmente, nenhuma pendência local, hash preservado antes/depois. Competência outubro/2026 inferida do nome do ZIP e comunicada ao usuário. Comparação real concluída após renovação manual confirmada pelo usuário: 136 notas reconhecidas e três pendentes por status diferente de EMITIDA. Consulta adicional somente de leitura confirmou que as três estão com status CANCELAMENTO_MANUAL. Permanecem fora das reconhecidas; nenhuma alteração de regra ou estado fiscal. ZIP preservado por hash antes/depois. A execução anterior retornou 401 e foi interrompida sem repetição automática; a repetição posterior foi manual após renovação. Sem testes SQLite/PostgreSQL ou migrations, pois o script não usa banco.

## Avaliação da referência de NFS-e — 06/10/2026

Consulta somente de leitura a `C:/dev/manutec-faturamento/src/faturamento/notas.py` e `tests/test_notas.py`, autorizada pelo usuário. Nenhum arquivo desse projeto alterado ou executado; nenhum ZIP real, credencial ou banco consultado nesta avaliação.

A rotina lê um ZIP já baixado do painel, pareia PDF/XML pelo nome-base, extrai número da NFS-e, DPS/RPS, documento do tomador e valor do XML nacional. Cruza os dados com a listagem de NFS-e e liga `id_venda` à prévia de contratos do outro projeto. Aceita status EMITIDA, separa divergências e mais de uma nota por contrato; grava sem sobrescrever. O modo simular evita gravação de PDFs, mas consulta a API. Isso não demonstra download automático de NFS-e pela API.

Reaproveitar a leitura do par PDF/XML e a conferência por identificadores. Não transferir automaticamente a associação por contratos, nomes de arquivos, diretório OneDrive ou regras de envio para nosso cadastro. Pontos a corrigir na adaptação: valores com Decimal e campos obrigatórios (a referência permite ignorar algumas verificações quando o valor/RPS está ausente); rejeitar pares ambíguos/nomes duplicados no ZIP em vez de substituir silenciosamente; limitar volume total e leitura dos arquivos/XML; formar janelas de até 15 datas inclusivas (a referência consulta 16–31 em meses de 31 dias, intervalo de 16 datas). Os testes consultados usam rede fictícia; não foram executados nem validam esses casos adicionais.

Proposta posteriormente aprovada e implementada, conforme estado atual acima: versão local de conferência de ZIP, sem banco, associação automática ao cliente ou envio. Verificar campos obrigatórios e pares PDF/XML; consultar NFS-e em período explícito limitado; apresentar resumo de correspondências e pendências sem expor dados pessoais. Testar com arquivos fictícios e depois com um ZIP existente indicado pelo usuário. Validação real depende desse arquivo; não solicitar nova emissão de nota. Salvar/organizar os documentos e integrar ao painel ficam para etapa definida após a conferência.

## Informações e preferências confirmadas pelo usuário

- As notas são de serviço (NFS-e).
- Os boletos são emitidos dentro do Conta Azul. O usuário acredita que a operação utilize Iugu, mas isso não foi confirmado; não tratar como requisito de integração direta com Iugu.
- Preferência por obter os documentos diretamente do Conta Azul, se possível via API.
- Arquivos de pasta local são uma alternativa aceita como origem; usuário sugeriu botão para anexar documentos ou ajuda de IA e pediu recomendação.
- O envio usará o e-mail do domínio próprio da Manutec Válvulas, administrado pelo cPanel. Endereço remetente, empresa de hospedagem, servidor SMTP, porta, TLS, autenticação e limites ainda não foram informados/verificados. cPanel é o painel de administração, não identifica sozinho o provedor.

## Proposta apresentada — ainda não implementada nem integralmente aprovada

Priorizar Conta Azul como origem e manter botão Anexar documentos para exceções, laudos e arquivos locais. Adiar pasta monitorada e IA até haver necessidade real; IA poderia sugerir condomínio/categoria com conferência, sem decidir sozinha envios. Usar SMTP autenticado da conta do domínio, sujeito às configurações reais do provedor.

Fluxo proposto: buscar no Conta Azul ou anexar → conferir condomínio e categoria → apresentar destinatários cadastrados → confirmar envio → registrar resultado. Prever prevenção de duplicidade desde a primeira implementação. Associação por identificadores externos/CNPJ precisa ser definida; não confiar apenas no nome do arquivo. Autenticação local concluída segundo o usuário; nenhum envio implementado.

## Evidência da pesquisa oficial feita em 28/09

- [Consulta de cobrança](https://developers.contaazul.com/docs/charge-apis-openapi/v1): retorno documentado contém id, url e status. Confirma acesso ao link da cobrança, não comprova download direto do PDF do boleto.
- [Nota fiscal por chave](https://developers.contaazul.com/open-api-docs/open-api-invoice/v1/obternotafiscalporchave): documenta XML de NF-e ou ZIP com cartas de correção. Não demonstra suporte às NFS-e usadas pela Manutec nem ao PDF delas.
- [Download de NFS-e no painel Conta Azul](https://ajuda.contaazul.com/hc/pt-br/articles/8126334141581-NFS-e-como-baixar-os-arquivos-da-nota-fiscal): descreve opções de PDF/XML pela interface, sujeitas à disponibilidade da prefeitura. Disponibilidade no painel não comprova disponibilidade na API.
- [Introdução às APIs](https://developers.contaazul.com/aboutapis) e [changelog](https://developers.contaazul.com/changelog): consultar documentação atual ao retomar; FAQs e documentação de versões antigas podem divergir. Não prometer recuperação de ambos os PDFs antes de testar a API pública.

## Resultado da investigação na retomada

A [consulta de NFS-e](https://developers.contaazul.com/open-api-docs/open-api-invoice/v1/obternotasfiscaisservicoporfiltro) existe em GET /v1/notas-fiscais-servico. Exige período de até 15 dias e permite paginação e filtros de cliente/status. A introdução da API está desatualizada em relação a esse endpoint; priorizar a operação e seu contrato.

No [OpenAPI fiscal](https://developers.contaazul.com/_bundle/open-api-docs/open-api-invoice.json?download=), NotaFiscalServico contém identificação, documento do cliente, venda, competência, valor e status, mas não campo de PDF, XML ou URL. Portanto a listagem é documentada; obtenção do arquivo NFS-e pela API continua não comprovada. O download de NF-e por chave não deve ser assumido como solução para NFS-e.

Cobranças: GET /v1/financeiro/eventos-financeiros/contas-a-receber/cobranca/{id_cobranca} fornece URL e status. Relação parcela → solicitações confirmada em produção; usuário confirmou visualização do boleto pelo link da cobrança REGISTRADO em 06/10/2026. Usuário também confirmou download manual pelo novo link aberto nessa página. Arquivo salvo validado estruturalmente como PDF de uma página, sem avisos no leitor estrito. Download direto autenticado pela API pública comprovado pela nova rotina, conforme seção atual acima; não depende do navegador. Não gerar cobrança para fazer esse teste.

## Preparação do acesso

Conforme [guia de credenciais](https://developers.contaazul.com/guide), é necessário acesso ao portal do desenvolvedor e aplicação com client_id/client_secret. O [fluxo de autorização](https://developers.contaazul.com/requestingcode) exige redirect_uri idêntica à cadastrada e state aleatório validado no retorno. A documentação informa permissão administrativa no escopo OAuth: não há garantia de token restrito a leitura. Consultas devem ser limitadas por nossa implementação; a sonda local já protege o armazenamento e permite renovação manual; integração ao painel permanece pendente.

Antes de criar aplicação ou iniciar OAuth, confirmar se o usuário já tem cadastro/aplicação e preparar a URL de retorno. Não pedir segredos no chat nem copiar URL de retorno contendo código para documentação. Não ler .env apenas por estar aberto no editor.

## Próxima etapa proposta

Alinhamento com clientes adiado até a base definitiva, conforme decisão atual. Próxima etapa proposta: protótipo navegável do fluxo de anexos e conferência com dados fictícios, sujeito à aprovação do usuário. Boleto via API e conferência do ZIP de NFS-e já validados tecnicamente; envio real, lote e associações persistidas continuam fora do escopo.

A retomada autorizou continuar a investigação. Sonda manual de renovação preparada em backend/contaazul_auth.py, com configuração local protegida e oito testes simulados. O cURL do portal continha apenas o marcador REFRESH_TOKEN_GERADO; não comprovou fornecimento de Refresh Token real. Acrescentado --autorizar para primeira troca guiada de código; usuário informou execução concluída com tokens salvos localmente. Integração ao painel e envio ainda não foram executados. Usuário quer progresso por etapas: ao concluir uma, explicar a próxima e pedir autorização para avançar. Commit e push rotineiros têm autorização permanente em AGENTS.md.


## Sonda de consulta preparada

Usuário informou autenticação concluída e autorizou preparar a consulta. `backend/contaazul_consulta.py` usa o ACCESS_TOKEN local, sem renovação automática. Consulta primeira página de NFS-e por competência e contas a receber por vencimento, até 10 itens cada, em período de até 15 datas inclusivas. Confere apenas a primeira parcela e sua primeira solicitação de cobrança: no máximo quatro GETs. Sem dados pessoais, IDs ou URLs na saída; sem persistir respostas, seguir links, baixar arquivos ou enviar documentos.

Relação parcela → solicitacoes_cobrancas → id confirmada no [OpenAPI financeiro](https://developers.contaazul.com/_bundle/docs/financial-apis-openapi.json?download=). Ainda exige amostra autenticada; a primeira parcela pode não ter cobrança. Página vazia não prova indisponibilidade. O token determina a empresa acessada: a sonda não comprova automaticamente que ela é de desenvolvimento. Instruções no README do backend.


## Diagnóstico autenticado — 28/09/2026

Após HTTP 401, usuário renovou com sucesso. NFS-e retornou HTTP 500 tanto para 14–28/09 quanto para apenas 28/09; reduzir período não resolveu. Assistente executou uma única consulta financeira GET, primeira página de contas a receber com vencimento em 28/09: HTTP 200 e zero itens. Evidência confirma acesso financeiro nesse teste, sem comprovar causa da falha fiscal, existência de documentos ou disponibilidade dos PDFs. Nenhuma alteração, envio, consulta de parcela ou cobrança, nem persistência de resposta. Usuário confirmou que a conta de desenvolvimento está vazia. Não criar documentos para testar. Conta vazia é compatível com a lista financeira vazia, mas não determina a causa do erro fiscal.


## Decisão para a próxima sessão

Usuário autorizou preparar o acesso à conta real da Manutec, exclusivamente para consultas limitadas, sem emitir, alterar ou enviar documentos. Preparacao, autorizacao e primeira consulta de producao concluidas segundo saida apresentada pelo usuario, conforme estado abaixo. Conferir documentação vigente da aplicação de produção e OAuth; não assumir que a aplicação de desenvolvimento pode acessar a empresa real. Preservar configuração de teste, separar ambientes e manter segredos fora do chat/Git. Após conectar a conta correta, selecionar período com documento existente para validar disponibilidade dos arquivos.

Na pausa anterior, commit/push ficaram suspensos. As instruções atuais reapresentadas em 07/10/2026 determinam commit/push ao concluir cada etapa. Retomar pelo estado atual em SESSION_HANDOFF.md.

## Estado da preparacao de producao

Aplicacao de producao cadastrada e callback https://manutecvalvulas.com.br/contaazul/callback/ publicado pelo usuario via cPanel; pagina exibida segundo ele. CLIENT_ID e CLIENT_SECRET preenchidos pelo usuario em .venv/contaazul/producao/credenciais.env (ignorado no Git, ACL usuario/SYSTEM). Sondas agora aceitam --producao para selecionar esse arquivo; sem a opcao, preservam desenvolvimento. Tokens pendentes ficam na pasta do ambiente selecionado. Usuario executou a autorizacao de producao e apresentou mensagem de sucesso, com tokens salvos localmente. Em seguida executou a sonda com --producao --inicio 2026-09-01 --fim 2026-09-15: sucesso, 10 NFS-e na primeira pagina, 10 contas a receber na primeira pagina e link presente na primeira cobranca consultada. Contagens sao da pagina, nao totais do periodo. Nessa primeira consulta, link nao aberto e arquivos ainda nao comprovados; download de boleto foi validado posteriormente, conforme estado atual documentado. Nenhum documento baixado, alterado ou enviado. Evidencia: saida do terminal compartilhada pelo usuario; assistente nao repetiu chamadas nem leu credenciais. 17 testes com rede simulada aprovados; sem banco SQLite/PostgreSQL, migrations, commit ou push. Selecao de arquivo nao comprova empresa: conferir Manutec no navegador antes de autorizar.

Comandos e procedimento em [README do backend](../backend/README.md#configuracao-separada-de-producao).

### Inspecao limitada do link de cobranca

Verificacao do link autorizada pelo usuario e executada pelo assistente: sonda temporaria .venv/contaazul/producao/verificar_link.py obteve uma cobranca existente no periodo 01–15/09/2026. Destino HTTPS faturas.contaazul.com com fragmento. GET publico separado, sem Authorization/cookies/proxy e sem seguir redirects: HTTP 200, text/html, sem assinatura PDF, zero links .pdf no HTML inicial, dois scripts, zero formularios. Isso confirma pagina HTML acessivel, nao PDF nem ausencia de login apos carregar JavaScript. Nenhuma resposta/URL sensivel persistida; token carregado internamente sem exposicao. Para abrir a pagina, a sonda repetiu os tres GETs financeiros com --abrir e chamou navegador padrao; abertura reportada com sucesso. Total desta investigacao: seis GETs financeiros e um GET publico pela sonda, alem do carregamento normal do navegador. Nenhuma emissao, alteracao, pagamento, envio ou download de arquivo solicitado. Inspecao visual automatizada bloqueada: cua.getState falhou duas vezes com trusted Node process exited unexpectedly; nao houve leitura visual da pagina. Usuario informou que a pagina aberta exibe "Por favor, tente novamente. Nao foi possivel obter os dados" e que o botao retorna ao mesmo erro. Diagnostico adicional autorizado: tres GETs financeiros pelo modo --status da sonda temporaria, sem reabrir link, retornaram status QUITADO e uma unica solicitacao de cobranca na primeira parcela. Portanto a amostra esta quitada; nao ha evidencia de que esse status cause o erro da pagina. Nenhum PDF obtido. Na retomada de 06/10/2026, usuario informou vencimento e valor de uma amostra em aberto. A consulta inicial retornou 401; apos renovacao manual confirmada, a API retornou cinco recebiveis PENDING no dia, com uma unica correspondencia por valor. A parcela possui duas solicitacoes: REGISTRADO e CANCELADO. Foi aberta somente a URL da unica REGISTRADO; usuario confirmou que o boleto apareceu. GET publico previo retornou HTTP 200, text/html, sem assinatura PDF. Assim, o link retornado pela API funcionou para essa amostra. Usuario confirmou depois que a pagina abre outro link para baixar o boleto e que concluiu o download, escolhendo o local no dialogo de salvar. Usuario forneceu o caminho local e o assistente validou o arquivo em leitura: 98.897 bytes, assinatura e marcador de fim de PDF presentes; pypdf em modo estrito leu uma pagina sem criptografia, com dimensoes e fluxo de conteudo validos, zero avisos. PDF estruturalmente valido; dados financeiros e autenticidade bancaria nao inspecionados. Confirmada obtencao manual de PDF pelo fluxo iniciado no link da API. Posteriormente, download direto pela API publica comprovado nesta amostra, sem navegador, conforme secao atual acima. A causa do erro da amostra quitada permanece indeterminada. Nao criar, reemitir, cancelar ou enviar cobrancas. Documentacao oficial do GET confirma url e status, sem promessa de PDF: https://developers.contaazul.com/docs/charge-apis-openapi/v1. A sonda temporaria anterior fez nove GETs financeiros e um GET publico. A investigacao do link na retomada fez 13 GETs financeiros (um 401 e doze 200), um GET publico e abertura no navegador. O teste posterior do novo script fez mais cinco GETs, incluindo o download direto do PDF; total da retomada: 18 GETs financeiros e um publico, alem do uso do navegador. Nenhuma causa raiz concluida; nao presumir token invalido ou indisponibilidade geral.
