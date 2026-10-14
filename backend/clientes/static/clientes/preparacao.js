// Confirmação exige nova conferência após qualquer mudança no texto; o servidor valida de novo.
document.addEventListener('DOMContentLoaded', () => {
  const conferido = document.getElementById('conferido');
  const confirmar = document.getElementById('confirmar');
  if (conferido && confirmar && !confirmar.disabled) {
    const atualizar = () => { confirmar.disabled = !conferido.checked; };
    conferido.addEventListener('change', atualizar);
    ['assunto', 'mensagem', 'motivo_reenvio'].forEach(id => {
      const campo = document.getElementById(id);
      if (campo) campo.addEventListener('input', () => { conferido.checked = false; atualizar(); });
    });
    atualizar();
  }
  document.querySelectorAll('[data-confirmar-acao]').forEach(form => {
    form.addEventListener('submit', event => {
      if (!window.confirm(form.dataset.confirmarAcao)) event.preventDefault();
    });
  });
});
