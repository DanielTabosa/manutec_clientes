# Banco de dados

Consultar em alterações de PostgreSQL, schema, migrations ou modelo persistido.

- Avaliar PK/FK, constraints, índices, históricos e integridade.
- Considerar tabelas preexistentes e modelos `managed=False`; não presumir que migrations recriem o domínio.
- Explicar impacto nos dados existentes, compatibilidade e estratégia de validação antes de mudanças.
- Distinguir garantias do banco de validações da aplicação e testes SQLite.

Entrega: avaliação do modelo e alterações estritamente autorizadas; não alterar banco ou criar migrations por antecipação.
