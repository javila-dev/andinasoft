/*
 * Softphone de Andinasoft (ventana aparte que abre el panel de Chatwoot).
 *
 * - El iframe de Chatwoot no tiene permiso de micrófono: por eso la llamada vive aquí,
 *   en una ventana de primer nivel con la sesión normal de Andinasoft.
 * - El panel (mismo origen) manda la conversación por postMessage. Este lado pide al
 *   servidor los números: el servidor confirma la conversación con Chatwoot y decide
 *   a qué número se marca; el navegador solo elige entre los que el servidor ofrece.
 * - Todo texto se pinta con textContent.
 */
(function () {
  'use strict';

  var LISTO = 'andinasoft-softphone-listo';
  var SOLICITUD = 'andinasoft-softphone-solicitud';
  var RECIBIDO = 'andinasoft-softphone-recibido';
  var FIN = 'andinasoft-softphone-fin';
  var ORIGEN = window.location.origin;
  var LINEA_KEY = 'andinasoft.softphone.linea';
  var LINEA_AUTO = 'auto';

  var cfg = document.body.dataset;
  var state = {
    solicitud: null, // {account_id, conversation_id, contact_id, cedula, nombre}
    destinos: [],
    destino: '',
    llamada: null, // {id, numero, etiqueta}
    device: null,
    call: null,
    contestada: null, // Date
    timer: null,
  };

  function $(id) {
    return document.getElementById(id);
  }

  function show(screen) {
    ['esperando', 'elegir', 'llamada', 'fin'].forEach(function (name) {
      $('screen-' + name).hidden = name !== screen;
    });
  }

  function enLlamada() {
    return !!state.call;
  }

  function api(url, body) {
    var options = { headers: { Accept: 'application/json' }, credentials: 'same-origin', cache: 'no-store' };
    if (body) {
      options.method = 'POST';
      options.headers['Content-Type'] = 'application/json';
      options.headers['X-CSRFToken'] = cfg.csrf;
      options.body = JSON.stringify(body);
    }
    return fetch(url, options).then(function (res) {
      return res.json().then(
        function (data) {
          if (!res.ok) throw new Error(data.detail || 'Error ' + res.status);
          return data;
        },
        function () {
          throw new Error('Respuesta inválida del servidor (' + res.status + '). Recarga esta ventana.');
        }
      );
    });
  }

  function nombreContacto() {
    return (state.solicitud && state.solicitud.nombre) || 'Cliente';
  }

  // ---------- elegir número ----------
  function cargarDestinos() {
    var s = state.solicitud;
    show('elegir');
    $('elegir-contacto').textContent = nombreContacto();
    $('elegir-lista').textContent = 'Cargando números…';
    $('elegir-aviso').hidden = true;
    $('btn-llamar').disabled = true;
    api(cfg.apiDestinos, {
      account_id: s.account_id, conversation_id: s.conversation_id, contact_id: s.contact_id, cedula: s.cedula,
    })
      .then(function (data) {
        if (state.solicitud !== s) return;
        if (data.contacto && !s.nombre) {
          s.nombre = data.contacto;
          $('elegir-contacto').textContent = data.contacto;
        }
        state.destinos = data.destinos || [];
        state.destino = state.destinos.length ? state.destinos[0].id : '';
        $('elegir-grabar').hidden = !data.grabar;
        renderLineas(data.lineas || [], data.linea_auto);
        renderDestinos();
      })
      .catch(function (err) {
        if (state.solicitud !== s) return;
        $('elegir-lista').textContent = '';
        aviso(err.message);
      });
  }

  function aviso(texto) {
    $('elegir-aviso').textContent = texto;
    $('elegir-aviso').hidden = !texto;
  }

  function renderDestinos() {
    var lista = $('elegir-lista');
    lista.textContent = '';
    if (!state.destinos.length) {
      aviso('Este contacto no tiene un número colombiano válido en Chatwoot ni en Andinasoft.');
      return;
    }
    state.destinos.forEach(function (d) {
      var input = document.createElement('input');
      input.type = 'radio';
      input.name = 'destino';
      input.value = d.id;
      input.checked = d.id === state.destino;
      input.addEventListener('change', function () {
        state.destino = d.id;
      });
      var etiqueta = document.createElement('span');
      etiqueta.className = 'phone__option-label';
      etiqueta.textContent = d.etiqueta;
      var numero = document.createElement('span');
      numero.className = 'muted';
      numero.textContent = d.numero;
      var texto = document.createElement('span');
      texto.className = 'phone__option-text';
      texto.appendChild(etiqueta);
      texto.appendChild(numero);
      var label = document.createElement('label');
      label.className = 'phone__option';
      label.appendChild(input);
      label.appendChild(texto);
      lista.appendChild(label);
    });
    $('btn-llamar').disabled = false;
  }

  /* «Llamar desde»: automático (rota entre las líneas) o una línea fija. Se recuerda en este navegador. */
  function renderLineas(lineas, auto) {
    var select = $('elegir-linea');
    select.textContent = '';
    var opciones = (auto ? [{ id: LINEA_AUTO, nombre: 'Automático (rota entre las líneas)', numero: '' }] : []).concat(lineas);
    opciones.forEach(function (l) {
      var option = document.createElement('option');
      option.value = l.id;
      option.textContent = l.numero ? l.nombre + ' · ' + l.numero : l.nombre;
      select.appendChild(option);
    });
    var guardada = '';
    try {
      guardada = window.localStorage.getItem(LINEA_KEY) || '';
    } catch (e) {
      /* almacenamiento bloqueado */
    }
    var ids = opciones.map(function (l) {
      return l.id;
    });
    if (ids.indexOf(guardada) >= 0) select.value = guardada;
    // Con una sola línea no hay nada que elegir.
    $('elegir-linea-campo').hidden = opciones.length < 2;
  }

  function lineaElegida() {
    var valor = $('elegir-linea').value || '';
    try {
      if (valor) window.localStorage.setItem(LINEA_KEY, valor);
    } catch (e) {
      /* almacenamiento bloqueado */
    }
    return valor;
  }

  // ---------- llamada ----------
  function llamar() {
    var s = state.solicitud;
    if (!s || !state.destino || enLlamada()) return;
    $('btn-llamar').disabled = true;
    aviso('');
    api(cfg.apiLlamar, {
      account_id: s.account_id, conversation_id: s.conversation_id, contact_id: s.contact_id, cedula: s.cedula,
      destino: state.destino,
      linea: lineaElegida(),
    })
      .then(function (data) {
        state.llamada = { id: data.llamada, numero: data.numero, etiqueta: data.etiqueta, linea: data.linea };
        return marcar(data.token);
      })
      .catch(function (err) {
        limpiarDevice();
        show('elegir');
        aviso(err.message);
        $('btn-llamar').disabled = false;
      });
  }

  function marcar(token) {
    show('llamada');
    $('llamada-contacto').textContent = nombreContacto();
    $('llamada-numero').textContent = state.llamada.etiqueta + ' · ' + state.llamada.numero +
      (state.llamada.linea ? ' · desde ' + state.llamada.linea : '');
    $('llamada-tiempo').textContent = '0:00';
    estado('Conectando…');
    $('btn-silenciar').disabled = true;
    $('btn-silenciar').setAttribute('aria-pressed', 'false');
    $('btn-silenciar').textContent = 'Silenciar';

    state.device = new window.Twilio.Device(token, { codecPreferences: ['opus', 'pcmu'], closeProtection: true });
    state.device.on('error', function (err) {
      console.warn('softphone: error del dispositivo', err);
    });
    return state.device.connect({ params: { llamada: String(state.llamada.id) } }).then(function (call) {
      state.call = call;
      estado('Llamando…');
      call.on('accept', function () {
        state.contestada = new Date();
        estado('En llamada');
        $('btn-silenciar').disabled = false;
        state.timer = window.setInterval(pintarTiempo, 1000);
      });
      call.on('disconnect', function () {
        terminar();
      });
      call.on('cancel', function () {
        terminar();
      });
      call.on('error', function (err) {
        console.warn('softphone: error de la llamada', err);
        terminar(mensajeError(err));
      });
    }, function (err) {
      throw new Error(mensajeError(err));
    });
  }

  function mensajeError(err) {
    var code = err && err.code;
    if (code === 31401 || code === 31208 || (err && err.name === 'NotAllowedError')) {
      return 'El navegador no dio permiso para usar el micrófono. Permítelo e intenta de nuevo.';
    }
    return 'No se pudo completar la llamada' + (code ? ' (código ' + code + ')' : '') + '.';
  }

  function estado(texto) {
    $('llamada-estado').textContent = texto;
  }

  function pintarTiempo() {
    if (!state.contestada) return;
    var s = Math.floor((Date.now() - state.contestada.getTime()) / 1000);
    $('llamada-tiempo').textContent = Math.floor(s / 60) + ':' + ('0' + (s % 60)).slice(-2);
  }

  function silenciar() {
    if (!state.call) return;
    var mute = !state.call.isMuted();
    state.call.mute(mute);
    $('btn-silenciar').setAttribute('aria-pressed', mute ? 'true' : 'false');
    $('btn-silenciar').textContent = mute ? 'Activar micrófono' : 'Silenciar';
  }

  function colgar() {
    if (state.call) state.call.disconnect();
    else terminar();
  }

  function limpiarDevice() {
    if (state.timer) window.clearInterval(state.timer);
    state.timer = null;
    state.call = null;
    if (state.device) {
      try {
        state.device.destroy();
      } catch (e) {
        /* ya destruido */
      }
    }
    state.device = null;
  }

  function terminar(error) {
    if (!state.llamada || !$('screen-fin').hidden) return;
    var hablada = !!state.contestada;
    limpiarDevice();
    show('fin');
    $('fin-contacto').textContent = nombreContacto();
    $('fin-numero').textContent = state.llamada.etiqueta + ' · ' + state.llamada.numero;
    $('fin-estado').textContent = error || (hablada ? 'Llamada terminada' : 'No contestó');
    $('fin-detalle').textContent = 'Consultando el resultado…';
    $('btn-seguimiento').hidden = !window.opener;
    state.contestada = null;
    consultarResultado(state.llamada.id, 0);
  }

  /* Twilio confirma por webhook unos segundos después de colgar. */
  function consultarResultado(id, intento) {
    api(cfg.apiLlamada + id + '/')
      .then(function (data) {
        if (!state.llamada || state.llamada.id !== id) return;
        if (!data.finalizada && intento < 6) {
          window.setTimeout(function () {
            consultarResultado(id, intento + 1);
          }, 1500);
          return;
        }
        state.llamada.estado = data.estado;
        state.llamada.duracion = data.duracion;
        $('fin-estado').textContent = data.finalizada ? data.estado_texto : $('fin-estado').textContent;
        var partes = [];
        if (data.estado === 'completada') partes.push('Duración ' + Math.floor(data.duracion / 60) + ':' + ('0' + (data.duracion % 60)).slice(-2));
        if (data.finalizada) partes.push(data.nota_privada ? 'Anotada en la conversación.' : 'No se pudo anotar en la conversación.');
        $('fin-detalle').textContent = partes.join(' · ');
      })
      .catch(function () {
        $('fin-detalle').textContent = '';
      });
  }

  function registrarSeguimiento() {
    if (!window.opener || !state.llamada) return;
    window.opener.postMessage({
      type: FIN,
      conversation_id: state.solicitud && state.solicitud.conversation_id,
      llamada: state.llamada.id,
      estado: state.llamada.estado || '',
      duracion: state.llamada.duracion || 0,
    }, ORIGEN);
    $('btn-seguimiento').hidden = true;
    $('fin-detalle').textContent = 'Completa el seguimiento en el panel de Chatwoot.';
  }

  // ---------- mensajes del panel ----------
  function onMessage(event) {
    if (event.origin !== ORIGEN || !event.data || event.data.type !== SOLICITUD) return;
    var s = event.data.solicitud || {};
    if (event.source) event.source.postMessage({ type: RECIBIDO }, ORIGEN);
    if (enLlamada()) return; // primero termina la llamada actual
    state.solicitud = {
      account_id: String(s.account_id || ''),
      conversation_id: String(s.conversation_id || ''),
      contact_id: String(s.contact_id || ''),
      cedula: String(s.cedula || ''),
      nombre: String(s.nombre || ''),
    };
    state.llamada = null;
    state.destinos = [];
    cargarDestinos();
    window.focus();
  }

  window.addEventListener('message', onMessage);
  $('btn-llamar').addEventListener('click', llamar);
  $('btn-silenciar').addEventListener('click', silenciar);
  $('btn-colgar').addEventListener('click', colgar);
  $('btn-seguimiento').addEventListener('click', registrarSeguimiento);
  $('btn-otra').addEventListener('click', function () {
    if (state.solicitud) cargarDestinos();
    else show('esperando');
  });

  if (window.opener) window.opener.postMessage({ type: LISTO }, ORIGEN);
  else $('esperando-texto').textContent = 'Abre esta ventana desde el botón «Llamar» del panel de Andinasoft en Chatwoot.';
})();
