# Preparação do envio de documentos

Referência: conversa de 28/09/2026. Planejamento apenas; integração, anexos e envio ainda não implementados. A sessão foi pausada pelo usuário por limite de tokens.

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

## Ponto exato de retomada

Foi proposta a próxima etapa: investigar especificamente recuperação de NFS-e e boletos existentes e preparar uma conexão somente de consulta ao Conta Azul, sem emitir cobranças ou enviar e-mails. O assistente pediu autorização; o usuário respondeu pedindo pausa, portanto essa autorização ainda não foi concedida.

Ao retomar, apresentar brevemente essa etapa e pedir autorização. Depois, verificar endpoints atuais e requisitos de OAuth, esclarecer acesso ao portal do desenvolvedor e validar uma amostra com autorização específica. Não pedir senhas/tokens no chat, não ler/expor .env, não emitir documentos, não criar cobranças e não enviar e-mails por antecipação. Registrar explicitamente limitações e oferecer anexação local caso o documento não esteja acessível pela API.

Usuário quer progresso por etapas: ao concluir uma, explicar a próxima e pedir autorização para avançar. Commit e push rotineiros já têm autorização permanente em AGENTS.md.
