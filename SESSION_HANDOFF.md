# Retomada — 28/09/2026

## Etapa atual

Autenticação e renovação concluídas segundo o usuário. Execução real da sonda pelo usuário retornou HTTP 401 inicialmente; após renovar, NFS-e retornou HTTP 500 para 14–28/09/2026 e novamente para somente 28/09/2026. Parâmetros conferidos contra documentação pública. Não presumir token inválido nem concluir indisponibilidade definitiva da API. Diagnóstico isolado executado pelo assistente: um GET de contas a receber para vencimento em 28/09/2026 retornou HTTP 200, lista reconhecida e zero itens. Credenciais carregadas internamente, sem exposição; nenhuma resposta sensível persistida. Nenhuma parcela/cobrança consultada, arquivo baixado ou envio feito.

Próximo passo: confirmar com o usuário se a conta de desenvolvimento contém NFS-e/boletos e qual período usar. Falha fiscal ainda sem causa determinada; acesso financeiro funciona nesse teste. Evitar repetir chamadas fiscais idênticas; se necessário preparar diagnóstico para suporte com dados sanitizados. Não enviar mensagem ao suporte sem autorização. Não pedir tokens no chat.

Sonda: período padrão hoje menos 14 dias até hoje, ajustável com --inicio/--fim (15 datas inclusivas). Primeira página de NFS-e por competência e contas a receber por vencimento, 10 itens cada; primeira parcela e primeira solicitação de cobrança quando presentes. Máximo quatro GETs, sem redirecionamentos/proxy ambiente/retries, timeout e tamanho de resposta limitados. Não segue links, persiste respostas, consulta banco ou envia documentos. Mostra apenas contagens/presença de link. Vazio ou primeira parcela sem cobrança é inconclusivo. O token identifica a empresa; a sonda não garante ambiente de desenvolvimento.

Validação: 14 testes unittest (8 autenticação, 6 consulta) com rede simulada aprovados. Não houve migrations nem validação SQLite/PostgreSQL nesta etapa. Sonda publicada em 66dbfd6. Diagnóstico atual apenas documental, sem novos testes de banco; conteúdo e diff conferidos. Documentos sincronizados: README backend, PROJECT_STATE, preparação do envio. Revisar git log/status para commit desta etapa; commit/push autorizados permanentemente, nunca force push.

## Decisões e próximos limites

NFS-e e boletos emitidos no Conta Azul; Iugu é hipótese do usuário. Preferência API, arquivo local como alternativa. Remetente domínio próprio Manutec via cPanel; endereço/SMTP ainda pendentes. Botão Anexar, conferência antes de enviar, prevenção de duplicidade e registro do resultado são propostas; não implementadas nem integralmente aprovadas. IA e pasta monitorada adiadas. Detalhes/fontes em docs/PREPARACAO_ENVIO_DOCUMENTOS.md.

API pública confirma listagem NFS-e, sem arquivo/link no contrato; download de NF-e por chave não comprova NFS-e. OpenAPI financeiro documenta parcela → solicitacoes_cobrancas → id; cobrança retorna URL/status, não comprova PDF. Não criar cobranças/notas para testar. Próxima etapa após amostra: decidir obtenção dos arquivos com base no resultado; explicar e pedir autorização ao usuário para avançar.

## Acesso e cuidados

Credenciais exclusivamente em `.venv/contaazul/credenciais.env`, ignorado pelo Git, ACL usuário/SYSTEM. Não ler/expor valores. Authorization Basic apareceu em captura; recomendação de troca apresentada, usuário decidiu manter. Não extrair da imagem. O cURL do portal tinha REFRESH_TOKEN_GERADO como exemplo, não token real. Fluxo --autorizar já usado com sucesso segundo o usuário; não repetir como pendência. Script auth valida destino/state e salva access/refresh de forma atômica. Se existir tokens-pendentes.env, recuperar localmente antes de renovar. Escopo OAuth administrativo: somente leitura é limite da implementação.

## Projeto preservado

Painel de destinatários concluído e aceito pelo usuário, inclusive lista própria salva. Não repetir aceitação. Cinco categorias independentes, revisões, encerramento local/global, sem reativação automática nem envio. Regras em docs/DESTINATARIOS_COMUNICACOES.md. Migration 0007 aplicada ao PostgreSQL instalado, com legado vazio e dados/concessões preservados. UX: rótulos didáticos, selecionar/desmarcar categorias, ações junto às tabelas e retorno ao cliente/rolagem após salvar.

Validação anterior: 49 testes SQLite e inspeção visual aprovada; 11 verificações PostgreSQL isoladas anteriores, não equivalentes a testes desta sonda. Servidor localhost:8000, último PID conhecido 31044 (--noreload); conferir antes de depender dele. Não alterar dados do cliente usado na aceitação.

Backup protegido: `.venv/backups/pre_0007_20260928/pre_0007.dump`, hash/evidência em verification.json. Preservar antes de recriar .venv. Recuperação em banco vazio separado conforme README; não reverter migration automaticamente.

Processo proporcional acordado: leituras pontuais, testes pertinentes, sem subagentes desnecessários. Usuário iniciante: paciência e uma instrução por vez. Rotina de commit/push autorizada em AGENTS.md. Ambiente teve falha do sandbox; comandos escalonados e git -c safe.directory=C:/dev/manutec-clientes. Não expor .env. Substituir este handoff ao fim da próxima sessão relevante.
