# Plan de integración: Andinasoft + Chatwoot Dashboard App (v2)

**Estado:** Propuesta revisada contra el código de Andinasoft y el código fuente de Chatwoot (`develop`, 2026-10-08).
**Objetivo:** que los agentes consulten cartera y registren seguimientos de Andinasoft desde la conversación de Chatwoot, sin duplicar lógica financiera.

> Verificar la versión de Chatwoot instalada: lo de abajo sale de `develop`. Archivos de referencia en Chatwoot:
> `app/javascript/dashboard/components/widgets/DashboardApp/Frame.vue`,
> `app/javascript/dashboard/components/widgets/conversation/ConversationBox.vue`,
> `app/models/dashboard_app.rb`, `app/policies/dashboard_app_policy.rb`.

## 1. Qué es (y qué no es) un Dashboard App de Chatwoot

### Lo que sí da
- **Una pestaña** con el título de la app junto a la pestaña "Mensajes" de la conversación. Al abrirla, carga la URL configurada en un `iframe`.
- **Contexto por `postMessage`** (`{event: 'appContext', data}` serializado como JSON) con:
  - `conversation`: la conversación completa (id, `account_id`, `inbox_id`, estado, etiquetas, `custom_attributes`, `meta.sender`, `meta.assignee`, `meta.channel`, mensajes cargados).
  - `contact`: id, nombre, email, `phone_number`, `identifier`, `custom_attributes`, `additional_attributes`.
  - `currentAgent`: `id`, `name`, `email`.
  - `customAttributes` (definiciones de atributos de la cuenta) y `theme` (`light`/`dark`).
- **Envíos del contexto:** al cargar el iframe, al volver a mostrar la pestaña, al cambiar las definiciones de atributos o el tema, y a pedido con `window.parent.postMessage('chatwoot-dashboard-app:fetch-info', ...)` (solo si la pestaña está visible).
- **Cambio de conversación:** Chatwoot vuelve a la pestaña "Mensajes" y el iframe tiene `key = conversación + app`, así que **se desmonta y se vuelve a cargar desde cero** al abrirlo en otra conversación. No hay riesgo de datos "pegados" de la conversación anterior por parte de Chatwoot.
- El iframe **no tiene `sandbox`**: puede abrir ventanas emergentes (útil para iniciar sesión), descargar archivos y navegar.

### Lo que no da (límites duros)
| Límite | Consecuencia para el plan |
|---|---|
| No es un panel lateral: **la pestaña reemplaza la vista de mensajes**. El agente no ve el chat y el panel a la vez. | Diseñar para el ancho completo de la conversación, no para una columna estrecha. El "Copiar resumen" implica ir y volver entre pestañas. |
| El iframe **no puede escribir en el chat**: Chatwoot solo escucha `fetch-info`. No hay forma de insertar texto en la caja de respuesta, enviar mensajes, poner etiquetas ni actualizar el contacto desde el panel. | Toda escritura en Chatwoot va por **backend de Andinasoft → API REST de Chatwoot** con un token guardado en el servidor. |
| El contexto se envía con destino `'*'` y **sin firma**. Cualquier página que abra el iframe puede falsificarlo. | El contexto sirve para saber *qué mostrar*, nunca para autorizar. La autorización es la sesión de Andinasoft. `currentAgent.email` solo sirve para advertir si no coincide con el usuario en sesión. |
| La URL es **fija** (sin variables por conversación o agente). | Todo el contexto llega por `postMessage`; la URL es una sola página. |
| **Todos los agentes de la cuenta ven todas las apps** (`index?`/`show?` = `true`); solo los administradores las crean o editan. No se puede limitar por bandeja ni equipo. | El control de quién ve cartera lo hace Andinasoft (permisos y proyectos del usuario). Un agente sin usuario en Andinasoft ve la pantalla de login o "sin autorización". |
| Solo existe en la vista de conversación (no en la ficha de contacto ni en reportes). | El vínculo contacto ↔ cliente se gestiona desde una conversación. |
| Sin `allow="clipboard-write"` en el iframe. | `navigator.clipboard.writeText` puede fallar en un iframe de otro origen. Usar respaldo con `document.execCommand('copy')` (con clic del usuario) y, si falla, mostrar el texto seleccionado. |
| Cada vez que se abre en una conversación nueva se recarga la página completa. | El panel debe ser liviano: HTML pequeño y datos en llamadas JSON separadas y rápidas. |

### Lo que se puede hacer *con la API de Chatwoot* (desde el backend)
- Guardar la cédula del cliente en un **atributo personalizado del contacto** (p. ej. `cedula_andinasoft`). A partir de ahí llega sola en `contact.custom_attributes` en cada conversación de ese contacto → identificación sin depender del teléfono.
- Crear **notas privadas** en la conversación (p. ej. "Seguimiento registrado en Andinasoft: compromiso $X para el 15/10") para que quede rastro visible en Chatwoot.
- Poner **etiquetas** (`cartera-mora`, `compromiso-pago`).
- (Fase 2) Enviar el PDF del estado de cuenta como mensaje, con confirmación explícita del agente.

## 2. Arquitectura

```text
Chatwoot (pestaña "Cartera" = Dashboard App, iframe)
    | postMessage: conversation, contact, currentAgent  (no confiable)
    v
Andinasoft /chatwoot/panel/   (plantilla Django + JS liviano)
    | fetch() con Authorization: Bearer <token corto> (sin cookies)
    v
Vistas JSON (sin DRF, igual que client_portal): chatwoot_panel_auth + check_project + check_perms
    |-- resolución de cliente: atributo cedula → vínculo guardado → teléfono
    |-- negocios: list_business_cards (recorre proyectos activos)
    |-- saldos: build_estado_cuenta_context (fuente única)
    |-- seguimientos: tabla `seguimientos` de cada proyecto
    |-- escritura en Chatwoot (nota privada, atributo, etiqueta) vía API REST
    v
BD default (clientes, vínculos, auditoría) + BD por proyecto (adjudicación, plan_pagos, recaudos, seguimientos)
```

## 3. Seguridad con dominios distintos (decidido)

Chatwoot y Andinasoft **no comparten dominio** (decisión fija). Dentro del iframe, Andinasoft es un sitio de terceros: la cookie de sesión no viaja (`SameSite=Lax`), y Safari/Firefox/incógnito bloquean o aíslan cookies de terceros. Por eso **el panel no usa cookies**: usa un token corto en un header.

### Principio
La frontera de seguridad es **el usuario de Andinasoft y sus permisos**, no Chatwoot. El contexto de Chatwoot (teléfono, conversación) solo dice *qué buscar*; si alguien lo falsifica, solo puede ver lo que su propio usuario de Andinasoft ya puede ver en Andinasoft.

### Flujo de acceso
1. Chatwoot carga `/chatwoot/panel/` (HTML estático, sin datos sensibles).
2. Si el panel no tiene token → botón **"Conectar con Andinasoft"** → `window.open('/chatwoot/conectar/')`. Esa ventana es de primer nivel: el login normal de Andinasoft funciona con su cookie de siempre.
3. Con sesión iniciada, `/chatwoot/conectar/` (requiere clic de confirmación "Autorizar panel de Chatwoot") emite un **token firmado de corta duración** y lo entrega con `window.opener.postMessage({token}, ORIGEN_ANDINASOFT)` y se cierra.
4. El panel valida `event.origin === ORIGEN_ANDINASOFT`, guarda el token en `localStorage` (sobrevive a cambios de conversación, recargas y cierre del navegador hasta que vence) y lo envía en `Authorization: Bearer <token>` en cada llamada.
5. Token vencido o revocado → el API responde 401 → el panel vuelve al paso 2.

### Token
- Modelo nuevo `ChatwootPanelToken` (BD `default`): `user`, `jti` (aleatorio, único), `created_at`, `expires_at` (**vence tras 5 días sin uso**: cada llamada válida lo corre a ahora + 5 días; para no escribir en cada request, se actualiza como máximo una vez por hora), `revoked_at`, `last_used_at`, `ip`, `user_agent`. En la cookie no hay nada; en el navegador solo queda la cadena firmada.
- Cadena firmada con `django.core.signing` (`jti` + `user_id`); el servidor valida firma **y** que el registro exista, no esté vencido ni revocado, y que el usuario siga activo.
- **Alcance limitado**: solo sirve para las rutas `/chatwoot/api/...` (decorador propio, no el `api_token_auth` general, cuyos tokens son de larga duración).
- El token vence tras 5 días sin uso, sobrevive al cierre del navegador: en equipos compartidos el agente debe pulsar "Desconectar". El panel muestra siempre "Conectado como <usuario>". La cadena del token no cambia al renovarse (el vencimiento vive en el servidor), así que el panel no tiene que reemplazarla.
- Revocación: botón "Desconectar" en el panel y lista de sesiones activas en el admin. Al desactivar un usuario, sus tokens dejan de funcionar.
- Como no hay cookies, **no hay CSRF** en estas rutas (`@csrf_exempt` solo en ellas, que únicamente aceptan Bearer).

### Controles adicionales
- `/chatwoot/panel/` con `@xframe_options_exempt` y `Content-Security-Policy: frame-ancestors <ORIGEN_CHATWOOT>`; el resto de Andinasoft sigue con `X-Frame-Options: DENY`. `/chatwoot/conectar/` **no** se puede embeber (evita clickjacking del botón "Autorizar").
- CSP estricta en el panel (`script-src 'self'`, sin scripts en línea) para que un XSS no pueda robar el token.
- El panel acepta mensajes solo de `ORIGEN_CHATWOOT` y envía `fetch-info` solo a ese origen.
- Cada endpoint aplica `check_project(proyecto)` y el permiso de cartera del usuario. Superusuario no es requisito.
- **Verificación cruzada con la API de Chatwoot** al vincular un contacto o registrar un seguimiento: el backend consulta `GET /api/v1/accounts/{id}/conversations/{conversation_id}` con su propio token y confirma que el contacto/teléfono corresponde. Así el registro queda atado a una conversación real, no a lo que diga el navegador.
- Aviso visible si `currentAgent.email` de Chatwoot no coincide con el email del usuario de Andinasoft (alguien usando la sesión de otro).
- Auditoría: tabla `ChatwootPanelAudit` (usuario, acción, proyecto, adj, contacto, conversación, ip, fecha) para consultas de cartera, vínculos y seguimientos.
- Límite de consultas por usuario (p. ej. 120/min) para frenar extracción masiva.
- Respuestas mínimas: sin cédulas completas de cotitulares ni datos que no se muestran.
- Andinasoft es Django 3.2 y nginx no envía `Cross-Origin-Opener-Policy`, así que `window.opener` funciona. Si en el futuro se agrega COOP, excluir `/chatwoot/conectar/`.

### Configuración (entorno)
`CHATWOOT_ORIGIN`, `CHATWOOT_API_URL`, `CHATWOOT_API_TOKEN` (solo servidor), `CHATWOOT_ACCOUNT_ID`, `CHATWOOT_PANEL_TOKEN_IDLE_DAYS` (default 5).

## 4. Identificación del cliente

Orden de resolución:
1. `contact.custom_attributes.cedula_andinasoft` → `clientes.idTercero`.
2. Vínculo guardado `ChatwootContactLink(account_id, contact_id)` en `default`.
3. Teléfono (ver §4.1).
4. Búsqueda manual por cédula o nombre (reutilizar `_find_clientes_por_nombre` del MCP).

### 4.1 Búsqueda por teléfono (formato libre)

Los teléfonos en `clientes` son texto libre (`3505810975`, `350 581 09 75`, `350-581-0975`, `+57 350 5810975`, `573505810975`, `(350) 581.09.75`, o dos números en el mismo campo). Chatwoot envía `+573505810975`. Todos deben encontrar al mismo cliente.

**Llave de búsqueda** (función `telefono_llave(valor)` en Python, con pruebas):
1. Quitar todo lo que no sea dígito.
2. Quitar prefijo internacional colombiano: `0057…` → sin `0057`; `57` + 10 dígitos → sin `57`.
3. Si quedan **10 dígitos** → esa es la llave (celulares y fijos nuevos `60X` en Colombia).
4. Si el número de Chatwoot trae **otro indicativo** (no `+57`) → la llave son todos los dígitos (p. ej. `13055551234`); no se recorta a 10 para no confundir `+1 305…` con un celular colombiano `305…`.
5. Menos de 10 dígitos (fijos viejos de 7) → no se busca automáticamente; queda la búsqueda manual.

**Consulta** (MariaDB 10.6 tiene `REGEXP_REPLACE`): se limpia cada columna a solo dígitos y se busca la llave *contenida*, lo que cubre el prefijo `57` guardado y los campos con dos números:

```sql
WHERE REGEXP_REPLACE(celular1, '[^0-9]', '') LIKE '%3505810975%'
   OR REGEXP_REPLACE(celular2, '[^0-9]', '') LIKE '%3505810975%'
   OR REGEXP_REPLACE(telefono1,'[^0-9]', '') LIKE '%3505810975%'
   OR REGEXP_REPLACE(telefono2,'[^0-9]', '') LIKE '%3505810975%'
```
(en Django con `Func(..., function='REGEXP_REPLACE')` + `__contains`; la llave va como parámetro, nunca concatenada).

- `celular_cony` se busca aparte y el resultado se marca "coincide con el cónyuge de…", nunca como titular.
- Es un recorrido completo de `clientes` (~4.800 filas); toma milisegundos. Si crece mucho, se agrega una tabla índice `ClienteTelefono(llave, cliente)` reconstruida por cron.
- **Un solo cliente encontrado** → se muestra con la etiqueta "Identificado por teléfono" y el botón "Vincular". **Varios** → lista para elegir. **Ninguno** → buscador manual.

### 4.2 Lo que muestran los datos reales (BD local, 2026-10-08)

Análisis agregado de `clientes` (4.762 registros; sin extraer datos personales). **Confirmar contra producción** si la BD local no es una copia reciente.

| Hallazgo | Cifra | Decisión |
|---|---|---|
| `celular1` con 10 dígitos limpios | 4.131 de 4.360 (95%) | Caso principal; la llave de 10 dígitos funciona. |
| Celulares con espacios, guiones, paréntesis, `+57` | ~60 | Cubiertos por "solo dígitos". |
| Texto pegado al número: `3001234567 ELLA`, `… WHATSAPP`, `… HIJO MARIO …` | ~25 | Cubiertos por "solo dígitos" + "contenido". |
| Textos sin número: `NO TIENE`, `None`, `NULL`, `N/A`, `------` | ~1.000 (sobre todo `celular2`/`telefono2`) | Se ignoran (sin dígitos). |
| Basura: `0`, `0000000000`, `3332333` | ~15 | Ignorar llaves con ≤ 2 dígitos distintos. |
| `telefono1` casi siempre fijo viejo de 7 dígitos | 2.184 | No se busca por ellos. |
| Extranjeros (`+1`, `+34`, `+56`…) | ~150, a veces **sin** `+` (`1305…`, `346…`) o **sin indicativo** (10 dígitos que no empiezan por 3) | Usar la librería **`phonenumbers`** para separar indicativo y número nacional del dato de Chatwoot (ver regla abajo). |
| Celulares de 9 dígitos (falta un dígito) | 30 | No se pueden encontrar; búsqueda manual. Reportarlos para corrección. |
| Clientes sin ningún número utilizable | 135 | Búsqueda manual. |
| Clientes con el teléfono de un asesor | 23 | Excluir llaves que pertenezcan a `asesores` (aviso "es el número de un asesor"). |
| `idTercero` con prefijo `ALT-` | 1.242 | La cédula del atributo de Chatwoot debe guardar el `idTercero` tal cual (con `ALT-`), no solo dígitos. |
| Solo 2.192 de 4.762 clientes son titulares de algún negocio | 46% | **Buscar solo entre titulares con negocio** (los demás no tienen cartera). |

**Números compartidos entre clientes (lo más importante):** 627 llaves de 10 dígitos aparecen en 2–3 clientes distintos.

| Tipo | Llaves | Efecto |
|---|---|---|
| Cotitulares del mismo negocio (pareja, familia) | 240 | Inofensivo: se muestran ambos titulares y el mismo negocio una sola vez. |
| Ninguno tiene negocio | 272 | Desaparecen al filtrar por titulares. |
| Solo uno tiene negocio | 105 | Queda uno solo tras filtrar → identificación directa. |
| Dos o más con negocios distintos y no son cotitulares | **10** | Ambigüedad real → lista para que el agente elija. |

Conclusión: con el filtro de titulares, el teléfono identifica a un cliente (o a un grupo de cotitulares) en casi todos los casos; quedan ~10 números ambiguos.

**Regla ajustada para números extranjeros** (sin dependencia nueva: se prueba el número nacional quitando un indicativo de 1, 2 o 3 dígitos):
- `+57` → llave de 10 dígitos, búsqueda "contenida" (como arriba).
- Otro indicativo → buscar (a) todos los dígitos "contenidos" (`13055551234`, `34612345678`) **o** (b) el número nacional (`3055551234`, `612345678`) **igual exacto** al valor limpio en BD, y solo si ese valor no empieza por `3` con 10 dígitos (para no chocar con celulares colombianos). Toda coincidencia por la regla (b) se marca "posible" y exige confirmación.

**Casos de prueba obligatorios** (todos deben dar la llave `3505810975` y encontrar al cliente):
`3505810975` · `350 581 09 75` · `350-581-0975` · `(350) 581.09.75` · `+573505810975` · `573505810975` · `+57 350 581 0975` · `0057 3505810975` · `3505810975 / 3101234567` (segundo número también se encuentra) · `+13055551234` **no** debe encontrar a un cliente con `3055551234`. `5810975` (7 dígitos) no busca. `3001234567 ELLA` y `3001234567  WHATSAPP` encuentran. `NO TIENE`, `None`, `0000000000` no encuentran nada. `+13055551234` encuentra `1 (305) 555-1234` y `13055551234`; `+34612345678` encuentra `612345678` (marcado "posible"). Dos clientes cotitulares con el mismo celular → un resultado con ambos titulares.

Al confirmar el vínculo: guardar `ChatwootContactLink` y escribir `cedula_andinasoft` en el contacto de Chatwoot vía API. Desvincular borra ambos.

**Modelo nuevo (BD `default`, administrado por Django):**
`ChatwootContactLink`: `account_id`, `contact_id`, `cliente` (FK a `clientes`, llave texto `idTercero`), `created_by`, `created_at`, `updated_at`; único por `(account_id, contact_id)`.

## 5. Negocios y cartera

- **Un negocio es `(proyecto, idadjudicacion)`**: cada proyecto tiene su BD. Ninguna ruta usa un id entero global.
- Listado de negocios: `client_portal.selectors.adjudications.list_business_cards(cedula)`. Se filtra por los proyectos del usuario (`Usuarios_Proyectos`); los de otros proyectos se muestran solo como "existe un negocio en otro proyecto".
- Saldos y cuotas: **única fuente `andinasoft.estado_cuenta_service.build_estado_cuenta_context`**. No usar `client_portal.selectors.payments.get_payment_summary` (hace varias consultas por cuota y puede dar cifras distintas).
- Pagos: `Recaudos_general` del proyecto (recibos con fecha, valor, forma de pago).
- **Saldos como el PDF:** el `saldo` de `info_adjudicaciones` es el valor financiado, no lo pendiente. El saldo de capital y lo abonado salen de `saldos_cuotas` (`saldo_ci + saldo_fn`, `abonado_ci + abonado_fn`) y "para cancelar hoy" = `total_pago_hoy` + mora, igual que `statement_of_account.html`. El plan de pagos completo usa `estado_cuenta_service.plan_pagos_con_saldos` (mismas fórmulas; verificado igual al PDF en 24 negocios con mora).
- Criterio de aceptación: las cifras del panel coinciden con el PDF del estado de cuenta del mismo día.

## 6. Seguimientos (gestión de cobro)

- Reutilizar la tabla existente `seguimientos` de cada proyecto y sus opciones de `form_seguimiento` (`Cobro`, `Envio informacion`, `Peticion`, `Saludo`, `Anotacion`; forma de contacto `Whatsapp` por defecto). No crear tipos nuevos que rompan los reportes.
- `seguimientos` es **MyISAM y `managed=False`**: no se le agregan columnas. Tabla lateral nueva en `default`:
  `ChatwootSeguimientoRef`: `proyecto`, `adj`, `seguimiento_id`, `account_id`, `conversation_id`, `idempotency_key` (único), `created_by`, `created_at`.
- **Idempotencia:** el panel genera un UUID por envío; si ya existe en `ChatwootSeguimientoRef`, se devuelve el registro existente sin crear otro (`atomic` no protege tablas MyISAM).
- Tras guardar: nota privada en la conversación de Chatwoot con el resumen del seguimiento (opcional en el MVP; si falla la API de Chatwoot, el seguimiento igual queda guardado).
- `respuesta_cliente` es `varchar(500)`, igual que el formulario.

## 7. Vistas (sin DRF)

| Método | Ruta | Propósito |
|---|---|---|
| GET | `/chatwoot/panel/` | Página del iframe (sin datos) |
| GET / POST | `/chatwoot/conectar/` | Ventana emergente: login normal + autorizar → entrega token |
| POST | `/chatwoot/api/desconectar/` | Revoca el token actual |
| POST | `/chatwoot/api/contexto/` | Recibe `account_id`, `contact_id`, teléfono, atributos → cliente sugerido/vinculado y negocios |
| POST / DELETE | `/chatwoot/api/vinculo/` | Vincular / desvincular contacto ↔ cliente |
| GET | `/chatwoot/api/<proyecto>/<adj>/cartera/` | Resumen (vencido, mora, total a pagar hoy, próximas cuotas) |
| GET | `/chatwoot/api/<proyecto>/<adj>/cuotas/` | Plan de pagos con saldo por cuota |
| GET | `/chatwoot/api/<proyecto>/<adj>/pagos/` | Recibos aplicados |
| GET / POST | `/chatwoot/api/<proyecto>/<adj>/seguimientos/` | Historial / registrar |

Rutas `/chatwoot/api/...`: decorador `chatwoot_panel_auth` (Bearer), `check_project(request, proyecto)`, permiso de lectura de cartera y auditoría. Respuestas con `Decimal` serializado como texto.

## 8. Interfaz

- Cabecera: contacto de Chatwoot (nombre, teléfono), estado (vinculado / sugerido / sin identificar), usuario de Andinasoft en sesión (y aviso si su email no coincide con `currentAgent.email`), selector de negocio.
- Pestañas internas: **Cartera** · **Cuotas y pagos** · **Seguimiento**.
- "Copiar resumen" con respaldo para portapapeles bloqueado.
- Estados: cargando, sin sesión, sin autorización, sin coincidencias, varias coincidencias, sin negocios, error.
- Ancho completo de la conversación; respetar `theme` (claro/oscuro) que envía Chatwoot.

### 8.1 Estilo visual: igual a Chatwoot, no Bootstrap

El panel **no** hereda `base.html` ni Bootstrap de Andinasoft: es una página independiente que debe verse como parte de Chatwoot.

- **Colores:** copiar los tokens de Chatwoot (`app/javascript/dashboard/assets/scss/_next-colors.scss`, licencia MIT) a un CSS propio `static/chatwoot_panel/panel.css` como variables (`--slate-1…12`, `--blue-9`, `--ruby-9`, `--amber-9`, `--teal-9`, `--surface-1/2`, `--border-weak/strong`, `--solid-1/2/3`), con sus valores de modo claro en `:root` y de modo oscuro en `.dark`.
- **Tema:** el JS pone o quita la clase `.dark` en `<html>` según `data.theme` del `appContext` (Chatwoot lo reenvía cuando el agente cambia de tema).
- **Tipografía:** Inter servida desde Andinasoft (sin Google Fonts, para mantener la CSP estricta), 14px base, pesos 420/500/600 como Chatwoot.
- **Componentes a imitar:** pestañas compactas con subrayado azul (como las pestañas Mensajes/Cartera de la conversación), tarjetas con borde `--border-weak` y radio 12px sobre `--surface-1`, botones sólidos `--blue-9` y botones "ghost" `--slate`, inputs de 32–36px de alto, etiquetas tipo *label* de Chatwoot para estados: `--ruby-9` vencida/mora, `--amber-9` próxima, `--teal-9` pagada, `--slate` pendiente.
- **Sin frameworks ni CDN:** CSS y JS propios servidos desde Andinasoft (`script-src 'self'`), sin Tailwind por CDN ni jQuery. Página liviana porque se recarga en cada conversación.
- Referencia visual: capturas de la pantalla de conversación y de Ajustes de Chatwoot (claro y oscuro) para comparar en la revisión de la Etapa 1.

## 9. Etapas

**Etapa 0 – Verificación (antes de programar)**
- [ ] Versión de Chatwoot instalada y que la pestaña Dashboard App aparece.
- [x] Dominios: Chatwoot y Andinasoft están en dominios distintos → autenticación por token (§3).
- [ ] Crear el atributo de contacto `cedula_andinasoft` en Chatwoot.
- [ ] Token de API de Chatwoot (usuario administrador o agent bot) para notas, atributos y etiquetas.
- [x] Largo de `seguimientos.respuesta_cliente`: `varchar(500)` en 10 proyectos (coincide con el formulario). **Alttum no tiene tabla `seguimientos`** en la BD local: confirmar en producción; si no existe, el panel no ofrece registrar seguimientos en Alttum.
- [x] Formatos reales de teléfonos analizados (§4.2). Repetir el conteo en producción.

**Etapa 1 – Panel embebido y acceso (hecha 2026-10-08, app `chatwoot_panel`):** vista exenta de X-Frame con CSP `frame-ancestors`, lectura de contexto con validación de origen, ventana `/chatwoot/conectar/`, `ChatwootPanelToken` + decorador Bearer, desconectar/revocar, auditoría, estilo visual de Chatwoot (§8.1) con modo claro/oscuro.
**Etapa 2 – Identificación y cartera (hecha 2026-10-08):** `ChatwootContactLink`, resolución en 4 pasos, escritura del atributo en Chatwoot, negocios filtrados por proyecto, resumen y cuotas desde `build_estado_cuenta_context`.
**Etapa 3 – Pagos y seguimientos (hecha 2026-10-08):** recibos, registro idempotente en `seguimientos` + `ChatwootSeguimientoRef`, nota privada opcional, copiar resumen.
**Etapa 4 – Pruebas y piloto:** token vencido/revocado/de usuario desactivado, contexto falsificado (otro teléfono/conversación), usuario sin el proyecto, contactos duplicados, cambio rápido de conversación, Chrome/Firefox/Safari/incógnito, piloto con pocos agentes.

## 10. Fase 2

- Enviar el PDF de estado de cuenta (ya existe: `mcp_server.tools.adjudicaciones.adjudicacion_estado_cuenta`) como adjunto por la API de Chatwoot, con confirmación del agente.
- Recordatorios de compromisos de pago vía n8n (patrón de `sac_n8n_notify` / `novaciones_notify`).
- Etiquetas automáticas de mora en Chatwoot.
- Indicadores de cumplimiento de compromisos.

**Principio rector:** Chatwoot es la interfaz de atención; Andinasoft es la fuente de verdad. El iframe solo lee; todo lo que se escribe en Chatwoot pasa por el backend.
