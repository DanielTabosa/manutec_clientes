(() => {
  const mode = document.getElementById('id_modo');
  const updateHelp = () => document.querySelectorAll('[data-modo]').forEach(p => {
    p.hidden = p.dataset.modo !== mode?.value;
  });
  mode?.addEventListener('change', updateHelp);
  updateHelp();
  document.querySelectorAll('[data-destinatario]').forEach(row => {
    const categories = [...row.querySelectorAll('[data-categoria]')];
    const all = row.querySelector('[data-todas]');
    const stop = row.querySelector('input[name$="-encerrado_local"]');
    const readonly = row.closest('table').dataset.podeEditar !== 'true';
    const sync = () => {
      const count = categories.filter(input => input.checked).length;
      all.checked = count === categories.length;
      all.indeterminate = count > 0 && count < categories.length;
      all.disabled = readonly || Boolean(stop?.checked);
      categories.forEach(input => { input.disabled = readonly || Boolean(stop?.checked); });
      if (stop) stop.disabled = readonly;
    };
    all.addEventListener('change', () => {
      categories.forEach(input => { input.checked = all.checked; });
      sync();
    });
    categories.forEach(input => input.addEventListener('change', sync));
    stop?.addEventListener('change', () => {
      if (stop.checked) categories.forEach(input => { input.checked = false; });
      sync();
    });
    sync();
  });
})();
