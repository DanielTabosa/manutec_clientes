(() => {
  // Cadastro de cliente: mostra CNPJ (pessoa jurídica) ou CPF (pessoa física).
  const tipo = document.getElementById('id_tipo_pessoa');
  if (!tipo) return;
  const linha = name => document.getElementById('id_' + name)?.closest('[data-campo], .form-row');
  const atualizar = () => {
    const pf = tipo.value === 'PF';
    for (const name of ['cnpj', 'data_inicio', 'nome_fantasia']) { const el = linha(name); if (el) el.hidden = pf; }
    const cpf = linha('cpf'); if (cpf) cpf.hidden = !pf;
  };
  tipo.addEventListener('change', atualizar);
  atualizar();
})();
