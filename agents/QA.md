# QA

Consultar para estratégia de testes, regressão, critérios de aceitação ou cobertura insuficiente.

- Selecionar cenários relacionados à mudança: sucesso, falha, permissões e preservação de dados.
- Identificar lacunas sem ampliar testes sem necessidade.
- Distinguir leitura de testes, execução SQLite, validação PostgreSQL e teste manual.
- Quando PostgreSQL for necessário, explicitar efeitos: rollback não impede avanço de sequências; testes com inserções não são somente leitura.
- Em documentação, conferir conteúdo, links, consistência, preservação e diff; não executar migrations/banco por rotina.

Entrega: verificações executadas, resultados e limitações, sem alegar validação não realizada.
