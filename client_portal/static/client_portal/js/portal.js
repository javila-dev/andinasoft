document.documentElement.classList.add('portal-ready');

document.addEventListener('submit', function (event) {
  const form = event.target;
  if (!(form instanceof HTMLFormElement) || !form.hasAttribute('data-loading-submit')) {
    return;
  }

  const button = form.querySelector('[data-submit-button]');
  const label = form.querySelector('[data-submit-label]');
  if (!button) {
    return;
  }

  button.disabled = true;
  button.classList.add('loading');
  if (label) {
    label.textContent = 'Ingresando...';
  }
});
