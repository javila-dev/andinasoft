/*
 * Panel de cartera embebido en Chatwoot (Dashboard App).
 *
 * - Chatwoot envía el contexto (contacto, conversación, agente, tema) por postMessage.
 *   Solo se aceptan mensajes del origen configurado; el contexto dice QUÉ mostrar,
 *   nunca autoriza nada.
 * - La autorización es un token Bearer que entrega la ventana /chatwoot/conectar/
 *   (mismo origen que este panel) y se guarda en localStorage.
 * - Todo texto que viene de Chatwoot o de Andinasoft se pinta con textContent (nunca innerHTML).
 */
(function () {
  'use strict';

  var FETCH_INFO = 'chatwoot-dashboard-app:fetch-info';
  var TOKEN_KEY = 'andinasoft.chatwootPanel.token';
  var TOKEN_MESSAGE = 'andinasoft-panel-token';
  var ATRIBUTO_CEDULA = 'cedula_andinasoft';

  var cfg = document.body.dataset;
  var chatwootOrigin = cfg.chatwootOrigin || '';
  var debug = cfg.debug === '1';
  var embedded = window.parent !== window;

  var state = {
    token: readToken(),
    user: null,
    context: null,
    contextKey: '',
    ident: null, // respuesta de /api/contexto/
    identLoading: false,
    identError: '',
    buscando: false,
    busqueda: null, // {q, candidatos}
    negocio: null, // {proyecto, adj}
    cartera: null,
    carteraLoading: false,
    carteraError: '',
    promesa: null,
    promesaLoading: false,
    promesaError: '',
    documentos: null,
    documentosLoading: false,
    documentosError: '',
    docActivo: null,
    docLoading: false,
    docError: '',
    docUrl: '', // blob: del PDF abierto
    visor: null,
    seg: null, // {tipos, formas, forma_por_defecto, seguimientos}
    segLoading: false,
    segError: '',
    segSaving: false,
    segMsg: null, // {tipo: 'ok'|'error', texto}
    segForm: null, // nodo del formulario, se conserva entre renders para no perder lo escrito
    tab: 'cartera',
    aviso: '',
  };

  var money = new Intl.NumberFormat('es-CO', { style: 'currency', currency: 'COP', maximumFractionDigits: 0 });
  var dateFmt = new Intl.DateTimeFormat('es-CO', { day: '2-digit', month: 'short', year: 'numeric', timeZone: 'UTC' });

  function $(id) {
    return document.getElementById(id);
  }

  function fmtMoney(value) {
    var n = Number(value || 0);
    return money.format(isNaN(n) ? 0 : n);
  }

  function fmtDate(iso) {
    if (!iso) return '—';
    var d = new Date(iso + 'T00:00:00Z');
    return isNaN(d.getTime()) ? iso : dateFmt.format(d);
  }

  /* Crea un elemento. children: texto, nodos o arrays; los textos van como textContent. */
  function el(tag, attrs, children) {
    var node = document.createElement(tag);
    attrs = attrs || {};
    Object.keys(attrs).forEach(function (key) {
      var value = attrs[key];
      if (value === null || value === undefined || value === false) return;
      if (key === 'class') node.className = value;
      else if (key === 'text') node.textContent = value;
      else if (key.indexOf('on') === 0) node.addEventListener(key.slice(2), value);
      else node.setAttribute(key, value === true ? '' : value);
    });
    append(node, children);
    return node;
  }

  function append(node, children) {
    if (children === null || children === undefined || children === false) return;
    if (Array.isArray(children)) {
      children.forEach(function (child) {
        append(node, child);
      });
    } else if (children instanceof Node) {
      node.appendChild(children);
    } else {
      node.appendChild(document.createTextNode(String(children)));
    }
  }

  function mount(root, children) {
    root.textContent = '';
    append(root, children);
  }

  // ---------- token ----------
  function readToken() {
    try {
      return window.localStorage.getItem(TOKEN_KEY) || '';
    } catch (e) {
      return '';
    }
  }

  function saveToken(token) {
    state.token = token || '';
    try {
      if (token) window.localStorage.setItem(TOKEN_KEY, token);
      else window.localStorage.removeItem(TOKEN_KEY);
    } catch (e) {
      /* almacenamiento bloqueado: el token vive solo en memoria */
    }
  }

  function api(url, options) {
    options = options || {};
    var headers = { Accept: 'application/json' };
    headers.Authorization = 'Bearer ' + state.token;
    // Solo en desarrollo: el túnel gratuito de ngrok intercepta las peticiones con una página de aviso.
    if (debug) headers['ngrok-skip-browser-warning'] = '1';
    if (options.body) headers['Content-Type'] = 'application/json';
    return fetch(url, {
      method: options.method || 'GET',
      headers: headers,
      body: options.body ? JSON.stringify(options.body) : undefined,
      credentials: 'omit',
      cache: 'no-store',
    }).then(function (res) {
      if (res.status === 401) {
        saveToken('');
        state.user = null;
        render();
        throw new Error('no-autorizado');
      }
      return res.json().then(
        function (data) {
          if (!res.ok) throw new Error(data.detail || 'Error ' + res.status);
          return data;
        },
        function () {
          throw new Error('Respuesta inválida del servidor (' + res.status + ').');
        }
      );
    });
  }

  function negocioUrl(negocio, recurso) {
    return cfg.apiNegocio + encodeURIComponent(negocio.proyecto) + '/' + encodeURIComponent(negocio.adj) + '/' + recurso + '/';
  }

  // ---------- contexto de Chatwoot ----------
  function chatwootContact() {
    var ctx = state.context || {};
    return ctx.contact || (ctx.conversation && ctx.conversation.meta && ctx.conversation.meta.sender) || {};
  }

  function chatwootIds() {
    var ctx = state.context || {};
    var conversation = ctx.conversation || {};
    var contact = chatwootContact();
    return {
      account_id: conversation.account_id || '',
      contact_id: contact.id || '',
      conversation_id: conversation.id || '',
    };
  }

  // ---------- pantallas ----------
  function show(screen) {
    ['config', 'cargando', 'conectar', 'app'].forEach(function (name) {
      $('screen-' + name).hidden = name !== screen;
    });
  }

  function render() {
    if (!chatwootOrigin) return show('config');
    if (!state.token) return show('conectar');
    if (!state.user) return show('cargando');
    show('app');
    renderSession();
    renderAgente();
    renderCliente();
    renderTabs();
    renderCartera();
    renderPromesa();
    renderDocumentos();
    renderSeguimiento();
  }

  function renderSession() {
    $('session-user').textContent = state.user ? 'Conectado como ' + state.user.nombre : '';
  }

  /* El nombre y teléfono del contacto ya los muestra Chatwoot arriba; aquí solo el aviso de agente. */
  function renderAgente() {
    var agent = (state.context || {}).currentAgent || {};
    var banner = $('banner-agente');
    var mismatch = state.user && state.user.email && agent.email &&
      state.user.email.toLowerCase() !== String(agent.email).toLowerCase();
    banner.hidden = !mismatch;
    if (mismatch) {
      $('banner-agente-text').textContent =
        'Estás en Chatwoot como ' + agent.email + ' pero el panel está conectado como ' +
        state.user.email + '. Si no eres tú, pulsa «Desconectar».';
    }
  }

  // ---------- identificación del cliente ----------
  function cargarContexto(extra) {
    var contact = chatwootContact();
    var attrs = contact.custom_attributes || {};
    var body = Object.assign(chatwootIds(), {
      telefono: contact.phone_number || '',
      cedula_atributo: attrs[ATRIBUTO_CEDULA] || '',
    }, extra || {});
    state.identLoading = true;
    state.identError = '';
    state.busqueda = null;
    render();
    return api(cfg.apiContexto, { method: 'POST', body: body })
      .then(function (data) {
        aplicarIdent(data);
      })
      .catch(function (err) {
        if (err.message === 'no-autorizado') return;
        state.identError = err.message;
      })
      .then(function () {
        state.identLoading = false;
        render();
      });
  }

  function aplicarIdent(data) {
    state.ident = data;
    var negocios = data.negocios || [];
    var actual = state.negocio;
    var sigue = actual && negocios.some(function (n) {
      return n.proyecto === actual.proyecto && n.adj === actual.adj;
    });
    if (!sigue) seleccionarNegocio(negocios.length === 1 ? negocios[0] : null);
  }

  function elegirCliente(cedula) {
    cargarContexto({ cedula: cedula });
  }

  function vincular() {
    var ident = state.ident;
    if (!ident || !ident.cliente) return;
    var ids = chatwootIds();
    if (!ids.account_id || !ids.contact_id) {
      state.aviso = 'No se puede vincular: Chatwoot no envió el contacto.';
      return render();
    }
    state.identLoading = true;
    render();
    api(cfg.apiVincular, { method: 'POST', body: Object.assign(ids, { cedula: ident.cliente.cedula }) })
      .then(function (data) {
        state.aviso = data.chatwoot_sync
          ? 'Contacto vinculado. La cédula quedó guardada en el contacto de Chatwoot.'
          : 'Contacto vinculado en Andinasoft.';
        aplicarIdent(data);
      })
      .catch(function (err) {
        if (err.message !== 'no-autorizado') state.aviso = err.message;
      })
      .then(function () {
        state.identLoading = false;
        render();
      });
  }

  function desvincular() {
    var ids = chatwootIds();
    state.identLoading = true;
    render();
    api(cfg.apiVincular, { method: 'DELETE', body: ids })
      .then(function () {
        state.aviso = 'Vínculo eliminado.';
        state.ident = null;
        seleccionarNegocio(null);
        return cargarContexto({ cedula_atributo: '' });
      })
      .catch(function (err) {
        if (err.message !== 'no-autorizado') state.aviso = err.message;
        state.identLoading = false;
        render();
      });
  }

  function buscar(q) {
    q = (q || '').trim();
    if (q.length < 3) {
      state.busqueda = { q: q, candidatos: [], error: 'Escribe al menos 3 caracteres.' };
      return render();
    }
    state.buscando = true;
    render();
    api(cfg.apiBuscar, { method: 'POST', body: { q: q } })
      .then(function (data) {
        state.busqueda = { q: q, candidatos: data.candidatos || [] };
      })
      .catch(function (err) {
        if (err.message !== 'no-autorizado') state.busqueda = { q: q, candidatos: [], error: err.message };
      })
      .then(function () {
        state.buscando = false;
        render();
      });
  }

  var VIA = {
    vinculo: 'Vinculado',
    atributo: 'Cédula en Chatwoot',
    telefono: 'Identificado por teléfono',
    seleccion: 'Elegido por ti',
  };

  function renderCliente() {
    var root = $('cliente-root');
    var ident = state.ident;
    var nodes = [];

    if (state.aviso) {
      nodes.push(el('div', { class: 'notice' }, [
        el('span', { text: state.aviso }),
        el('button', { type: 'button', class: 'notice__close', 'aria-label': 'Cerrar aviso', onclick: function () {
          state.aviso = '';
          render();
        } }, '×'),
      ]));
    }

    if (state.identLoading && !ident) {
      nodes.push(el('div', { class: 'cliente__row' }, [
        el('div', { class: 'spinner spinner--sm', 'aria-hidden': 'true' }),
        el('span', { class: 'muted', text: 'Buscando al cliente en Andinasoft…' }),
      ]));
      return mount(root, nodes);
    }
    if (state.identError) {
      nodes.push(el('div', { class: 'cliente__row' }, [
        el('span', { class: 'label label--ruby', text: 'Error' }),
        el('span', { class: 'muted', text: state.identError }),
        el('button', { type: 'button', class: 'btn btn--ghost btn--sm', onclick: function () {
          cargarContexto();
        } }, 'Reintentar'),
      ]));
      return mount(root, nodes);
    }
    if (!ident) return mount(root, nodes);

    (ident.avisos || []).forEach(function (texto) {
      nodes.push(el('div', { class: 'banner banner--amber banner--inline', text: texto }));
    });

    if (ident.cliente) {
      var vinculado = ident.via === 'vinculo' || ident.via === 'atributo';
      nodes.push(el('div', { class: 'cliente__row' }, [
        el('div', { class: 'cliente__info' }, [
          nombreCliente(ident.cliente),
          el('div', { class: 'cliente__meta' }, [
            el('span', { text: 'C.C. ' + ident.cliente.cedula_mask }),
            el('span', { class: 'label ' + (vinculado ? 'label--teal' : 'label--amber'), text: VIA[ident.via] || ident.via }),
          ]),
        ]),
        el('div', { class: 'cliente__actions' }, vinculado
          ? [el('button', { type: 'button', class: 'btn btn--ghost btn--sm', disabled: state.identLoading, onclick: desvincular }, 'Desvincular')]
          : [
            el('button', { type: 'button', class: 'btn btn--ghost btn--sm', onclick: function () {
              state.ident = Object.assign({}, state.ident, { cliente: null, estado: 'ninguno', negocios: [] });
              seleccionarNegocio(null);
              render();
            } }, 'No es este cliente'),
            el('button', { type: 'button', class: 'btn btn--solid btn--sm', disabled: state.identLoading, onclick: vincular }, 'Vincular'),
          ]),
      ]));
      nodes.push(renderNegocios(ident));
      return mount(root, nodes);
    }

    if ((ident.candidatos || []).length) {
      nodes.push(el('p', { class: 'cliente__hint', text: 'Varios clientes coinciden. Elige el correcto:' }));
      nodes.push(renderCandidatos(ident.candidatos));
    } else {
      nodes.push(el('p', { class: 'cliente__hint', text: 'No encontramos al cliente por el teléfono. Búscalo por cédula o nombre:' }));
    }
    nodes.push(renderBuscador());
    mount(root, nodes);
  }

  function nombreCliente(cliente) {
    var nombre = cliente.nombre || cliente.cedula;
    if (!state.negocio) return el('div', { class: 'cliente__name', text: nombre });
    var url = cfg.adjUrl + encodeURIComponent(state.negocio.proyecto) + '/' + encodeURIComponent(state.negocio.adj) + '/';
    return el('div', { class: 'cliente__name' }, el('a', {
      class: 'link', href: url, target: '_blank', rel: 'noopener',
      title: 'Abrir la adjudicación ' + state.negocio.adj + ' en Andinasoft',
    }, [el('span', { text: nombre }), el('span', { class: 'link__icon', 'aria-hidden': 'true' }, '↗')]));
  }

  function renderCandidatos(candidatos) {
    return el('ul', { class: 'candidatos' }, candidatos.map(function (c) {
      return el('li', { class: 'candidato' }, [
        el('div', { class: 'candidato__info' }, [
          el('div', { class: 'candidato__name', text: c.nombre || c.cedula_mask }),
          el('div', { class: 'candidato__meta', text: 'C.C. ' + c.cedula_mask + ' · ' + c.negocios + ' negocio' + (c.negocios === 1 ? '' : 's') + ' · ' + (c.proyectos || []).join(', ') }),
          c.motivo ? el('div', { class: 'candidato__meta', text: c.motivo }) : null,
          c.posible ? el('span', { class: 'label label--amber', text: 'Coincidencia posible' }) : null,
        ]),
        el('button', { type: 'button', class: 'btn btn--ghost btn--sm', onclick: function () {
          elegirCliente(c.cedula);
        } }, 'Elegir'),
      ]);
    }));
  }

  function renderBuscador() {
    var input = el('input', {
      class: 'input', type: 'search', name: 'q', placeholder: 'Cédula o nombre del cliente',
      autocomplete: 'off', value: state.busqueda ? state.busqueda.q : '', 'aria-label': 'Buscar cliente',
    });
    var form = el('form', { class: 'buscador', onsubmit: function (event) {
      event.preventDefault();
      buscar(input.value);
    } }, [
      input,
      el('button', { type: 'submit', class: 'btn btn--solid btn--sm', disabled: state.buscando }, state.buscando ? 'Buscando…' : 'Buscar'),
    ]);
    var nodes = [form];
    var b = state.busqueda;
    if (b && b.error) nodes.push(el('p', { class: 'cliente__hint', text: b.error }));
    else if (b && !b.candidatos.length && !state.buscando) {
      nodes.push(el('p', { class: 'cliente__hint', text: 'Sin resultados con negocios para «' + b.q + '».' }));
    } else if (b) nodes.push(renderCandidatos(b.candidatos));
    return el('div', {}, nodes);
  }

  function renderNegocios(ident) {
    var negocios = ident.negocios || [];
    var nodes = [];
    if (!negocios.length) {
      nodes.push(el('p', { class: 'cliente__hint', text: ident.negocios_otros_proyectos
        ? 'El cliente tiene negocios solo en proyectos que no tienes asignados en Andinasoft.'
        : 'El cliente no tiene negocios.' }));
    } else if (negocios.length > 1) {
      nodes.push(el('div', { class: 'chips', role: 'listbox', 'aria-label': 'Negocios del cliente' }, negocios.map(function (n) {
        var activo = state.negocio && state.negocio.proyecto === n.proyecto && state.negocio.adj === n.adj;
        return el('button', {
          type: 'button', class: 'chip' + (activo ? ' is-active' : ''), role: 'option', 'aria-selected': activo ? 'true' : 'false',
          onclick: function () {
            seleccionarNegocio(n);
            render();
          },
        }, [el('span', { class: 'chip__title', text: n.proyecto }), el('span', { class: 'chip__meta', text: n.inmueble + ' · ' + n.adj })]);
      })));
    }
    if (negocios.length && ident.negocios_otros_proyectos) {
      nodes.push(el('p', { class: 'cliente__hint', text: 'Además tiene ' + ident.negocios_otros_proyectos + ' negocio(s) en proyectos que no tienes asignados.' }));
    }
    return el('div', { class: 'negocios' }, nodes);
  }

  // ---------- negocio seleccionado ----------
  function seleccionarNegocio(negocio) {
    var nuevo = negocio ? { proyecto: negocio.proyecto, adj: negocio.adj } : null;
    var mismo = state.negocio && nuevo && state.negocio.proyecto === nuevo.proyecto && state.negocio.adj === nuevo.adj;
    if (mismo) return;
    state.negocio = nuevo;
    state.cartera = null;
    state.carteraError = '';
    state.promesa = null;
    state.promesaError = '';
    state.documentos = null;
    state.documentosError = '';
    liberarVisor();
    state.seg = null;
    state.segError = '';
    state.segMsg = null;
    state.segForm = null;
    if (nuevo) cargarCartera();
  }

  function cargarRecurso(recurso, campo) {
    var negocio = state.negocio;
    if (!negocio || state[campo] || state[campo + 'Loading']) return;
    state[campo + 'Loading'] = true;
    api(negocioUrl(negocio, recurso))
      .then(function (data) {
        if (state.negocio === negocio) state[campo] = data;
      })
      .catch(function (err) {
        if (err.message !== 'no-autorizado' && state.negocio === negocio) state[campo + 'Error'] = err.message;
      })
      .then(function () {
        if (state.negocio === negocio) state[campo + 'Loading'] = false;
        render();
      });
  }

  function cargarCartera() {
    var negocio = state.negocio;
    state.carteraLoading = true;
    api(negocioUrl(negocio, 'cartera'))
      .then(function (data) {
        if (state.negocio === negocio) state.cartera = data;
      })
      .catch(function (err) {
        if (err.message !== 'no-autorizado' && state.negocio === negocio) state.carteraError = err.message;
      })
      .then(function () {
        if (state.negocio === negocio) state.carteraLoading = false;
        render();
      });
  }

  function vacio(titulo, texto) {
    return el('div', { class: 'card' }, el('div', { class: 'card__empty' }, [
      el('h2', { class: 'card__title', text: titulo }),
      texto ? el('p', { class: 'card__text', text: texto }) : null,
    ]));
  }

  function cargando(texto) {
    return el('div', { class: 'card' }, el('div', { class: 'card__loading' }, [
      el('div', { class: 'spinner spinner--sm', 'aria-hidden': 'true' }),
      el('span', { class: 'muted', text: texto }),
    ]));
  }

  function sinNegocio() {
    if (state.identLoading || !state.ident) return cargando('Buscando al cliente…');
    if (!state.ident.cliente) return vacio('Primero identifica al cliente', 'Elige o busca al cliente arriba para ver su cartera.');
    if (!(state.ident.negocios || []).length) return vacio('Sin negocios para mostrar');
    return vacio('Elige un negocio', 'El cliente tiene varios negocios: selecciona uno arriba.');
  }

  function kpi(titulo, valor, detalle, tono) {
    return el('div', { class: 'kpi' + (tono ? ' kpi--' + tono : '') }, [
      el('div', { class: 'kpi__label', text: titulo }),
      el('div', { class: 'kpi__value', text: valor }),
      detalle ? el('div', { class: 'kpi__detail', text: detalle }) : null,
    ]);
  }

  function resumenTexto(c) {
    var lineas = [
      'Estado de cuenta · ' + c.proyecto + ' · ' + c.inmueble + ' (' + c.adj + ')',
      'Fecha de corte: ' + fmtDate(c.fecha_corte),
    ];
    if (Number(c.total_vencido) > 0) {
      lineas.push('Valor vencido: ' + fmtMoney(c.vencido) + ' (' + c.cuotas_vencidas + ' cuota' + (c.cuotas_vencidas === 1 ? '' : 's') + ')');
      lineas.push('Intereses de mora: ' + fmtMoney(c.mora));
      lineas.push('Total vencido a la fecha: ' + fmtMoney(c.total_vencido));
    } else {
      lineas.push('Estás al día en tus pagos.');
    }
    (c.proximas || []).forEach(function (p) {
      lineas.push('Próxima cuota: ' + fmtDate(p.fecha) + ' por ' + fmtMoney(p.valor));
    });
    if (c.ultimo_pago) {
      lineas.push('Último pago: ' + fmtMoney(c.ultimo_pago.valor) + ' el ' + fmtDate(c.ultimo_pago.fecha) + ' (recibo ' + c.ultimo_pago.recibo + ')');
    }
    lineas.push('Saldo de capital: ' + fmtMoney(c.saldo));
    return lineas.join('\n');
  }

  function copiar(texto, boton) {
    var hecho = function () {
      var original = boton.textContent;
      boton.textContent = 'Copiado';
      window.setTimeout(function () {
        boton.textContent = original;
      }, 1500);
    };
    var respaldo = function () {
      var area = el('textarea', { class: 'copy-buffer', readonly: true });
      area.value = texto;
      document.body.appendChild(area);
      area.select();
      var ok = false;
      try {
        ok = document.execCommand('copy');
      } catch (e) {
        ok = false;
      }
      document.body.removeChild(area);
      if (ok) hecho();
      else {
        state.aviso = 'El navegador no dejó copiar. Selecciona el texto del resumen y cópialo a mano.';
        render();
      }
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(texto).then(hecho, respaldo);
    } else {
      respaldo();
    }
  }

  /* El PDF también exige el token, así que se baja con fetch y se guarda desde un blob. */
  function descargarEstadoCuenta(negocio, boton) {
    if (!negocio || boton.disabled) return;
    var original = boton.textContent;
    boton.disabled = true;
    boton.textContent = 'Generando PDF…';
    var headers = { Authorization: 'Bearer ' + state.token };
    if (debug) headers['ngrok-skip-browser-warning'] = '1';
    fetch(negocioUrl(negocio, 'estado-cuenta'), { headers: headers, credentials: 'omit', cache: 'no-store' })
      .then(function (res) {
        if (res.status === 401) {
          saveToken('');
          state.user = null;
          throw new Error('no-autorizado');
        }
        if (!res.ok || (res.headers.get('Content-Type') || '').indexOf('application/pdf') !== 0) {
          return res.json().then(
            function (data) {
              throw new Error(data.detail || 'No se pudo generar el estado de cuenta.');
            },
            function () {
              throw new Error('No se pudo generar el estado de cuenta.');
            }
          );
        }
        var disposicion = res.headers.get('Content-Disposition') || '';
        var match = disposicion.match(/filename="?([^";]+)"?/);
        var nombre = match ? match[1] : 'Estado_de_cuenta_' + negocio.adj + '.pdf';
        return res.blob().then(function (blob) {
          var url = URL.createObjectURL(blob);
          var enlace = el('a', { href: url, download: nombre, class: 'copy-buffer' });
          document.body.appendChild(enlace);
          enlace.click();
          document.body.removeChild(enlace);
          window.setTimeout(function () {
            URL.revokeObjectURL(url);
          }, 30000);
        });
      })
      .catch(function (err) {
        if (err.message !== 'no-autorizado') state.aviso = err.message;
      })
      .then(function () {
        boton.disabled = false;
        boton.textContent = original;
        render();
      });
  }

  function renderCartera() {
    var root = $('cartera-root');
    if (!state.negocio) return mount(root, sinNegocio());
    if (state.carteraError) return mount(root, vacio('No se pudo cargar la cartera', state.carteraError));
    var c = state.cartera;
    if (!c) return mount(root, cargando('Calculando la cartera…'));

    var alDia = Number(c.total_vencido) <= 0;
    var nodes = [];
    nodes.push(el('div', { class: 'negocio' }, [
      el('div', {}, [
        el('div', { class: 'negocio__title', text: c.proyecto + ' · ' + c.inmueble }),
        el('div', { class: 'negocio__meta', text: c.adj + (c.titulares.length ? ' · ' + c.titulares.join(', ') : '') }),
      ]),
      el('div', { class: 'negocio__labels' }, [
        c.estado ? el('span', { class: 'label label--slate', text: c.estado }) : null,
        el('span', { class: 'label ' + (alDia ? 'label--teal' : 'label--ruby'), text: alDia ? 'Al día' : c.dias_mora + ' días de mora' }),
      ]),
    ]));

    nodes.push(el('div', { class: 'kpis' }, [
      kpi('Total vencido', fmtMoney(c.total_vencido),
        alDia ? 'Sin cuotas vencidas' : fmtMoney(c.vencido) + ' en cuotas + ' + fmtMoney(c.mora) + ' de mora', alDia ? 'teal' : 'ruby'),
      kpi('Saldo de capital', fmtMoney(c.saldo), 'Valor ' + fmtMoney(c.valor) + ' · abonado ' + fmtMoney(c.pagado)),
      kpi('Para cancelar hoy', fmtMoney(c.pago_total_hoy), 'Todo el saldo más intereses y mora'),
      c.ultimo_pago
        ? kpi('Último pago', fmtMoney(c.ultimo_pago.valor), fmtDate(c.ultimo_pago.fecha) + ' · recibo ' + c.ultimo_pago.recibo)
        : kpi('Último pago', '—', 'Sin recibos registrados'),
    ]));

    if (c.vencidas.length) {
      nodes.push(el('div', { class: 'card' }, [
        el('div', { class: 'card__header' }, el('h3', { class: 'card__title', text: 'Cuotas vencidas' })),
        tabla(['Cuota', 'Fecha', 'Pendiente', 'Mora', 'Días'], c.vencidas.map(function (q) {
          return [q.cuota, fmtDate(q.fecha), fmtMoney(q.pendiente), fmtMoney(q.mora), String(q.dias)];
        }), [false, false, true, true, true]),
      ]));
    }

    nodes.push(el('div', { class: 'card' }, [
      el('div', { class: 'card__header' }, el('h3', { class: 'card__title', text: 'Próximos 30 días' })),
      c.proximas.length
        ? tabla(['Fecha', 'Valor'], c.proximas.map(function (p) {
          return [fmtDate(p.fecha), fmtMoney(p.valor)];
        }), [false, true])
        : el('p', { class: 'card__body muted', text: 'No hay cuotas por vencer en los próximos 30 días.' }),
    ]));

    var botonCopiar = el('button', { type: 'button', class: 'btn btn--ghost btn--sm', onclick: function () {
      copiar(resumenTexto(c), botonCopiar);
    } }, 'Copiar resumen');
    var botonPdf = el('button', { type: 'button', class: 'btn btn--solid btn--sm', onclick: function () {
      descargarEstadoCuenta(state.negocio, botonPdf);
    } }, 'Descargar estado de cuenta');
    nodes.push(el('div', { class: 'footer-row' }, [
      el('span', { class: 'muted', text: 'Corte ' + fmtDate(c.fecha_corte) + ' · mismas cifras del estado de cuenta' }),
      el('div', { class: 'footer-row__actions' }, [botonCopiar, botonPdf]),
    ]));
    mount(root, nodes);
  }

  function tabla(headers, rows, numeric) {
    return el('div', { class: 'table-wrap' }, el('table', { class: 'table' }, [
      el('thead', {}, el('tr', {}, headers.map(function (h, i) {
        return el('th', { class: numeric[i] ? 'num' : null, scope: 'col', text: h });
      }))),
      el('tbody', {}, rows.map(function (row) {
        var cls = row.className;
        return el('tr', { class: cls || null }, row.map(function (cell, i) {
          return el('td', { class: numeric[i] ? 'num' : null }, cell);
        }));
      })),
    ]));
  }

  // ---------- escrituración y entrega ----------
  var TONO_ESTADO = {
    cumplido: 'teal',
    al_dia: 'teal',
    por_vencer: 'amber',
    vencido: 'ruby',
    sin_fecha: 'slate',
  };

  function hito(titulo, data, textoCumplido) {
    var tono = TONO_ESTADO[data.estado] || 'slate';
    var cumplido = data.estado === 'cumplido';
    var valor = cumplido && data.real ? fmtDate(data.real) : fmtDate(data.pactada);
    var detalle;
    if (cumplido) detalle = textoCumplido + (data.pactada ? ' · pactada ' + fmtDate(data.pactada) : '');
    else detalle = data.pactada ? 'Fecha pactada' : 'Sin fecha pactada en la promesa';
    return el('div', { class: 'kpi' }, [
      el('div', { class: 'hito__head' }, [
        el('span', { class: 'kpi__label', text: titulo }),
        el('span', { class: 'label label--' + tono, text: data.estado_label }),
      ]),
      el('div', { class: 'kpi__value kpi__value--sm', text: valor }),
      el('div', { class: 'kpi__detail', text: detalle }),
    ]);
  }

  function cambio(etiqueta, par) {
    if (!par) return null;
    return el('div', { class: 'otrosi__cambio' }, [
      el('span', { class: 'muted', text: etiqueta }),
      el('span', { text: (par.anterior ? fmtDate(par.anterior) : '—') + ' → ' + (par.nueva ? fmtDate(par.nueva) : '—') }),
    ]);
  }

  function renderPromesa() {
    var root = $('promesa-root');
    if (state.tab !== 'promesa') return;
    if (!state.negocio) return mount(root, sinNegocio());
    if (state.promesaError) return mount(root, vacio('No se pudo cargar la promesa', state.promesaError));
    var p = state.promesa;
    if (!p) {
      cargarRecurso('promesa', 'promesa');
      return mount(root, cargando('Cargando entrega y escrituración…'));
    }
    var esc = p.escritura;
    var nodes = [];

    nodes.push(el('div', { class: 'negocio' }, [
      el('div', {}, [
        el('div', { class: 'negocio__title', text: 'Promesa ' + (p.nropromesa || 'sin número') }),
        el('div', { class: 'negocio__meta', text: p.fecha_promesa ? 'Firmada el ' + fmtDate(p.fecha_promesa) : 'Sin fecha de promesa' }),
      ]),
      el('div', { class: 'negocio__labels' }, [
        p.tiene_promesa ? null : el('span', { class: 'label label--slate', text: 'Sin datos de promesa' }),
        el('a', {
          class: 'link', href: p.ficha_url, target: '_blank', rel: 'noopener',
          title: 'Abrir la ficha del cliente en servicio al cliente (Andinasoft)',
        }, [el('span', { text: 'Ver ficha de servicio al cliente' }), el('span', { class: 'link__icon', 'aria-hidden': 'true' }, '↗')]),
      ]),
    ]));

    nodes.push(el('div', { class: 'kpis' }, [
      hito('Entrega', p.entrega, 'Entregado'),
      hito('Escritura', esc, 'Escriturado'),
    ]));

    var pasos = el('ol', { class: 'pasos' }, esc.pasos.map(function (paso) {
      var fecha = paso.hecho ? (paso.fecha ? fmtDate(paso.fecha) : 'Hecho') : 'Pendiente';
      return el('li', { class: 'paso' + (paso.hecho ? ' is-done' : '') }, [
        el('span', { class: 'paso__dot', 'aria-hidden': 'true' }, paso.hecho ? '✓' : ''),
        el('span', { class: 'paso__label', text: paso.label }),
        el('span', { class: 'paso__fecha', text: fecha }),
      ]);
    }));
    var estadoTramite = esc.completa ? 'Completo' : (esc.siguiente_label ? 'Sigue: ' + esc.siguiente_label : '');
    nodes.push(el('div', { class: 'card' }, [
      el('div', { class: 'card__header card__header--row' }, [
        el('h3', { class: 'card__title', text: 'Trámite de escritura' }),
        el('span', { class: 'muted', text: estadoTramite }),
      ]),
      esc.alerta_firma_empresa ? el('div', {
        class: 'banner banner--amber banner--card',
        text: 'El cliente firmó hace ' + esc.dias_firma_cliente + ' días y falta la firma de la empresa.',
      }) : null,
      pasos,
    ]));

    nodes.push(el('div', { class: 'card' }, [
      el('div', { class: 'card__header' }, el('h3', { class: 'card__title', text: 'Otrosíes y prórrogas' })),
      p.otrosi.length
        ? el('ul', { class: 'timeline' }, p.otrosi.map(function (o) {
          return el('li', { class: 'timeline__item' }, [
            el('div', { class: 'timeline__meta' }, [
              el('span', { class: 'timeline__date', text: fmtDate(o.fecha) }),
              el('span', { class: 'label label--blue', text: o.tipo }),
            ]),
            cambio('Promesa', o.promesa),
            cambio('Entrega', o.entrega),
            cambio('Escritura', o.escritura),
            o.observaciones ? el('p', { class: 'timeline__text muted', text: o.observaciones }) : null,
          ]);
        }))
        : el('p', { class: 'card__body muted', text: 'Sin otrosíes: aplican las fechas de la promesa.' }),
    ]));

    if (p.observaciones) {
      nodes.push(el('div', { class: 'card' }, [
        el('div', { class: 'card__header' }, el('h3', { class: 'card__title', text: 'Observaciones' })),
        el('p', { class: 'card__body', text: p.observaciones }),
      ]));
    }
    mount(root, nodes);
  }

  // ---------- documentos ----------
  function liberarVisor() {
    if (state.docUrl) URL.revokeObjectURL(state.docUrl);
    state.docUrl = '';
    state.docActivo = null;
    state.docError = '';
    state.visor = null;
  }

  function abrirDocumento(doc) {
    var negocio = state.negocio;
    liberarVisor();
    state.docActivo = doc;
    state.docLoading = true;
    render();
    var headers = { Authorization: 'Bearer ' + state.token };
    if (debug) headers['ngrok-skip-browser-warning'] = '1';
    fetch(negocioUrl(negocio, 'documentos') + doc.id + '/', { headers: headers, credentials: 'omit', cache: 'no-store' })
      .then(function (res) {
        if (res.status === 401) {
          saveToken('');
          state.user = null;
          throw new Error('no-autorizado');
        }
        if (!res.ok) {
          return res.json().then(
            function (data) {
              throw new Error(data.detail || 'No se pudo abrir el documento.');
            },
            function () {
              throw new Error('No se pudo abrir el documento.');
            }
          );
        }
        return res.blob();
      })
      .then(function (blob) {
        if (state.negocio !== negocio || state.docActivo !== doc) return;
        state.docUrl = URL.createObjectURL(new Blob([blob], { type: 'application/pdf' }));
      })
      .catch(function (err) {
        if (err.message !== 'no-autorizado' && state.docActivo === doc) state.docError = err.message;
      })
      .then(function () {
        if (state.docActivo === doc) state.docLoading = false;
        render();
      });
  }

  function renderVisor() {
    var doc = state.docActivo;
    if (!doc) return null;
    var cabecera = el('div', { class: 'card__header card__header--row' }, [
      el('h3', { class: 'card__title', text: doc.nombre }),
      el('div', { class: 'footer-row__actions' }, [
        state.docUrl ? el('a', { class: 'btn btn--ghost btn--sm', href: state.docUrl, download: doc.nombre + '.pdf' }, 'Descargar') : null,
        el('button', { type: 'button', class: 'btn btn--ghost btn--sm', onclick: function () {
          liberarVisor();
          render();
        } }, 'Cerrar'),
      ]),
    ]);
    var cuerpo;
    if (state.docError) cuerpo = el('p', { class: 'card__body muted', text: state.docError });
    else if (!state.docUrl) cuerpo = el('div', { class: 'card__loading' }, [
      el('div', { class: 'spinner spinner--sm', 'aria-hidden': 'true' }),
      el('span', { class: 'muted', text: 'Abriendo documento…' }),
    ]);
    else {
      // El iframe se conserva entre renders para no recargar el PDF.
      if (!state.visor || state.visor.dataset.src !== state.docUrl) {
        state.visor = el('iframe', { class: 'visor', src: state.docUrl, title: doc.nombre });
        state.visor.dataset.src = state.docUrl;
      }
      cuerpo = state.visor;
    }
    return el('div', { class: 'card' }, [cabecera, cuerpo]);
  }

  function renderDocumentos() {
    var root = $('documentos-root');
    if (state.tab !== 'documentos') return;
    if (!state.negocio) return mount(root, sinNegocio());
    if (state.documentosError) return mount(root, vacio('Documentos no disponibles', state.documentosError));
    var data = state.documentos;
    if (!data) {
      cargarRecurso('documentos', 'documentos');
      return mount(root, cargando('Cargando documentos…'));
    }
    var docs = data.documentos || [];
    var lista = docs.length
      ? el('ul', { class: 'docs' }, docs.map(function (d) {
        var activo = state.docActivo && state.docActivo.id === d.id;
        return el('li', {}, el('button', {
          type: 'button', class: 'doc' + (activo ? ' is-active' : ''), 'aria-pressed': activo ? 'true' : 'false',
          onclick: function () {
            abrirDocumento(d);
          },
        }, [
          el('span', { class: 'doc__icon', 'aria-hidden': 'true' }, 'PDF'),
          el('span', { class: 'doc__info' }, [
            el('span', { class: 'doc__name', text: d.nombre }),
            el('span', { class: 'doc__meta', text: [d.fecha, d.usuario].filter(Boolean).join(' · ') }),
          ]),
        ]));
      }))
      : el('p', { class: 'card__body muted', text: 'El negocio no tiene documentos cargados.' });
    mount(root, [
      el('div', { class: 'card' }, [
        el('div', { class: 'card__header' }, el('h3', { class: 'card__title', text: 'Documentos del contrato' })),
        lista,
      ]),
      renderVisor(),
    ]);
  }

  // ---------- seguimiento ----------
  function nuevaLlave() {
    if (window.crypto && window.crypto.randomUUID) return window.crypto.randomUUID();
    return 'k' + Date.now().toString(36) + Math.random().toString(36).slice(2, 12);
  }

  function hoyIso() {
    var d = new Date();
    return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
  }

  function construirFormulario(seg) {
    var opciones = function (valores, elegido) {
      return valores.map(function (v) {
        return el('option', { value: v, selected: v === elegido }, v);
      });
    };
    var tipo = el('select', { class: 'input', name: 'tipo', id: 'seg-tipo' }, opciones(seg.tipos, seg.tipos.indexOf('Cobro') >= 0 ? 'Cobro' : seg.tipos[0]));
    var forma = el('select', { class: 'input', name: 'forma', id: 'seg-forma' }, opciones(seg.formas, seg.forma_por_defecto));
    var comentario = el('textarea', {
      class: 'input input--area', name: 'comentario', id: 'seg-comentario', rows: '3', maxlength: '500',
      placeholder: '¿Qué respondió el cliente?',
    });
    var contador = el('span', { class: 'field__hint', text: '0 / 500' });
    comentario.addEventListener('input', function () {
      contador.textContent = comentario.value.length + ' / 500';
    });
    var compromiso = el('input', { type: 'checkbox', name: 'compromiso', id: 'seg-compromiso' });
    var fecha = el('input', { class: 'input', type: 'date', name: 'fecha_compromiso', id: 'seg-fecha', min: hoyIso() });
    var valor = el('input', {
      class: 'input', type: 'text', name: 'valor_compromiso', id: 'seg-valor', inputmode: 'numeric',
      autocomplete: 'off', placeholder: '$ 0',
    });
    valor.addEventListener('input', function () {
      var digitos = valor.value.replace(/\D/g, '');
      valor.value = digitos ? fmtMoney(digitos) : '';
    });
    var camposCompromiso = el('div', { class: 'form__row', hidden: true }, [
      el('label', { class: 'field' }, [el('span', { class: 'field__label', text: 'Fecha del compromiso' }), fecha]),
      el('label', { class: 'field' }, [el('span', { class: 'field__label', text: 'Valor' }), valor]),
    ]);
    compromiso.addEventListener('change', function () {
      camposCompromiso.hidden = !compromiso.checked;
    });
    var guardar = el('button', { type: 'submit', class: 'btn btn--solid' }, 'Guardar seguimiento');
    var mensaje = el('p', { class: 'form__msg', role: 'status', hidden: true });

    var form = el('form', { class: 'card form', novalidate: true }, [
      el('div', { class: 'card__header' }, el('h3', { class: 'card__title', text: 'Registrar seguimiento' })),
      el('div', { class: 'form__body' }, [
        el('div', { class: 'form__row' }, [
          el('label', { class: 'field' }, [el('span', { class: 'field__label', text: 'Tipo' }), tipo]),
          el('label', { class: 'field' }, [el('span', { class: 'field__label', text: 'Forma de contacto' }), forma]),
        ]),
        el('label', { class: 'field' }, [
          el('span', { class: 'field__label', text: 'Respuesta del cliente' }), comentario, contador,
        ]),
        el('label', { class: 'check' }, [compromiso, el('span', { text: 'Hay compromiso de pago' })]),
        camposCompromiso,
        el('div', { class: 'form__actions' }, [mensaje, guardar]),
      ]),
    ]);
    form.dataset.key = nuevaLlave();

    form.addEventListener('submit', function (event) {
      event.preventDefault();
      if (state.segSaving) return;
      var negocio = state.negocio;
      var ids = chatwootIds();
      var body = {
        tipo: tipo.value,
        forma: forma.value,
        comentario: comentario.value,
        compromiso: compromiso.checked,
        fecha_compromiso: compromiso.checked ? fecha.value : '',
        valor_compromiso: compromiso.checked ? valor.value.replace(/\D/g, '') : '',
        idempotency_key: form.dataset.key,
        account_id: ids.account_id,
        conversation_id: ids.conversation_id,
      };
      state.segSaving = true;
      guardar.disabled = true;
      guardar.textContent = 'Guardando…';
      mensaje.hidden = true;
      api(negocioUrl(negocio, 'seguimientos'), { method: 'POST', body: body })
        .then(function (data) {
          if (state.negocio !== negocio) return;
          state.seg = Object.assign({}, state.seg, { seguimientos: data.seguimientos });
          form.reset();
          contador.textContent = '0 / 500';
          camposCompromiso.hidden = true;
          tipo.value = seg.tipos.indexOf('Cobro') >= 0 ? 'Cobro' : seg.tipos[0];
          forma.value = seg.forma_por_defecto;
          form.dataset.key = nuevaLlave();
          mensaje.className = 'form__msg form__msg--ok';
          mensaje.textContent = (data.creado ? 'Seguimiento guardado' : 'Ese seguimiento ya estaba guardado') +
            (data.nota_privada ? ' y anotado en la conversación.' : '.');
          mensaje.hidden = false;
        })
        .catch(function (err) {
          if (err.message === 'no-autorizado') return;
          // Se conserva la llave: reintentar no duplica el seguimiento.
          mensaje.className = 'form__msg form__msg--error';
          mensaje.textContent = err.message;
          mensaje.hidden = false;
        })
        .then(function () {
          state.segSaving = false;
          guardar.disabled = false;
          guardar.textContent = 'Guardar seguimiento';
          renderHistorial();
        });
    });
    return form;
  }

  function renderHistorial() {
    var root = $('seguimiento-historial');
    if (!root || !state.seg) return;
    var lista = state.seg.seguimientos || [];
    mount(root, [
      el('div', { class: 'card__header' }, el('h3', { class: 'card__title', text: 'Historial' })),
      lista.length
        ? el('ul', { class: 'timeline' }, lista.map(function (s) {
          return el('li', { class: 'timeline__item' }, [
            el('div', { class: 'timeline__meta' }, [
              el('span', { class: 'timeline__date', text: fmtDate(s.fecha) }),
              el('span', { text: s.tipo + ' · ' + s.forma }),
              el('span', { class: 'muted', text: s.usuario }),
              s.desde_chatwoot ? el('span', { class: 'label label--blue', text: 'Desde Chatwoot' }) : null,
            ]),
            el('p', { class: 'timeline__text', text: s.comentario }),
            s.valor_compromiso ? el('span', {
              class: 'label label--amber',
              text: 'Compromiso ' + fmtMoney(s.valor_compromiso) + (s.fecha_compromiso ? ' · ' + fmtDate(s.fecha_compromiso) : ''),
            }) : null,
          ]);
        }))
        : el('p', { class: 'card__body muted', text: 'Todavía no hay seguimientos para este negocio.' }),
    ]);
  }

  function renderSeguimiento() {
    var root = $('seguimiento-root');
    if (state.tab !== 'seguimiento') return;
    if (!state.negocio) {
      state.segForm = null;
      return mount(root, sinNegocio());
    }
    if (state.segError) return mount(root, vacio('Seguimientos no disponibles', state.segError));
    if (!state.seg) {
      cargarRecurso('seguimientos', 'seg');
      return mount(root, cargando('Cargando seguimientos…'));
    }
    if (!state.segForm) {
      state.segForm = construirFormulario(state.seg);
      mount(root, [state.segForm, el('div', { class: 'card', id: 'seguimiento-historial' })]);
    } else if (!root.contains(state.segForm)) {
      mount(root, [state.segForm, el('div', { class: 'card', id: 'seguimiento-historial' })]);
    }
    renderHistorial();
  }

  // ---------- pestañas ----------
  function renderTabs() {
    document.querySelectorAll('.tabs__item').forEach(function (tab) {
      var active = tab.dataset.tab === state.tab;
      tab.classList.toggle('is-active', active);
      tab.setAttribute('aria-selected', active ? 'true' : 'false');
    });
    document.querySelectorAll('.tabpanel').forEach(function (panel) {
      panel.hidden = panel.dataset.panel !== state.tab;
    });
  }

  function selectTab(name) {
    state.tab = name;
    render();
  }

  // ---------- sesión ----------
  function setLoadingError(message) {
    $('cargando-spinner').hidden = !!message;
    $('cargando-texto').textContent = message || 'Cargando…';
    $('btn-reintentar').hidden = !message;
  }

  function loadUser() {
    setLoadingError('');
    if (!state.token) return render();
    render();
    api(cfg.apiYo)
      .then(function (user) {
        state.user = user;
        state.contextKey = '';
        onContextChange();
        render();
      })
      .catch(function (err) {
        if (err.message !== 'no-autorizado') {
          setLoadingError('No se pudo conectar con Andinasoft.');
        }
        render();
      });
  }

  function connect() {
    var aviso = $('conectar-aviso');
    aviso.hidden = true;
    var popup = window.open(cfg.conectarUrl, 'andinasoft-conectar', 'width=480,height=640');
    if (!popup) {
      aviso.textContent = 'El navegador bloqueó la ventana. Permite ventanas emergentes para este sitio e intenta de nuevo.';
      aviso.hidden = false;
    }
  }

  function disconnect() {
    var done = function () {
      saveToken('');
      state.user = null;
      state.ident = null;
      seleccionarNegocio(null);
      render();
    };
    api(cfg.apiDesconectar, { method: 'POST' }).then(done, done);
  }

  /* Pide la identificación cuando cambia el contacto (no en cada reenvío del contexto). */
  function onContextChange() {
    if (!state.user || !state.context) return;
    var contact = chatwootContact();
    var attrs = contact.custom_attributes || {};
    var key = [chatwootIds().contact_id, contact.phone_number || '', attrs[ATRIBUTO_CEDULA] || ''].join('|');
    if (key === state.contextKey) return;
    state.contextKey = key;
    state.aviso = '';
    state.ident = null;
    seleccionarNegocio(null);
    cargarContexto();
  }

  // ---------- mensajes ----------
  function onMessage(event) {
    // Token entregado por /chatwoot/conectar/ (mismo origen que este panel).
    if (event.origin === window.location.origin && event.data && event.data.type === TOKEN_MESSAGE) {
      if (typeof event.data.token === 'string' && event.data.token) {
        saveToken(event.data.token);
        state.user = null;
        loadUser();
      }
      return;
    }

    // Contexto de Chatwoot: solo del origen configurado.
    if (!chatwootOrigin || event.origin !== chatwootOrigin) return;
    var payload = event.data;
    if (typeof payload === 'string') {
      try {
        payload = JSON.parse(payload);
      } catch (e) {
        return;
      }
    }
    if (!payload || payload.event !== 'appContext' || !payload.data) return;
    state.context = payload.data;
    if (payload.data.theme) applyTheme(payload.data.theme);
    onContextChange();
    render();
  }

  function applyTheme(theme) {
    var root = document.documentElement;
    root.classList.toggle('dark', theme === 'dark');
    root.classList.toggle('light', theme === 'light');
  }

  function requestContext() {
    if (embedded && chatwootOrigin) {
      window.parent.postMessage(FETCH_INFO, chatwootOrigin);
    }
  }

  // ---------- inicio ----------
  window.addEventListener('message', onMessage);
  $('btn-conectar').addEventListener('click', connect);
  $('btn-desconectar').addEventListener('click', disconnect);
  $('btn-reintentar').addEventListener('click', loadUser);
  document.querySelectorAll('.tabs__item').forEach(function (tab) {
    tab.addEventListener('click', function () {
      selectTab(tab.dataset.tab);
    });
  });
  // Otra pestaña del navegador conectó o desconectó el panel.
  window.addEventListener('storage', function (event) {
    if (event.key !== TOKEN_KEY) return;
    state.token = event.newValue || '';
    state.user = null;
    loadUser();
  });

  loadUser();
  requestContext();
})();
