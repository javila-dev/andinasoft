/* Entrega el token al panel que abrió esta ventana (mismo origen) y se cierra. */
(function () {
  'use strict';

  var token = document.body.dataset.token || '';
  document.body.removeAttribute('data-token');

  if (window.opener && token) {
    window.opener.postMessage({ type: 'andinasoft-panel-token', token: token }, window.location.origin);
    window.setTimeout(function () {
      window.close();
    }, 600);
  } else {
    document.getElementById('conectado-texto').textContent =
      'No se encontró el panel de Chatwoot que abrió esta ventana. Ciérrala y pulsa «Conectar con Andinasoft» de nuevo.';
  }
})();
