# Retomada — associação adiada; desenho de anexos/conferência proposto

## Decisão atual e próximo passo

Usuário esclareceu que os clientes da base instalada são reais, mas foram cadastrados apenas para testes e podem conter dados imprecisos. **Alinhamento de documentos/clientes só será necessário quando a base definitiva estiver preenchida.** Não preparar lista de clientes faltantes, importação ou correções com base nos resultados anteriores. Preservar scripts e relatório como evidência técnica, sem repetir consultas de associação ou alterar cadastros.

Usuário autorizou registrar essa decisão e desenhar o fluxo de anexar boleto/nota e conferir destinatários antes do envio, com exemplos fictícios. Desenho concluído em docs/PREPARACAO_ENVIO_DOCUMENTOS.md, seção Base de teste e desenho do fluxo. Ainda não é implementação ou aprovação de novas regras.

Proposta: escolher cliente → anexar/classificar boleto e/ou nota → mostrar por contato os anexos permitidos pelas categorias já configuradas → revisar assunto/texto e confirmar. Boleto/nota independentes. Na demonstração, cliente, contatos e PDFs são inteiramente fictícios; botão Simular preparação e resultado explicitamente simulado. Contato sem e-mail aparece impedido para e-mail, sem apagar cadastro. Reutilizar a configuração de destinatários aprovada; não alterar seleções silenciosamente. Envio real, SMTP, persistência e prevenção de duplicidade ficam para etapa futura.

**Próximo passo a perguntar ao usuário:** aprova esse desenho e posso criar um protótipo visual navegável, sem banco/API/envio? Aguardar resposta antes de implementar. Não usar cadastros reais da base instalada como exemplos confiáveis. Não implementar extração/importação ou envio automaticamente.

Etapa atual somente documental: atualizados PROJECT_STATE.md, backend/README.md, docs/PREPARACAO_ENVIO_DOCUMENTOS.md e este handoff. Conferir conteúdo/links/diff e fazer commit/push conforme instruções atuais. Nenhuma migration, gravação em banco ou teste SQLite/PostgreSQL pertinente. Implementações anteriores nos commits 4acb467 e 91cfa9b preservadas.

Preferência permanente: ao concluir cada tarefa, apresentar resultado, sugerir próximo passo concreto e perguntar se pode continuar. Aguardar autorização da nova etapa, sem reconfirmar passos internos já autorizados.

## Prévia anterior — evidência de teste, não diagnóstico da base definitiva

`backend/contaazul_previa_clientes.py` gerou CSV protegido `.venv/contaazul/producao/previas/clientes-nfse-202610.csv`: uma sugestão, 135 notas sem cadastro (110 CNPJs distintos), três documentos não conferidos. PostgreSQL local: três clientes, três CNPJs atuais e um encerrado. Resultado esperado de uma base de teste incompleta/imprecisa; não usar como justificativa para cadastrar 110 clientes.

Nenhum vínculo gravado. ZIP preservado por hash. Apenas consulta PostgreSQL READ ONLY com timeout e parâmetros. Relatório não sobrescrito/fora do Git; contém índice/número da nota e nome/ID apenas quando sugerido. Não expor conteúdo no chat/commit. 54 testes simulados passaram na etapa anterior; prévia real foi exclusivamente de leitura, não teste de escrita/rollback/SQLite.

## Resultado confirmado em 07/10/2026

Usuário autorizou implementar conferência de NFS-e e indicou `C:/Users/didit/Downloads/NFSe-10-2026 (2).zip`; outubro/2026 inferido do nome e comunicado. ZIP contém 139 PDFs + 139 XMLs. Todos os 139 pares passaram nas verificações locais; arquivo preservado por hash antes/depois.

Primeira comparação retornou HTTP 401 e parou sem repetição. Verificada somente existência de tokens-pendentes.env: ausente. Usuário renovou manualmente e informou sucesso. Repetição manual concluída: **136 notas reconhecidas, três pendentes por status**. Consulta adicional agregada confirmou **136 EMITIDA e três CANCELAMENTO_MANUAL**; a prévia posterior manteve esse resultado. Somente EMITIDA é aceita; as três permanecem pendentes sem alteração de regra ou documento. Nenhum número de nota, CNPJ, nome ou valor exposto no chat; nenhuma resposta da API persistida. Não repetir consultas para confirmar esse resultado novamente.

## Código e limites

`backend/contaazul_nfse.py` e `backend/test_contaazul_nfse.py`: somente leitura do ZIP e GETs na API, sem extração/gravação/renomeação, sem banco, contratos ou envio. Pareia PDF/XML por nome-base, recusa duplicidade, exige número, RPS, tomador e valor Decimal. XML UTF-8 sem DTD/entidades; suporta namespace nacional e estrutura infNFSe/DPS no namespace ABRASF observada no ZIP real. Número único/status EMITIDA/RPS/documento/valor devem conferir com a API.

PDF tem apenas assinatura, marcador final e nome do par conferidos; conteúdo textual do PDF, assinatura digital e autenticidade fiscal não são validados. Não prometer que o conteúdo de cada PDF foi auditado.

Limites: ZIP 100 MiB compactado e soma descompactada, até 2.000 entradas; XML 2 MiB/PDF 10 MiB; JSON 2 MiB por resposta. Janelas de até 15 datas inclusivas, até 10 páginas de 50 itens por janela (máximo 30 GETs/mês). Paginação incompleta interrompe sem falso sucesso. Sem redirects/renovação/repetição automática. Retornos: 0 todas reconhecidas com pelo menos uma, 2 pendências/nenhuma, 1 falha técnica. Console usa índices anônimos; durante teste real foi mostrado apenas resumo/motivos agregados.

Comando (não repetir sem propósito):

```powershell
.\.venv\Scripts\python.exe backend/contaazul_nfse.py --producao --competencia 2026-10 --zip "C:\Users\didit\Downloads\NFSe-10-2026 (2).zip"
```

45 testes Conta Azul passaram (17 autenticação/consulta/ambientes, 12 boleto, 16 NFS-e). São testes com rede simulada e ZIPs fictícios; nenhum SQLite/PostgreSQL ou migration foi necessário. Ajuda e diff conferidos. Referência `C:/dev/manutec-faturamento` consultada apenas para leitura; nenhum arquivo ou credencial desse projeto alterado/executado/lido indevidamente.

## Boleto já concluído

`backend/contaazul_boleto.py` baixa um boleto existente pela operação oficial GET `/v1/financeiro/eventos-financeiros/contas-a-receber/cobranca/{id_cobranca}/imprimir`. Única conta PENDING por vencimento/valor e única cobrança REGISTRADO; página cheia com 10 recebíveis ou seleção ambígua interrompe. Até 10 solicitações por parcela; máximo 13 GETs. JSON 1 MiB/PDF 10 MiB. Arquivo existente interrompe antes da rede; publicação por hard link exclusivo preserva concorrência. Sem emissão/reemissão/cancelamento/pagamento/envio.

Teste autorizado do boleto de R$ 1.500,00, vencimento 13/10/2026, concluído em 06/10: conta única entre cinco, duas cobranças (REGISTRADO e CANCELADO). PDF salvo em `.venv/contaazul/producao/downloads/boleto-20261013.pdf`, protegido/ignorado. Uma página, 98.897 bytes, leitura estrita pypdf sem avisos. Texto normalizado igual ao download manual e valor/vencimento presentes; bytes diferem, motivo não investigado. Não baixar/remover novamente para repetir teste.

A investigação anterior do navegador fica superada pelo download direto comprovado. Primeira amostra QUITADO exibiu erro de link, sem causa raiz estabelecida. Sonda temporária `.venv/contaazul/producao/verificar_link.py` tem período fixo e escolhe primeira parcela; não usar preventivamente.

## Acesso, dados e Git

Configurações ignoradas e protegidas: desenvolvimento `.venv/contaazul/credenciais.env`; produção `.venv/contaazul/producao/credenciais.env`. `--producao` obrigatório para conta real; sem fallback. Não exibir ou ler valores de credenciais. Token determina a empresa, flag seleciona arquivo. Autorização inicial de produção já concluída; não repeti-la como pendência. HTTP 401: orientar renovação manual com `backend/contaazul_auth.py --producao`, conferindo previamente apenas existência de tokens-pendentes.env; nunca sobrescrever tokens pendentes.

Callback de produção publicado pelo usuário via cPanel: https://manutecvalvulas.com.br/contaazul/callback/ . Configuração de desenvolvimento preservada; conta de teste vazia. Erro fiscal HTTP 500 anterior em desenvolvimento não tem causa comprovada. Não criar documentos para testes.

As instruções atuais reapresentadas pelo usuário em 07/10/2026 determinam revisar, testar, commitar e fazer push ao concluir a etapa, sem nova confirmação. A suspensão da pausa anterior constava de documentos antigos; foi conciliada com a orientação atual. Não incluir ZIP/PDF, credenciais ou respostas da API no Git. Branch main, remoto origin. Consultar git log/status para resultado da publicação desta etapa; não registrar sucesso de push antecipadamente.

Arquivos da etapa acumulada: AGENTS.md, PROJECT_STATE.md, SESSION_HANDOFF.md, backend/README.md, docs/PREPARACAO_ENVIO_DOCUMENTOS.md; auth/consulta com seleção de produção; novos contaazul_boleto.py, contaazul_nfse.py e testes de ambientes/boleto/NFS-e no commit anterior 4acb467; etapa atual acrescenta contaazul_previa_clientes.py e test_contaazul_previa_clientes.py. Alterações anteriores do projeto foram preservadas. Fonte de referência não modificada.

## Projeto preservado

Painel de destinatários concluído e aceito, incluindo lista própria do usuário. Cinco categorias independentes, revisões e encerramento local/global, sem reativação automática nem envio. Migration 0007 aplicada ao PostgreSQL instalado com legado vazio e dados/concessões preservados. Validações anteriores: 49 testes SQLite, 11 verificações PostgreSQL isoladas e inspeção visual; não confundir com validações desta integração. Não alterar cliente usado na aceitação. Servidor localhost:8000 deve ser conferido antes de uso.

Backup protegido `.venv/backups/pre_0007_20260928/pre_0007.dump`, hash em verification.json; preservar antes de recriar .venv. Recuperação somente em banco vazio separado, conforme README; não reverter migration automaticamente.

Obtenção direta de arquivo NFS-e via API ainda não comprovada: fluxo atual usa ZIP fornecido. Prévia local de associação de NFS-e por CNPJ atual preservada, mas seu uso/alinhamento está adiado até a base definitiva. Desenho de anexos/conferência proposto; associação persistida, boletos, integração ao painel e envio continuam por definir/implementar. SMTP de domínio próprio via cPanel é direção, dados pendentes. IA e pasta monitorada adiadas.
