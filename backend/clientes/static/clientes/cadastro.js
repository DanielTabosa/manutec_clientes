(() => {
  const form = document.getElementById('cadastro-cliente');
  const cnpj = document.getElementById('id_cnpj');
  if (!cnpj) return;
  const url = form?.dataset.consultaUrl || document.getElementById('consulta-cnpj-script')?.dataset.url;
  if (!url) return;
  let status = document.getElementById('consulta-status');
  let button = document.getElementById('consultar-cnpj');
  if (!status) {
    status = document.createElement('p');
    status.setAttribute('role', 'status'); status.setAttribute('aria-live', 'polite');
    button = document.createElement('button'); button.type = 'button'; button.textContent = 'Consultar CNPJ';
    cnpj.after(button, status);
  }
  const preview = document.createElement('p'); status.after(preview);
  const normalize = value => value.replace(/[.\s/-]/g, '').toUpperCase();
  let controller, timer, last = '', version = 0;
  const autoValues = {};
  const fields = ['razao_social', 'nome_fantasia', 'logradouro', 'numero', 'complemento', 'bairro', 'cidade', 'estado', 'cep', 'telefone', 'email'].filter(name => document.getElementById('id_' + name));
  let addressVersion = 0;
  document.addEventListener('cep-alterado', () => { addressVersion++; });
  async function consultar(force = false) {
    const value = normalize(cnpj.value);
    if (!/^[A-Z0-9]{12}[0-9]{2}$/.test(value)) {
      if (force) status.textContent = 'Preencha o CNPJ completo para consultar.';
      return;
    }
    if (!force && value === last) return;
    last = value;
    const requestVersion = ++version;
    const startingAddressVersion = addressVersion;
    document.dispatchEvent(new Event('cnpj-consultando'));
    controller?.abort();
    controller = new AbortController();
    const before = Object.fromEntries(fields.map(name => [name, document.getElementById('id_' + name).value]));
    status.textContent = 'Consultando CNPJ…';
    try {
      const response = await fetch(url + '?cnpj=' + encodeURIComponent(value), {signal: controller.signal});
      const data = await response.json();
      if (normalize(cnpj.value) !== value || version !== requestVersion) return;
      if (!response.ok) throw new Error(data.erro || 'Consulta indisponível. Preencha os dados manualmente.');
      let preserved = false;
      preview.textContent = fields.includes('logradouro') ? '' : ['Dados consultados: ' + (data.razao_social || 'Razão social não informada'), data.nome_fantasia, data.logradouro, data.numero, data.complemento, data.bairro, data.cidade, data.estado, data.cep].filter(Boolean).join(' · ');
      for (const name of fields) {
        if (addressVersion !== startingAddressVersion && !['razao_social', 'nome_fantasia'].includes(name)) { preserved = true; continue; }
        const input = document.getElementById('id_' + name);
        if (input.value === before[name]) {
          input.value = data[name] || '';
          autoValues[name] = input.value;
        }
        else preserved = true;
      }
      status.textContent = 'Consulta concluída. Confira os dados antes de salvar.' + (preserved ? ' Alterações feitas durante a consulta foram preservadas.' : '');
    } catch (error) {
      if (error.name !== 'AbortError' && normalize(cnpj.value) === value) {
        last = '';
        status.textContent = error.message;
      }
    }
  }
  cnpj.addEventListener('input', () => {
    controller?.abort(); version++; last = ''; clearTimeout(timer);
    preview.textContent = '';
    for (const name of fields) {
      const input = document.getElementById('id_' + name);
      if (name in autoValues && input.value === autoValues[name]) input.value = '';
      delete autoValues[name];
    }
    status.textContent = ''; timer = setTimeout(() => consultar(), 500);
  });
  cnpj.addEventListener('blur', () => consultar());
  button.addEventListener('click', () => consultar(true));
})();
