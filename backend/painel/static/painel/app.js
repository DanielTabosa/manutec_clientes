// Interface de operação: menu móvel, confirmações e conferência antes de confirmar. O servidor valida tudo de novo.
document.addEventListener('DOMContentLoaded', () => {
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

  // Evita envio duplo: desabilita o botão após o primeiro clique válido.
  document.querySelectorAll('form[method="post"]').forEach(form => {
    form.addEventListener('submit', e => {
      if (e.defaultPrevented) return;
      const enviado = e.submitter;
      if (enviado) setTimeout(() => { enviado.disabled = true; enviado.setAttribute('aria-busy', 'true'); }, 0);
    });
  });
});
