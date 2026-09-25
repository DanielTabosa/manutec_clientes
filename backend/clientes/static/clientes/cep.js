(() => {
  const cep = document.getElementById('id_cep');
  if (!cep) return;
  const url = document.getElementById('consulta-cep-script').dataset.url;
  const status = document.createElement('p');
  status.setAttribute('role', 'status');
  status.setAttribute('aria-live', 'polite');
  const button = document.createElement('button');
  button.type = 'button';
  button.textContent = 'Consultar CEP';
  cep.after(button, status);
  const names = ['logradouro', 'bairro', 'cidade', 'estado'];
  const normalize = () => cep.value.trim().replace(/-/g, '');
  let timer, controller, version = 0, last = '';
  function cancel() {
    controller?.abort(); clearTimeout(timer); version++; last = '';
    status.textContent = '';
  }
  // O CNPJ preenche seu próprio endereço: uma consulta antiga de CEP não deve sobrescrevê-lo.
  document.getElementById('id_cnpj')?.addEventListener('input', cancel);
  document.addEventListener('cnpj-consultando', cancel);
  async function consultar(force = false) {
    const value = normalize();
    if (!/^[0-9]{8}$/.test(value)) {
      if (force) status.textContent = 'Informe um CEP com 8 números.';
      return;
    }
    if (!force && last === value) return;
    last = value; controller?.abort(); controller = new AbortController();
    const current = ++version;
    const before = Object.fromEntries(names.map(name => [name, document.getElementById('id_' + name).value]));
    status.textContent = 'Consultando CEP…';
    try {
      const response = await fetch(url + '?cep=' + encodeURIComponent(value), {signal: controller.signal});
      const data = await response.json();
      if (version !== current || normalize() !== value) return;
      if (!response.ok) throw new Error(data.erro || 'Consulta indisponível. Preencha o endereço manualmente.');
      for (const name of names) {
        const field = document.getElementById('id_' + name);
        if (field.value === before[name]) field.value = data[name] || '';
      }
      status.textContent = 'Endereço carregado. Confira os campos e complete os que estiverem vazios. Número e complemento foram preservados.';
    } catch (error) {
      if (error.name !== 'AbortError' && version === current && normalize() === value) {
        last = ''; status.textContent = error.message;
      }
    }
  }
  cep.addEventListener('input', () => { cancel(); document.dispatchEvent(new Event('cep-alterado')); timer = setTimeout(() => consultar(), 500); });
  cep.addEventListener('blur', () => consultar());
  button.addEventListener('click', () => consultar(true));
})();
