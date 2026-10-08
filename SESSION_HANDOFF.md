# Retomada — protótipo autorizado, implementação pausada

## Encerramento em 07/10/2026

Usuário pediu atualizar o handoff e encerrar por hoje. O protótipo navegável já foi autorizado com “sim”; retomar quando solicitado, sem pedir novamente aprovação do desenho.

## Ponto exato de retomada

A interface ainda NÃO foi criada. Existe apenas o roteiro inicial `backend/verificar_prototipo_documentos.cjs`, não integrado à suíte automática. Primeira execução Playwright falhou com ERR_FILE_NOT_FOUND porque falta `docs/prototipos/documentos/index.html`; não apresentar como teste aprovado ou protótipo entregue.

Próxima ação: implementar esse HTML separado do painel Django, com cliente, contatos e PDFs inteiramente fictícios. Fluxo aprovado: escolher cliente → anexar/classificar boleto e/ou nota → conferir anexos por destinatário → revisar assunto/texto e confirmar. Ana recebe ambos, Bruno boleto, Carla nota; Davi sem e-mail aparece impedido. Categorias independentes, sem mudar configurações silenciosamente. Ação final “Simular preparação”; nenhuma mensagem enviada. Sem banco, API ou persistência.

O roteiro cobre categorias, falta de e-mail, confirmação, retorno à revisão, remoção, PDF inválido, visualização, mobile e ausência de requisições HTTP. Depois de implementar, executar e inspecionar screenshots. Node disponível em `C:/Users/didit/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe`; NODE_PATH deve apontar para `C:/Users/didit/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules`. Playwright com chromium channel msedge iniciou com sucesso. QA_SCREENSHOT_DIR opcional deve ficar sob `.venv`, ignorado. Servir somente a pasta do protótipo em localhost para demonstração.

## Decisões preservadas

- Clientes atuais são reais, mas cadastros de teste possivelmente imprecisos. Associação/alinhamento só após preenchimento da base definitiva. Não repetir consultas, preparar lista de faltantes, importar ou corrigir cadastros pela prévia anterior.
- Painel de destinatários concluído e aceito; cinco categorias independentes. Contatos sem e-mail podem existir, mas não receber e-mail. Preservar regras e dados.
- Desenho em `docs/PREPARACAO_ENVIO_DOCUMENTOS.md`. Envio real, SMTP, associação persistida e integração ao painel continuam pendentes. Não implementar automaticamente.
- Ao concluir tarefas: resultado, próximo passo concreto e perguntar se pode continuar. Commit/push rotineiros autorizados. Nesta sessão respeitar encerramento, sem iniciar etapa nova.

## Evidências anteriores

- `backend/contaazul_boleto.py`: download direto comprovado, PDF ignorado `.venv/contaazul/producao/downloads/boleto-20261013.pdf`. Não repetir download preventivamente.
- `backend/contaazul_nfse.py`: ZIP `C:/Users/didit/Downloads/NFSe-10-2026 (2).zip` preservado, 139 pares locais válidos, 136 notas reconhecidas e três CANCELAMENTO_MANUAL. Conteúdo textual/autenticidade dos PDFs não auditados.
- `backend/contaazul_previa_clientes.py`: PostgreSQL READ ONLY, nenhum vínculo persistido. CSV ignorado `.venv/contaazul/producao/previas/clientes-nfse-202610.csv`: uma sugestão, 135 notas sem cadastro (110 CNPJs), três não conferidas. Resultado de base de teste; não diagnosticar base definitiva. Não sobrescrever ou expor relatório.
- 54 testes Conta Azul simulados passaram anteriormente. Leitura PostgreSQL não valida escrita ou SQLite. Não há necessidade de banco/migrations para este encerramento ou protótipo.
- Commits anteriores: 4acb467 download/conferência; 91cfa9b prévia; 8c5b1f2 adiamento do alinhamento/desenho.

## Ambiente e segurança

Não ler/expor credenciais sob `.venv/contaazul`. Produção exige --producao, sem fallback. Autorização já concluída; não repetir preventivamente. HTTP 401: conferir apenas existência de tokens-pendentes.env e orientar renovação manual, sem sobrescrever tokens pendentes.

Preservar backup `.venv/backups/pre_0007_20260928/pre_0007.dump` e verification.json. Migration 0007 já aplicada. `C:/dev/manutec-faturamento` foi referência somente de leitura.

Branch main, remoto origin. Shell escalado pode exigir `git -c safe.directory=C:/dev/manutec-clientes ...` por diferença de proprietário; usar exceção por comando. Conferir status/log para publicação do encerramento. Validar conteúdo/diff e sintaxe do roteiro; validação funcional continua pendente até existir interface.
