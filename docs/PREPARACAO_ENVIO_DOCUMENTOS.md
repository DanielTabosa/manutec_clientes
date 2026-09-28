# Preparação do envio de documentos

Referência: conversa de 28/09/2026. Planejamento apenas; integração, anexos e envio ainda não implementados. Pesquisa retomada após pedido do usuário para continuar; nenhuma conexão autenticada foi feita.

## Informações e preferências confirmadas pelo usuário

- As notas são de serviço (NFS-e).
- Os boletos são emitidos dentro do Conta Azul. O usuário acredita que a operação utilize Iugu, mas isso não foi confirmado; não tratar como requisito de integração direta com Iugu.
- Preferência por obter os documentos diretamente do Conta Azul, se possível via API.
- Arquivos de pasta local são uma alternativa aceita como origem; usuário sugeriu botão para anexar documentos ou ajuda de IA e pediu recomendação.
- O envio usará o e-mail do domínio próprio da Manutec Válvulas, administrado pelo cPanel. Endereço remetente, empresa de hospedagem, servidor SMTP, porta, TLS, autenticação e limites ainda não foram informados/verificados. cPanel é o painel de administração, não identifica sozinho o provedor.

## Proposta apresentada — ainda não implementada nem integralmente aprovada

Priorizar Conta Azul como origem e manter botão Anexar documentos para exceções, laudos e arquivos locais. Adiar pasta monitorada e IA até haver necessidade real; IA poderia sugerir condomínio/categoria com conferência, sem decidir sozinha envios. Usar SMTP autenticado da conta do domínio, sujeito às configurações reais do provedor.

Fluxo proposto: buscar no Conta Azul ou anexar → conferir condomínio e categoria → apresentar destinatários cadastrados → confirmar envio → registrar resultado. Prever prevenção de duplicidade desde a primeira implementação. Associação por identificadores externos/CNPJ precisa ser definida; não confiar apenas no nome do arquivo. Nada foi conectado ou enviado nesta conversa.

## Evidência da pesquisa oficial feita em 28/09

- [Consulta de cobrança](https://developers.contaazul.com/docs/charge-apis-openapi/v1): retorno documentado contém id, url e status. Confirma acesso ao link da cobrança, não comprova download direto do PDF do boleto.
- [Nota fiscal por chave](https://developers.contaazul.com/open-api-docs/open-api-invoice/v1/obternotafiscalporchave): documenta XML de NF-e ou ZIP com cartas de correção. Não demonstra suporte às NFS-e usadas pela Manutec nem ao PDF delas.
- [Download de NFS-e no painel Conta Azul](https://ajuda.contaazul.com/hc/pt-br/articles/8126334141581-NFS-e-como-baixar-os-arquivos-da-nota-fiscal): descreve opções de PDF/XML pela interface, sujeitas à disponibilidade da prefeitura. Disponibilidade no painel não comprova disponibilidade na API.
- [Introdução às APIs](https://developers.contaazul.com/aboutapis) e [changelog](https://developers.contaazul.com/changelog): consultar documentação atual ao retomar; FAQs e documentação de versões antigas podem divergir. Não prometer recuperação de ambos os PDFs antes de testar a API pública.

## Resultado da investigação na retomada

A [consulta de NFS-e](https://developers.contaazul.com/open-api-docs/open-api-invoice/v1/obternotasfiscaisservicoporfiltro) existe em GET /v1/notas-fiscais-servico. Exige período de até 15 dias e permite paginação e filtros de cliente/status. A introdução da API está desatualizada em relação a esse endpoint; priorizar a operação e seu contrato.

No [OpenAPI fiscal](https://developers.contaazul.com/_bundle/open-api-docs/open-api-invoice.json?download=), NotaFiscalServico contém identificação, documento do cliente, venda, competência, valor e status, mas não campo de PDF, XML ou URL. Portanto a listagem é documentada; obtenção do arquivo NFS-e pela API continua não comprovada. O download de NF-e por chave não deve ser assumido como solução para NFS-e.

Cobranças: GET /v1/financeiro/eventos-financeiros/contas-a-receber/cobranca/{id_cobranca} fornece URL e status; ainda falta verificar em amostra real se o link permite obter PDF, se exige sessão e como relacionar a cobrança à venda/parcela. Não gerar cobrança para fazer esse teste.

## Preparação do acesso — sem conexão executada

Conforme [guia de credenciais](https://developers.contaazul.com/guide), é necessário acesso ao portal do desenvolvedor e aplicação com client_id/client_secret. O [fluxo de autorização](https://developers.contaazul.com/requestingcode) exige redirect_uri idêntica à cadastrada e state aleatório validado no retorno. A documentação informa permissão administrativa no escopo OAuth: não há garantia de token restrito a leitura. Consultas devem ser limitadas por nossa implementação; armazenamento dos segredos e renovação ainda precisam ser projetados.

Antes de criar aplicação ou iniciar OAuth, confirmar se o usuário já tem cadastro/aplicação e preparar a URL de retorno. Não pedir segredos no chat nem copiar URL de retorno contendo código para documentação. Não ler .env apenas por estar aberto no editor.

## Próxima etapa proposta

Confirmar acesso ao Portal do Desenvolvedor e preparar a aplicação/conexão, com autorização do usuário. Depois validar uma NFS-e e uma cobrança existentes em período restrito, sem emitir, alterar ou enviar documentos. Registrar se os arquivos são realmente obtidos; se a NFS-e continuar sem download público documentado, consultar suporte oficial ou usar anexação local, sem recorrer à API privada.

A retomada autorizou continuar a investigação. Conexão real, implementação de integração e envio ainda não foram executados. Usuário quer progresso por etapas: ao concluir uma, explicar a próxima e pedir autorização para avançar. Commit e push rotineiros têm autorização permanente em AGENTS.md.
