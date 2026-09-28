(() => {
  const key = 'manutec:retorno:' + location.pathname;
  document.querySelectorAll('[data-retornar-cliente]').forEach(link => {
    link.addEventListener('click', event => {
      if (event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
      try { sessionStorage.setItem(key, JSON.stringify({y: window.scrollY, at: Date.now()})); } catch (_) {}
    });
  });
  window.addEventListener('pageshow', () => {
    try {
      const saved = JSON.parse(sessionStorage.getItem(key));
      sessionStorage.removeItem(key);
      if (saved && Date.now() - saved.at < 3600000 && Number.isFinite(saved.y)) {
        requestAnimationFrame(() => window.scrollTo(0, saved.y));
      }
    } catch (_) {}
  });
})();
