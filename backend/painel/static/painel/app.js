// Interface de operação: menu móvel, busca rápida, avisos, etapas, PDF lateral e confirmações.
// Tudo é complemento: sem JavaScript as páginas e formulários continuam funcionando; o servidor valida de novo.
document.addEventListener('DOMContentLoaded', () => {
  // Menu móvel
  const menu = document.getElementById('menu');
  const botao = document.querySelector('[data-abrir-menu]');
  if (menu && botao) {
    let fundo = null;
    const fechar = () => { menu.classList.remove('aberto'); botao.setAttribute('aria-expanded', 'false'); fundo?.remove(); fundo = null; };
    botao.addEventListener('click', () => {
      if (menu.classList.contains('aberto')) return fechar();
      menu.classList.add('aberto'); botao.setAttribute('aria-expanded', 'true');
      fundo = document.createElement('div'); fundo.className = 'nav-backdrop'; fundo.addEventListener('click', fechar);
      document.body.append(fundo);
      menu.querySelector('a')?.focus();
    });
    document.addEventListener('keydown', e => { if (e.key === 'Escape' && menu.classList.contains('aberto')) { fechar(); botao.focus(); } });
  }

  // Busca global: Ctrl+K / Cmd+K ou "/" fora de campos
  const busca = document.getElementById('busca-global');
  document.addEventListener('keydown', e => {
    const emCampo = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement?.tagName || '');
    if (busca && ((e.key.toLowerCase() === 'k' && (e.ctrlKey || e.metaKey)) || (e.key === '/' && !emCampo))) {
      e.preventDefault(); busca.focus(); busca.select();
    }
  });

  // Barra superior ganha borda ao rolar
  const barra = document.querySelector('.barra');
  if (barra) {
    const marcar = () => barra.classList.toggle('rolou', window.scrollY > 4);
    window.addEventListener('scroll', marcar, {passive: true}); marcar();
  }

  // Avisos flutuantes: fecham sozinhos (erros ficam até fechar)
  document.querySelectorAll('[data-toast]').forEach((aviso, i) => {
    const sair = () => { aviso.classList.add('saindo'); aviso.addEventListener('animationend', () => aviso.remove(), {once: true}); setTimeout(() => aviso.remove(), 400); };
    aviso.querySelector('.toast-fechar')?.addEventListener('click', sair);
    if (!aviso.classList.contains('alert-error')) setTimeout(sair, 5200 + i * 600);
  });

  // Etapas da preparação: destaca a etapa visível
  const passos = [...document.querySelectorAll('[data-passo]')];
  if (passos.length && 'IntersectionObserver' in window) {
    const alvos = passos.map(a => document.querySelector(a.getAttribute('href'))).filter(Boolean);
    const ativar = id => passos.forEach(a => a.classList.toggle('ativo', a.getAttribute('href') === '#' + id));
    const obs = new IntersectionObserver(entradas => {
      const visivel = entradas.filter(e => e.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0];
      if (visivel) ativar(visivel.target.id);
    }, {rootMargin: '-140px 0px -55% 0px'});
    alvos.forEach(a => obs.observe(a));
    ativar(alvos[0]?.id);
  }

  // PDF no painel lateral
  const gaveta = document.getElementById('gaveta-pdf');
  if (gaveta && typeof gaveta.showModal === 'function') {
    const quadro = gaveta.querySelector('iframe');
    document.addEventListener('click', e => {
      const link = e.target.closest('a[data-pdf]');
      if (!link || e.ctrlKey || e.metaKey || e.shiftKey || window.innerWidth < 700) return;
      e.preventDefault();
      gaveta.querySelector('#gaveta-titulo').textContent = link.dataset.pdf;
      gaveta.querySelector('#gaveta-abrir').href = link.href;
      quadro.src = link.href;
      gaveta.showModal();
    });
    gaveta.querySelector('[data-fechar-gaveta]').addEventListener('click', () => gaveta.close());
    gaveta.addEventListener('click', e => { if (e.target === gaveta) gaveta.close(); });
    gaveta.addEventListener('close', () => { quadro.src = 'about:blank'; });
  }

  // Arrastar PDFs para a área de anexos
  document.querySelectorAll('.dropzone').forEach(zona => {
    const campo = zona.querySelector('input[type="file"]');
    ['dragenter', 'dragover'].forEach(t => zona.addEventListener(t, e => { e.preventDefault(); zona.classList.add('arrastando'); }));
    ['dragleave', 'drop'].forEach(t => zona.addEventListener(t, e => { e.preventDefault(); zona.classList.remove('arrastando'); }));
    zona.addEventListener('drop', e => { if (campo && e.dataTransfer?.files.length) campo.files = e.dataTransfer.files; });
  });

  // Conferência antes de confirmar
  const conferido = document.getElementById('conferido');
  const confirmar = document.getElementById('confirmar');
  if (conferido && confirmar && !confirmar.disabled) {
    const atualizar = () => { confirmar.disabled = !conferido.checked; };
    conferido.addEventListener('change', atualizar);
    ['assunto', 'mensagem', 'motivo_reenvio'].forEach(id => {
      document.getElementById(id)?.addEventListener('input', () => { conferido.checked = false; atualizar(); });
    });
    atualizar();
  }

  document.querySelectorAll('[data-confirmar-acao]').forEach(form => {
    form.addEventListener('submit', e => { if (!window.confirm(form.dataset.confirmarAcao)) e.preventDefault(); });
  });

  // Carregamento no botão e proteção contra envio duplo
  document.querySelectorAll('form[method="post"]').forEach(form => {
    form.addEventListener('submit', e => {
      if (e.defaultPrevented) return;
      const enviado = e.submitter;
      if (enviado) setTimeout(() => { enviado.disabled = true; enviado.setAttribute('aria-busy', 'true'); }, 0);
    });
  });
});

// Ao voltar pelo histórico, reativa botões que ficaram em carregamento
window.addEventListener('pageshow', e => {
  if (e.persisted) document.querySelectorAll('[aria-busy="true"]').forEach(b => { b.disabled = false; b.removeAttribute('aria-busy'); });
});
