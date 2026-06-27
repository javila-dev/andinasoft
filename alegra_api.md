# Integración Alegra

Documentación del módulo `alegra_integration` y flujos relacionados en `accounting`. Pensada para operadores y **agentes de código** que mantengan o extiendan la integración.

## Guía rápida para agentes

| Tema | Dónde leer | Archivos clave |
|------|------------|----------------|
| Preview / envío / lotes | [Flujo Preview](#flujo-preview), [Flujo Send](#flujo-send), [Dashboard](#dashboard-ui) | `services.py`, `views.py` |
| Mapeos empresa/proyecto | [Mapeos esperados](#mapeos-esperados), [MappingResolver](#mappingresolver) | `mapping.py`, `models.py` |
| Egresos `POST /payments` | [Egresos — pagos](#pagos-accountingpagos) | `builders.py` → `ExpensePaymentBuilder` |
| Intercompany | [Intercompany](#pagos-y-transferencias-intercompany) | `builders.py`, `cuentas_intercompanias` |
| Webhooks facturas compra | [Webhooks](#webhooks-facturas-de-compra) | `webhook_bills.py`, `bill_mapping.py`, `bill_pdf.py` |
| Avisos n8n gastos Alegra | [Aprobación gastos Alegra](#aprobación-gastos-alegra) (modelos Admin, payloads, flujo n8n) | `accounting/gasto_n8n_notify.py` |
| Radicado journal CxP | [Radicados y tipos](#radicados-facturas-y-tipos-en-alegra) | `accounting/journal_cxp.py` |
| Recibos (numeración OK) | [Recibos](#recibos-de-caja) | `ReceiptPaymentBuilder` — usa `numberTemplate` |
| Tests | [Comandos](#comandos-de-verificación) | `alegra_integration/tests.py` |

**Reglas que no se deben romper:**

1. Los builders **no** llaman a Alegra; solo arman JSON.
2. Los IDs de Alegra vienen de `AlegraMapping` / `MappingResolver`, no del PUC legacy directo.
3. `local_key` es idempotencia: no cambiar formatos sin migración.
4. Documentos `status=sent` no se reenvían ni se degradan a `valid` en preview.
5. Journals (recibos, intercompany y comisiones internas) usan **`numberTemplate`** (string ID) y `status: open`.
6. `POST /payments` no lleva `amount` en la raíz: el valor va en `bills[].amount` o `categories[].price`.

---

## Objetivo

Reemplazar gradualmente interfaces contables tipo Excel/SIIGO por envío directo a Alegra, **sin eliminar flujos viejos**.

Hay UI interna (Dashboard + Referencias) y API REST bajo `/accounting/alegra/`.

**Documentos cubiertos:**

| Tipo lote (`document_type`) | Fuente | Envío Alegra |
|----------------------------|--------|--------------|
| `receipt` | `Recaudos_general` (BD proyecto) | `POST /journals` |
| `commission` | `Pagocomision` (SP proyecto) | Journal interno / `POST /bills` externo |
| `gtt` | `Gtt` + `Detalle_gtt` (aprobados) | `POST /bills` (documento soporte) |
| `caja` | `gastos_caja` legalizados + `reembolsos_caja` | `POST /bills` + `POST /journals` (super-asiento) |
| `expense` | `Pagos`, `Anticipos`, `transferencias_companias` | `POST /payments`, transfer bancaria, journals interco |

**Idea central:** Alegra usa IDs propios (banco, categoría, contacto, numeración, bill, etc.). El puente es `AlegraMapping` + `MappingResolver`.

---

## Estructura del módulo

```
alegra_integration/
├── models.py              # AlegraMapping, AlegraSyncBatch, AlegraDocument, índices, webhooks logs
├── mapping.py             # MappingResolver
├── builders.py            # Payloads por tipo de documento
├── services.py            # preview, send, contact-sync, reference-sync
├── client.py              # AlegraMCPClient (REST api/v1)
├── views.py + urls.py     # Dashboard, referencias, API
├── bill_mapping.py        # Webhook/edit bill → Facturas, tipo bill/journal
├── bill_pdf.py            # GET bill, PDF, enrich
├── webhook_bills.py       # Ingesta new-bill / edit-bill / delete-bill
├── webhook_inbound_status.py
├── pago_link.py           # Pagos.alegra_payment_id tras envío
└── management/commands/
    ├── backfill_alegra_bill_sync.py
    ├── backfill_alegra_journal_detalle.py
    └── backfill_webhook_inbound.py
```

**Accounting relacionado:**

- `accounting/journal_cxp.py` — extracción CxP de journals Alegra, `alegra_journal_detalle`, mapeo PUC→categoría.
- `accounting/gasto_aprobacion*.py`, `gasto_n8n_notify.py`, `gasto_poll.py` — aprobación gastos Alegra, webhooks n8n, polling in-app.
- Admin: `GastoAprobador` (incl. `telefono`), `GastoContableNotificacion`, `GastoTesoreriaNotificacion`.
- Campos en `Facturas`: `alegra_bill_id`, `alegra_document_type`, `alegra_journal_detalle`, …
- Campos en `Pagos`: `alegra_payment_id` (migración `0086`).

---

## Puntos de entrada

Base: `/accounting/alegra/`

### UI

| Ruta | Uso |
|------|-----|
| `GET /` | Dashboard: preview, enviar, tabla documentos, historial lotes |
| `GET /references` | Mapeos bancos, categorías, numeraciones, interfaces CxP, intercompany, GTT, recibos, comisiones |

### Operación (JSON + sesión)

| Método | Ruta | Descripción |
|--------|------|-------------|
| `POST` | `/preview` | Construye lote + documentos (`status=preview`) |
| `POST` | `/send` | Preview + envío en una llamada |
| `GET` | `/batches/` | Historial lotes |
| `GET` | `/batches/<id>` | Detalle lote + documentos |
| `POST` | `/batches/<id>/send` | Envía lote ya en preview **sin reconstruir** |
| `POST` | `/reference-sync` | Sincroniza catálogos Alegra → cache/UI |

Payload preview/send:

```json
{
  "empresa": "901018375",
  "proyecto": "Oasis",
  "document_type": "expense",
  "fecha_desde": "2026-05-01",
  "fecha_hasta": "2026-05-08"
}
```

- `proyecto` **obligatorio** para `receipt` y `commission`.
- `expense` opera por **empresa** (`Pagos.empresa`, transferencias donde la empresa es `sale` o `entra`).

Tipos: `receipt` | `commission` | `gtt` | `caja` | `expense`.

### Referencias (API)

- `GET /references/data?empresa=&type=banks|categories|cost_centers|number_templates|retentions|taxes|journal_numerations`
- `POST /references/save-retention-mapping` — retenciones (p. ej. `commission_retefuente`)
- `POST /references/save-cost-center-mapping` — centros de costo por proyecto (p. ej. comisiones)
- `GET /references/mappings?...`
- `GET /references/local-accounts?empresa=`
- `POST /references/save-bank-mapping`
- `POST /references/save-category-mapping`
- `POST /references/save-numeration-mapping`
- `GET /references/categories/search?empresa=&q=`
- `GET /references/interfaces?empresa=` — `info_interfaces` → CxP / anticipos
- `GET /references/intercompany?empresa=` — `cuentas_intercompanias`

### Contactos

- `POST /contact-sync` — progresivo con cache
- `POST /contact-link` — enlace manual local ↔ Alegra
- `GET /contact-link/lookup-local`, `/contact-link/validate-alegra`
- `POST /contacts/bulk-create-from-batch`, `/contacts/missing-in-alegra-from-batch`

### Debug

- `GET /debug/mapping-check?...` — comprobar resolución de un mapeo

---

## Dashboard UI

Tras **Preview**, el resumen del lote (`batch.summary`) distingue:

| Campo | Significado |
|-------|-------------|
| `total_documents` | Filas en el lote |
| `ready_to_send` | `status=valid` — se enviarán |
| `already_sent` | `status=sent` — solo informativo |
| `built_ok` | `ready_to_send + already_sent` |
| `invalid` | Errores de mapeo/datos |

**Optimización:** si ya existe `AlegraDocument` `sent` para la misma `empresa` + `source_model` + `source_pk`, el preview **no ejecuta el builder** (no resuelve mapeos ni arma payload); solo reasocia el documento al lote.

Métricas en pantalla (modo preview):

- **Listos para enviar** = `ready_to_send`
- **Ya enviados** = `already_sent` (no se reconstruyen ni reenvían)
- **Inválidos** = errores

Modal de confirmación de envío muestra cuántos se enviarán y cuántos ya enviados se omiten.

Al **enviar**, documentos `sent` se saltan; `invalid` cuentan como fallo; respuesta incluye `skipped` en `batch.summary`.

Tabla documentos: filtros Todos / Válidos / Enviados / Inválidos / Fallidos / Omitidos. Payload con pestaña **Local** (`__local` en JSON) para depuración.

---

## Credenciales

En `andinasoft.models.empresas`:

- `alegra_enabled`
- `alegra_token`

Auth: Basic `email:token`. Cliente con reintentos 429, 502/503/504, timeouts.

---

## Modelos principales

### `AlegraMapping`

Equivalencia local → `alegra_id`. Tipos: `bank_account`, `category`, `contact`, `cost_center`, `numeration`, `retention`, `payment_method`, `bill`.

Alcance: mayoría a nivel **empresa**; recibos/GTT pueden usar **proyecto** con fallback empresa.

### `AlegraSyncBatch`

Ejecución por rango de fechas. Estados: `pending`, `preview`, `processing`, `done`, `failed`, `partial`.

`summary` (JSON): en preview `{ready_to_send, already_sent, built_ok, invalid}`; tras send `{sent, failed, skipped}`.

`created_by`: usuario que generó el preview.

### `AlegraDocument`

Un envío potencial o real. Estados: `pending`, `valid`, `invalid`, `sent`, `failed`, `skipped`.

**`local_key` (idempotencia):**

| Patrón | Uso |
|--------|-----|
| `receipt:<proyecto>:<numrecibo>` | Recibo caja |
| `commission:internal\|external:<proyecto>:<id>` | Comisión |
| `gtt:<proyecto>:<detalle_pk>` | Línea GTT |
| `caja:bill:<reembolso_id>:<gasto_id>` | Bill por gasto legalizado |
| `caja:journal:<reembolso_id>` | Journal cierre CxP del reembolso |
| `expense:pago:<id>` | Pago mismo empresa → `POST /payments` |
| `expense:anticipo:<id>` | Anticipo |
| `banktransfer:<id_transf>:<nit>` | Transferencia misma empresa |
| `interco:pago:<id>:<nit_empresa>` | Pago intercompany (journal por empresa) |
| `interco:transfer:<id>:<nit>:in\|out` | Transferencia intercompany |

Constraint único: `(empresa, document_type, local_key)`.

### `AlegraContactIndex`

Contactos Alegra por identificación (NIT/CC) para `contact_by_identification`.

### Logs webhook

- `AlegraWebhookSubscriptionLog` — suscripciones
- `AlegraWebhookInboundLog` — POST recibidos + `process_status` / `factura_id`
- `AlegraBillGetLog` — respuestas GET `/bills/{id}`

---

## Flujo Preview

`AlegraIntegrationService.preview(...)`:

1. Valida empresa, proyecto, tipo, fechas.
2. Consulta fuentes (`_build_documents`).
3. Por cada registro:
   - Si ya hay doc **`sent`** (misma empresa/proyecto + `source_model` + `source_pk`) → **skip build**, reasignar al lote.
   - Si no → `builder.build()` → `_upsert_document` como `valid` o `invalid`.
4. Persiste contadores en `batch.summary` y `success_count = ready_to_send`.

**No llama a Alegra.**

Si existe doc `sent` con misma `local_key`, `_upsert_document` solo actualiza `batch` (no pisa payload ni baja a `valid`).

---

## Flujo Send

1. Preview (o lote existente) + `_send_batch_documents`.
2. Omite `sent`; opcionalmente reintenta `failed`.
3. Detecta duplicado por `local_key` → `skipped` + `already_sent`.
4. `_send_document` según `alegra_operation`.
5. Tras éxito: `alegra_id`, `sent_at`; para `accounting.Pagos` → `sync_pago_from_alegra_document` → `Pagos.alegra_payment_id`.

`POST /journals`: tras crear, GET opcional `fields=numberTemplate,type` en `response.__fetched`.

Lotes multi-empresa: un `AlegraMCPClient` por NIT.

---

## MappingResolver

`alegra_integration/mapping.py`

Métodos habituales: `get`, `numeration`, `bank_account_for_account`, `category_for_code`, `contact_for_*`, `contact_by_identification`, `bill_for_factura`, `cost_center_for_project`.

### `category_for_puc_code(account_code)`

Para egresos por categoría y journals. Orden:

1. `AlegraMapping` `category` + `local_code` = código PUC exacto.
2. Mapeo `local_code=cxp_credito_1` cuya `description` empieza por el PUC.
3. Primera `info_interfaces` con `cuenta_credito_1` = PUC → mapeo interfaz `cxp_credito_1`.
4. Fallback `local_code=default_cxp`.

### `bill_for_factura(factura_id, factura=...)`

Orden:

1. Mapeo `bill` + `local_model=accounting.Facturas` + `local_pk`.
2. Si `alegra_document_type` es `bill` (o vacío con id tipo `NIT:34`) → id desde `alegra_bill_id`.
3. Si tipo `journal` → **no** devuelve bill (egreso va por categorías).

`sync_alegra_bill_mapping` / webhook crean mapeo `bill` al radicar compra Alegra.

---

## Radicados (`Facturas`) y tipos en Alegra

### `alegra_bill_id` (formato compuesto)

| Formato | `alegra_document_type` | Origen |
|---------|------------------------|--------|
| `{NIT}:{id_bill}` | `bill` | Webhook `new-bill`, compra en Alegra |
| `{NIT}:journal:{id}` | `journal` | Radicado manual desde comprobante Alegra |

`infer_alegra_document_type()` en `bill_mapping.py`.

### Webhook → radicado

Ver sección [Webhooks](#webhooks-facturas-de-compra). Tras `new-bill`: `gasto_aprobacion_estado=pendiente_asignacion`, sin causación hasta aprobación.

`sync_alegra_bill_mapping` enlaza bill para egresos posteriores.

### Radicado manual (sin bill Alegra)

- Causación clásica: `cuenta_por_pagar` → `info_interfaces` (concepto CxP del software legacy).
- Prefijos tipo `INT-...` en `nrofactura`.
- Egreso: **no** `bills[]`; **`categories[]`** con mapeo interfaz `cxp_credito_1` (prioridad) o PUC / `default_cxp`.

### Radicado desde journal

1. `GET .../journal-preview?empresa=&journal_id=` — `parsear_journal_para_radicado` (`journal_cxp.py`).
2. Al guardar: `alegra_journal_detalle` (JSON lista por tercero: `id_tercero`, `valor`, `account_code`, `account_codes`, `alegra_category_id`).
3. `persist_journal_cxp_mappings` crea mapeos PUC → categoría Alegra.
4. Pago: `categoria_alegra_para_pago_journal` elige fila según `pago_detallado_relacionado` / tercero factura.

Reglas CxP en journal: crédito > 0, pasivo orden 2, exclusiones retención/impuesto cuando hay 22x, nómina solo «Salarios por pagar», etc. (tests en `accounting/test_journal_cxp.py`).

---

## Webhooks facturas de compra

- Consola: `/accounting/alegra/webhooks/`
- Ingesta: `GET|POST .../webhooks/bills/?empresa=<NIT>` (suscribir sin `https://` en URL API Alegra).
- Replay: `POST .../webhooks/inbound/replay` `{log_id, empresa}`.

`process_inbound_post` → `_handle_new_bill` / `_handle_edit_bill` / `_handle_delete_bill`.

Enriquecimiento async: `GET /bills/{id}?fields=url,stampFiles,stamp,attachments` → `sync_factura_from_alegra_bill`.

Comandos:

```bash
python manage.py backfill_alegra_bill_sync --empresa=<NIT> [--dry-run] [--only-placeholder-desc] [--only-missing-pdf]
python manage.py backfill_webhook_inbound.py  # ver comando
```

---

## Aprobación gastos Alegra

**UI:** `/accounting/gastos-alegra/asignar/` (Contabilidad), `/accounting/gastos-alegra/aprobar/` (aprobador asignado).  
**Tope sin aprobador:** `empresas.alegra_gasto_max_sin_aprobador` (Admin → empresas).

Estados en `Facturas.gasto_aprobacion_estado`: `pendiente_asignacion` → `pendiente_aprobacion` → `aprobado` (o auto-aprobado al asignar sin aprobador si el valor ≤ tope).

### Modelos Admin (destinatarios y teléfono)

| Modelo | Admin | Para qué |
|--------|-------|----------|
| `GastoAprobador` | Aprobadores de gasto Alegra | Quién puede ser asignado como aprobador. Campo **`telefono`** (ej. `573001234567`, sin `+`) → va en `recipients[].telefono` del webhook **pendiente_aprobacion** para WhatsApp en n8n. Prioridad: fila de la **misma empresa** del radicado; si no hay, fila con empresa vacía (todas). |
| `GastoContableNotificacion` | Notificaciones contables gasto Alegra | Quién recibe el webhook **pendiente_asignacion** y el polling in-app (contabilidad). Sin filas activas para la empresa → no se envía POST a n8n. |
| `GastoTesoreriaNotificacion` | Notificación tesorería gasto Alegra | **Una fila por usuario**; M2M `empresas` y M2M `oficinas` (`GastoNotificacionOficina`: MONTERIA, MEDELLIN). Polling cuando el radicado pasa a `aprobado`. |

Los grupos Django **Contabilidad** / permisos de facturas controlan la **UI** de asignar; los avisos n8n usan solo las tablas anteriores.

### Flujo n8n (resumen)

```mermaid
sequenceDiagram
    participant Alegra
    participant Andina
    participant n8n
    participant Aprobador

    Alegra->>Andina: webhook new-bill
    Andina->>n8n: POST pendiente_asignacion (contables)
    Note over n8n: email/WhatsApp a recipients[]

    Andina->>Andina: contable asigna oficina + aprobador
    Andina->>n8n: POST pendiente_aprobacion (telefono en recipient)
    n8n->>Aprobador: WhatsApp recipients[0].telefono
    Aprobador->>n8n: confirma sí
    n8n->>Andina: POST /webhooks/n8n/gasto-aprobacion
```

| Paso | Dirección | URL / evento |
|------|-----------|----------------|
| 1 | Andina → n8n | `event: gasto_alegra.pendiente_asignacion` |
| 2 | Andina → n8n | `event: gasto_alegra.pendiente_aprobacion` (incluye `recipients[0].telefono`) |
| 3 | n8n → Andina | `POST /accounting/webhooks/n8n/gasto-aprobacion` |

Detalle de payloads: [Notificaciones n8n salientes](#notificaciones-n8n-salientes-gastos-alegra). Guía operativa: `docs/n8n-alegra-gasto-notifications.md`.

### Avisos in-app (polling)

Con la app abierta (sesión activa), el navegador consulta cada **60 s** si hay radicados nuevos `origen=Alegra` en `pendiente_asignacion` para las empresas donde el usuario tiene fila activa en `GastoContableNotificacion`. Complementa (no reemplaza) los avisos n8n/email/WhatsApp.

| Aspecto | Detalle |
|---------|---------|
| Endpoint | `GET /accounting/ajax/gastos-alegra/notificaciones-poll?since_pk=0` |
| Auth | Sesión (`@login_required`) |
| Sin configuración | `{ "enabled": false }` — el JS deja de hacer polling |
| Query `since_pk` | Entero; solo radicados con `pk > since_pk` (default `0`) |
| Respuesta | `enabled`, `since_pk`, `max_pk`, `count`, `items[]` (máx. 20 por respuesta) |
| Toast | Tras el **primer** poll con `enabled: true` en la pestaña, se guarda `max_pk` en `sessionStorage` (`alegra_gasto_poll_since_pk`) **sin** toast; en polls siguientes, si `items.length > 0`, toast en `#general-right-alert` con enlace a asignar |
| Pausa | No poll si `document.hidden`; poll inmediato al volver visible (`visibilitychange`) |
| Página asignar | Sin toast si la URL es `/accounting/gastos-alegra/asignar/` |

Código: `accounting/gasto_poll.py`, vista `ajax_gastos_alegra_notificaciones_poll`, partial `templates/accounting/_gasto_alegra_poll.html`.

#### Tesorería — gastos aprobados (polling)

Cuando un radicado Alegra pasa a `gasto_aprobacion_estado=aprobado` (aprobador o auto-aprobación sin aprobador), los usuarios con fila activa en **`GastoTesoreriaNotificacion`** reciben toast si el radicado coincide con **empresa** y **oficina** configuradas (M2M; no hace falta una fila por cada combinación).

| Aspecto | Detalle |
|---------|---------|
| Admin | `GastoTesoreriaNotificacion`: usuario (único), empresas y oficinas (filter horizontal), activo |
| Endpoint | `GET /accounting/ajax/gastos-alegra/tesoreria-notificaciones-poll?since_ts=` (ISO 8601) |
| Filtro | `origen=Alegra`, `aprobado`, `gasto_aprobado_en > since_ts`, empresa ∈ M2M, `oficina` ∈ M2M |
| Sin empresas u oficinas en M2M | `{ "enabled": false }` |
| Watermark | `sessionStorage` clave `alegra_gasto_tesoreria_poll_since_ts` (`max_ts` de la respuesta) |
| Toast | Enlace a `/accounting/pagarfactura`; sin toast en esa página |
| Código | `accounting/gasto_tesoreria_poll.py`, `_gasto_tesoreria_poll.html` |

### APIs internas (Andina recibe del navegador)

Estas rutas son **entrada a Django** (sesión + CSRF). **No** son webhooks n8n.

#### Sugerencias de asignación (historial del tercero)

`GET /accounting/ajax/gastos-alegra/sugerencias-asignacion`

Query: `radicado` (pk del pendiente) **o** `empresa` + `id_tercero`.

**Respuesta 200:**

```json
{
  "historial": [
    {
      "pk": 17300,
      "nombretercero": "PROVEEDOR SA",
      "oficina": "MEDELLIN",
      "valor": 120000,
      "descripcion": "Servicios consultoría…",
      "aprobador_id": 5,
      "aprobador_label": "Jefe Área",
      "sin_aprobador": false,
      "fecharadicado": "2026-04-15"
    }
  ],
  "sugerencia": {
    "oficina": "MEDELLIN",
    "aprobador_id": 5
  }
}
```

Hasta **5** ítems en `historial` (mismo `idtercero` + empresa, ya asignados). La UI muestra el historial en letra pequeña y precarga oficina/aprobador según `sugerencia`.

#### Asignar oficina y aprobador (Contabilidad)

`POST /accounting/ajax/gastos-alegra/asignar`  
`Content-Type: application/json`

**Body que espera Andina:**

```json
{
  "radicado": 17369,
  "oficina": "MEDELLIN",
  "aprobador_id": 5,
  "comentario_contable": "Revisar soporte"
}
```

| Campo | Tipo | Obligatorio | Notas |
|-------|------|-------------|-------|
| `radicado` | int | sí | `Facturas.pk` |
| `oficina` | string | sí | `MONTERIA` o `MEDELLIN` |
| `aprobador_id` | int / null | no | Vacío o omitido → aprobación automática si el valor ≤ tope `alegra_gasto_max_sin_aprobador` |
| `comentario_contable` | string | no | Máx. 2000 caracteres |

**Respuesta 200:**

```json
{
  "ok": true,
  "factura": {
    "pk": 17369,
    "nrofactura": "FCII327559",
    "nombretercero": "PROVEEDOR SA",
    "fechafactura": "2026-05-04",
    "fecharadicado": "2026-05-21",
    "valor": 142456,
    "empresa": "901018375",
    "empresa_nombre": "Empresa ejemplo",
    "descripcion": "...",
    "alegra_bill_id": "901018375:1",
    "alegra_document_type": "bill",
    "alegra_id": "1",
    "oficina": "MEDELLIN",
    "gasto_aprobacion_estado": "pendiente_aprobacion",
    "gasto_aprobacion_comentario_contable": "Revisar soporte",
    "gasto_aprobador_asignado": "Jefe Área"
  }
}
```

Si se asignó aprobador, Django dispara el webhook n8n **pendiente_aprobacion** (ver abajo). Si fue auto-aprobado, `gasto_aprobacion_estado` será `aprobado` y **no** hay POST a n8n de aprobación pendiente.

#### Descartar radicado (Contabilidad)

`POST /accounting/ajax/gastos-alegra/eliminar`  
`Content-Type: application/json`

Quita de la cola un radicado Alegra **pendiente de asignación** que no debe procesarse (p. ej. bill recibido por webhook por error). Solo borra el registro local y desactiva el mapeo bill; **no** elimina el documento en Alegra.

**Body:**

```json
{ "radicado": 17369 }
```

**Respuesta 200:**

```json
{
  "ok": true,
  "eliminado": {
    "pk": 17369,
    "nrofactura": "FCII327559",
    "nombretercero": "PROVEEDOR SA",
    "valor": 142456,
    "alegra_bill_id": "901018375:1"
  }
}
```

Errores: radicado con pagos, ya asignado/aprobado, o sin permiso Contabilidad.

#### Aprobar gasto (aprobador asignado)

`POST /accounting/ajax/gastos-alegra/aprobar`  
`Content-Type: application/json`

**Body que espera Andina (exacto, lo envía la UI):**

```json
{
  "radicado": 17369
}
```

| Campo | Tipo | Obligatorio | Notas |
|-------|------|-------------|-------|
| `radicado` | int | sí | `Facturas.pk`; debe estar en `pendiente_aprobacion` y el usuario debe ser `gasto_aprobador_asignado` (o superuser) |

**Respuesta 200:**

```json
{
  "ok": true,
  "factura": {
    "pk": 17369,
    "nrofactura": "FCII327559",
    "nombretercero": "PROVEEDOR SA",
    "fechafactura": "2026-05-04",
    "fecharadicado": "2026-05-21",
    "valor": 142456,
    "empresa": "901018375",
    "empresa_nombre": "Empresa ejemplo",
    "descripcion": "...",
    "alegra_bill_id": "901018375:1",
    "alegra_document_type": "bill",
    "alegra_id": "1",
    "oficina": "MEDELLIN",
    "gasto_aprobacion_estado": "aprobado",
    "gasto_aprobacion_comentario_contable": "Revisar soporte",
    "gasto_aprobador_asignado": "Jefe Área"
  }
}
```

Errores habituales: `403` sin permiso / no es el aprobador asignado; `400` estado distinto de `pendiente_aprobacion` o radicado con pagos.

#### Aprobar con un clic (WhatsApp — recomendado)

`GET /accounting/gastos-alegra/aprobar-link/<radicado>/<token>/`  
Sin sesión Django ni CSRF. **Un GET = aprobación** (respuesta `text/plain`).

El token va firmado en la URL (HMAC + expiración). Se genera al asignar y llega en el webhook `pendiente_aprobacion` como `links.aprobar`:

```
https://app.example/accounting/gastos-alegra/aprobar-link/17369/<token>/
```

| Aspecto | Detalle |
|---------|---------|
| Seguridad | Token ligado a `radicado` + `gasto_aprobador_asignado`; expira (`GASTO_APROBACION_LINK_MAX_AGE`, default 72 h) |
| Secreto firma | `GASTO_APROBACION_LINK_SECRET` o `N8N_WEBHOOK_GASTO_APROBACION_SECRET` o `SECRET_KEY` |
| Respuesta OK | `Gasto #17369 (PROVEEDOR SA) aprobado correctamente.` |
| Ya aprobado | `200` idempotente: `… ya estaba aprobado.` |
| JSON opcional | `Accept: application/json` o `?format=json` |

**Flujo n8n:** Webhook `pendiente_aprobacion` → WhatsApp con `{{ $json.links.aprobar }}` → el aprobador abre el link. **No hace falta** mantener hilo conversacional ni llamar otro endpoint.

`links.aprobar_ui` sigue apuntando a la pantalla web de aprobación (sesión Django).

#### Aprobar desde n8n / WhatsApp (POST legacy)

`POST /accounting/webhooks/n8n/gasto-aprobacion`  
`Content-Type: application/json`  
Sin sesión Django ni CSRF (`@csrf_exempt`).

**Autenticación (una de dos):**

| Método | Header |
|--------|--------|
| API Token (recomendado si ya usas `api_auth`) | `Authorization: Token <clave APIToken>` |
| Secreto dedicado | `X-Andina-Webhook-Secret: <N8N_WEBHOOK_GASTO_APROBACION_SECRET>` |

Sin ninguna configuración válida → `401`.

**Body que espera Andina:**

```json
{
  "accion": "aprobar",
  "radicado": 17369,
  "aprobador_user_id": 5,
  "canal": "WhatsApp"
}
```

| Campo | Tipo | Obligatorio | Notas |
|-------|------|-------------|-------|
| `accion` | string | no (default `aprobar`) | Solo `aprobar` está implementado |
| `radicado` | int | sí | `Facturas.pk` en `pendiente_aprobacion` |
| `aprobador_user_id` | int | sí | Debe ser el `gasto_aprobador_asignado` y usuario activo en `GastoAprobador` |
| `canal` | string | no | Default `WhatsApp/n8n`; se guarda en `history_facturas` |

**Mapeo desde el webhook `pendiente_aprobacion`:**

| Campo del POST a Andina | Expresión n8n (ejemplo) |
|-------------------------|-------------------------|
| `radicado` | `{{ $json.factura.pk }}` |
| `aprobador_user_id` | `{{ $json.recipients[0].user_id }}` |
| WhatsApp al aprobador | `{{ $json.recipients[0].telefono }}` (requiere `GastoAprobador.telefono` en Admin) |

**Respuesta 200:**

```json
{
  "ok": true,
  "accion": "aprobar",
  "canal": "WhatsApp",
  "factura": {
    "pk": 17369,
    "gasto_aprobacion_estado": "aprobado",
    "gasto_aprobador_asignado": "Jefe Área",
    "...": "..."
  }
}
```

**Flujo WhatsApp sugerido en n8n:** nodo Webhook `alegra-gasto-pendiente-aprobacion` → mensaje a `recipients[0].telefono` con el link `links.aprobar` (un clic). El POST legacy abajo solo si necesitas aprobar server-side con `Authorization: Token …` (APIToken) o `X-Andina-Webhook-Secret`.

**Andina → n8n (todos los POST salientes, incl. gastos Alegra y upload movimientos):** envían `Authorization: {N8N_WEBHOOK_AUTH_PREFIX} {N8N_WEBHOOK_AUTH_TOKEN}` si el token está en `.env`. Código: `accounting/n8n_http.py`.

---

### Notificaciones n8n salientes (gastos Alegra)

Django hace `POST` JSON fire-and-forget hacia n8n (timeout 5 s). Activación: `N8N_ALEGRA_NOTIFICATIONS_ENABLED=1`. Código: `accounting/gasto_n8n_notify.py`. Copia extendida: `docs/n8n-alegra-gasto-notifications.md`.

#### Variables de entorno

| Variable | Uso |
|----------|-----|
| `N8N_ALEGRA_NOTIFICATIONS_ENABLED` | `1` / `True` para enviar webhooks salientes |
| `N8N_BASE_URL` | Base n8n (solo referencia al armar URLs) |
| `N8N_WEBHOOK_AUTH_TOKEN` | Token **saliente** (Andina → n8n): `Authorization: {prefix} {token}`. Usado en gastos Alegra, `N8N_WEBHOOK_UPLOAD_MOVEMENTS`, wompi/plink |
| `N8N_WEBHOOK_AUTH_PREFIX` | `Bearer` (default) o `Token` |
| `N8N_WEBHOOK_UPLOAD_MOVEMENTS` | URL webhook carga movimientos bancarios |
| `N8N_WEBHOOK_ALEGRA_GASTO_PENDIENTE_ASIGNACION` | URL Webhook n8n — contables |
| `N8N_WEBHOOK_ALEGRA_GASTO_PENDIENTE_APROBACION` | URL Webhook n8n — aprobador (puede ser `/webhook-test/<uuid>`) |
| `N8N_WEBHOOK_GASTO_APROBACION_SECRET` | **Entrante** opcional: `X-Andina-Webhook-Secret`. O usar `Authorization: Token` (`APIToken` Admin) |
| `GASTO_APROBACION_LINK_SECRET` | Firma de `links.aprobar` (un clic). Default: secret webhook o `SECRET_KEY` |
| `GASTO_APROBACION_LINK_MAX_AGE` | Segundos de validez del link (default `259200` = 72 h) |
| `ANDINA_PUBLIC_BASE_URL` | Base absoluta para `links.asignar` / `links.aprobar` (si vacío → path relativo) |

#### Objeto `recipients[]` (todos los eventos)

Cada destinatario incluye siempre:

| Campo | Tipo | Notas |
|-------|------|--------|
| `role` | string | `contabilidad` o `aprobador` |
| `user_id` | int | PK usuario Django |
| `username` | string | |
| `email` | string | Puede estar vacío |
| `name` | string | Nombre completo o username |
| `telefono` | string | **Aprobador:** `GastoAprobador.telefono`. **Contable:** `""` (no configurado hoy) |

#### Cuándo se dispara cada evento

| `event` | Dispara | No dispara |
|---------|---------|------------|
| `gasto_alegra.pendiente_asignacion` | `new-bill` crea radicado; import bill nuevo; `no_aplica`→`pendiente_asignacion` | `new-bill` idempotente; sin filas en `GastoContableNotificacion` |
| `gasto_alegra.pendiente_aprobacion` | Asignación con aprobador (`POST .../asignar`) | Asignación sin aprobador (auto-aprobado) |
| *(aprobación)* | n8n llama `POST .../gasto-aprobacion` | UI web `/ajax/gastos-alegra/aprobar` (no envía webhook saliente) |

#### 1) Lo que **recibes en n8n** — pendiente asignación (contables)

`POST` a la URL de asignación. `Content-Type: application/json`.

**Payload exacto** (campos siempre presentes salvo `alegra_bill`):

```json
{
  "event": "gasto_alegra.pendiente_asignacion",
  "occurred_at": "2026-05-21T15:30:00.123456-05:00",
  "trigger": "webhook_new_bill",
  "empresa": {
    "nit": "901018375",
    "nombre": "Nombre empresa en Andina"
  },
  "factura": {
    "pk": 17369,
    "nrofactura": "FCII327559",
    "nombretercero": "PROVEEDOR SA",
    "fechafactura": "2026-05-04",
    "fecharadicado": "2026-05-21",
    "valor": 142456,
    "empresa": "901018375",
    "empresa_nombre": "Nombre empresa en Andina",
    "descripcion": "Texto descripción",
    "alegra_bill_id": "901018375:28",
    "alegra_document_type": "bill",
    "alegra_id": "28",
    "oficina": "",
    "gasto_aprobacion_estado": "pendiente_asignacion",
    "gasto_aprobacion_comentario_contable": "",
    "gasto_aprobador_asignado": "",
    "idtercero": "800144355",
    "origen": "Alegra",
    "soporte_pdf_listo": false
  },
  "recipients": [
    {
      "role": "contabilidad",
      "user_id": 12,
      "username": "contable1",
      "email": "contable1@empresa.co",
      "name": "María Contable",
      "telefono": ""
    }
  ],
  "links": {
    "asignar": "https://tu-dominio/accounting/gastos-alegra/asignar/"
  },
  "alegra_bill": {
    "id": "28",
    "total": 142456,
    "state": "open",
    "provider_name": "PROVEEDOR SA",
    "provider_identification": "800144355",
    "number": "FCII327559"
  }
}
```

| Campo | Notas |
|-------|--------|
| `trigger` | `webhook_new_bill` (webhook Alegra), `import_bill` (`import_alegra_bill`), o idempotente `no_aplica`→`pendiente_asignacion` |
| `recipients` | Usuarios activos en `GastoContableNotificacion` para esa `empresa.nit`; si vacío, **no se envía** el POST |
| `recipients[].telefono` | Siempre presente; vacío para contables |
| `alegra_bill` | En `pendiente_asignacion`: snapshot del webhook Alegra. En `pendiente_aprobacion`: snapshot mínimo desde la factura (`total` = `valor`) |
| `factura.valor` / `factura.total` / `factura.pago_neto` | Enteros COP; `total` es alias de `valor` para plantillas n8n |
| `factura.soporte_pdf_listo` | `true` si ya hay archivo en `soporte_radicado` (el PDF async puede llegar después) |
| `factura.soporte_pdf_url` | URL en **Andina** para descarga por n8n (`GET .../webhooks/n8n/gastos-alegra/soporte-pdf/<radicado>`). No expone el bucket S3 privado |
| `links.soporte_pdf` | Misma URL; en n8n **HTTP Request** GET con `Authorization: Bearer <N8N_WEBHOOK_AUTH_TOKEN>` (igual que el POST saliente) |

Opcional en `.env`: `N8N_ALEGRA_ENSURE_SOPORTE_BEFORE_NOTIFY=True` intenta descargar el PDF desde Alegra **antes** del POST a n8n (más lento; solo bills Alegra).

**No** se envía el PDF en base64 dentro del JSON (payload muy pesado). n8n descarga por URL.

#### 2) Lo que **recibes en n8n** — pendiente aprobación (aprobador)

`POST` a la URL de aprobación. Misma estructura base; `event` distinto.

**Payload exacto:**

```json
{
  "event": "gasto_alegra.pendiente_aprobacion",
  "occurred_at": "2026-05-21T16:00:00.123456-05:00",
  "trigger": "asignacion_contable",
  "empresa": {
    "nit": "901018375",
    "nombre": "Nombre empresa en Andina"
  },
  "factura": {
    "pk": 17369,
    "nrofactura": "FCII327559",
    "nombretercero": "PROVEEDOR SA",
    "fechafactura": "2026-05-04",
    "fecharadicado": "2026-05-21",
    "valor": 142456,
    "empresa": "901018375",
    "empresa_nombre": "Nombre empresa en Andina",
    "descripcion": "Texto descripción",
    "alegra_bill_id": "901018375:28",
    "alegra_document_type": "bill",
    "alegra_id": "28",
    "oficina": "MEDELLIN",
    "gasto_aprobacion_estado": "pendiente_aprobacion",
    "gasto_aprobacion_comentario_contable": "Revisar soporte",
    "gasto_aprobador_asignado": "Jefe Área",
    "idtercero": "800144355",
    "origen": "Alegra",
    "soporte_pdf_listo": true
  },
  "assigned_by": {
    "role": "contabilidad",
    "user_id": 8,
    "username": "contable1",
    "email": "contable1@empresa.co",
    "name": "María Contable",
    "telefono": ""
  },
  "recipients": [
    {
      "role": "aprobador",
      "user_id": 5,
      "username": "jefe.area",
      "email": "jefe@empresa.co",
      "name": "Jefe Área",
      "telefono": "573001234567"
    }
  ],
  "links": {
    "aprobar": "https://tu-dominio/accounting/gastos-alegra/aprobar/"
  }
}
```

| Campo | Notas |
|-------|--------|
| `trigger` | Siempre `asignacion_contable` hoy |
| `recipients` | Un solo usuario: `gasto_aprobador_asignado` |
| `recipients[].telefono` | **`GastoAprobador.telefono`** (fila empresa del radicado o fila global); obligatorio en Admin para WhatsApp; si vacío, n8n no tiene número |
| `assigned_by` | Contable que llamó `POST .../asignar` (`telefono` vacío) |

**n8n — campos útiles del payload:**

- Mensaje: `factura.nombretercero`, `factura.nrofactura`, `factura.valor`, `factura.descripcion`, `links.aprobar`
- WhatsApp: `recipients[0].telefono`
- Aprobar en Andina: `factura.pk`, `recipients[0].user_id`

#### 3) Aprobación desde n8n → Andina

Andina **no** envía webhook al aprobar en UI ni al recibir la aprobación por n8n. Solo **n8n** llama a Andina: `POST /accounting/webhooks/n8n/gasto-aprobacion` (contrato en [Aprobar desde n8n / WhatsApp](#aprobar-desde-n8n--whatsapp-andina-recibe-de-n8n)).

---


## Reglas por documento

### Recibos de caja

- Builder: `ReceiptPaymentBuilder`
- `POST /journals`
- **`numberTemplate`** (string, mapeo `receipt_cash`), **`status: open`**
- Fecha = `Recaudos_general.fecha` (no `fecha_pago`)

**Débito (sin cadenas banco/interco automáticas):** por forma de pago del recibo.

1. `Recaudos_general.formapago` → fila en `formas_pago` del **proyecto** (BD proyecto).
2. Mapeo en Referencias → Recibos: `AlegraMapping` `category`, `local_model=andinasoft.formas_pago`, `local_pk=<descripcion>`, `local_code=receipt_debit` → id categoría Alegra (banco, puente datáfono, pasarela, etc.).
3. `MappingResolver.receipt_debit_for_forma_pago()` — si falta mapeo, preview inválido con mensaje claro.

La columna `formas_pago.cuenta_contable` (PUC SIIGO) se muestra en Referencias solo como referencia; **no** resuelve el débito.

**Crédito:** `receipt_client_advance` (anticipo clientes), repartido por titular de adjudicación.

**Contacto débito:**
- Forma **normal:** primer titular (`contact_for_cliente`).
- Forma **intercompany** (checkbox en Referencias + NIT contraparte en `alegra_payload` del mapeo `receipt_debit`): contacto de la empresa del grupo (`contact_for_empresa(NIT)`), típicamente la dueña del banco donde cayó el efectivo. Los créditos de anticipo siguen usando el titular.

API: `GET /references/receipt-formas-pago?empresa=&proyecto=` — incluye `intercompany`, `counterparty_nit`.

Al guardar (lote, Referencias → Recibos): `POST /references/save-receipt-formas-pago` con `{ empresa, proyecto, formas: [{ forma, alegra_id, description, intercompany, counterparty_nit }] }`.

También: `POST /references/save-category-mapping` por fila (mismo payload intercompany).

### Comisiones

Fuente: `Pagocomision` vía `CALL detalle_comisiones_fecha`. Routing por `asesor.tipo_asesor`. **Filtro por empresa:** solo entran comisiones cuyo asesor tenga `empresa_contable` igual a la empresa del lote (campo en admin de asesores; default `901018375`). Configuración por proyecto en **Referencias → Comisiones**.

| Tipo asesor | Envío Alegra | Mapeos clave |
|-------------|--------------|--------------|
| **Externo** | `POST /bills` (documento soporte, como GTT) | `commission_support_document`, `commission_expense`, `commission_retefuente` (empresa) |
| **Interno** | `POST /journals` (`numberTemplate` + `status: open`, como recibos) | `commission_journal`, `commission_debit`, `commission_credit`, **`commission` (centro de costo)** |

**Centro de costo:** por proyecto en **Referencias → Comisiones** (`local_code=commission`). Se envía en `costCenter` del bill (externos) y en cada línea del journal (internos).

**Valor del pago** (por proyecto y tipo de asesor): `commission_amount_source_external` / `commission_amount_source_internal` (`gross` → `comision`; `net` → `pagoneto`). Si solo existe el mapeo legado `commission_amount_source`, se usa como respaldo para ambos.

- **Externo + bruto:** línea `purchases.categories[].price` = `comision`; si `retefuente > 0`, `retentions[]` con mapeo `commission_retefuente` ([GET /retentions](https://developer.alegra.com/reference/get_retentions)).
- **Externo + neto:** línea = `pagoneto`; **no** se envía `retentions[]`.
- **Interno:** débito cuenta comisión, crédito cuenta por pagar; mismo valor según modo neto/bruto.

Ref. documento soporte: [POST /bills](https://developer.alegra.com/reference/post_bills) (`numberTemplate` obligatorio).

### GTT

- Solo `Gtt` aprobado, líneas `Detalle_gtt` valor > 0
- `POST /bills`, numeración `gtt_support_document`, cuentas `gtt_expense` / `gtt_cxp` por proyecto

### Caja efectivo (legalización)

Fuente: `gastos_caja` filtrados por **`forma_pago`** (caja seleccionada en el dashboard), `forma_pago.nit_empresa` y rango `fecha_gasto`. Disparo: Dashboard Alegra, tipo lote **`caja`** (sin proyecto; obligatorio elegir caja).

**Estados:**
- **`Revisado`** — contabilidad marca el gasto en Caja efectivo (tras aprobación del aprobador de caja). Alegra envía **`POST /bills`** por gasto en este estado **sin requerir reembolso**.
- **`Reembolso`** — el gasto ya fue incluido en una solicitud de reembolso. Alegra envía **`POST /bills`** igual que en `Revisado`.
- **`Legalizado`** — tras registrar legalización del reembolso. Alegra envía **`POST /journals`** por reembolso (bills ya enviados o pendientes en `Legalizado`).

Para solicitar reembolso, **`Revisado`** se trata igual que **`Aprobado`**.

**Preview / envío:** body JSON incluye `caja_id` (pk de `cuentas_pagos` con `es_caja=true` de la empresa). Se guarda en `batch.summary.caja_id`.

**Flujo por reembolso:**

1. Por cada gasto → `POST /bills` (`CajaGastoBillBuilder`).
   - `tipo_documento_soporte` en el gasto: `fe` → bill sin `numberTemplate`; `cuenta_cobro` → `numberTemplate` con numeración `caja_cuenta_cobro` (documento soporte · [GET /number-templates](https://developer.alegra.com/reference/get_number-templates-1) · `documentType=supportDocument`).
   - Proveedor: `Partners.idTercero` vía `contact_by_identification`.
   - **Línea base** (`purchases.categories[]`): `price` = subtotal del gasto (sin IVA).
   - **IVA:** si `valor_iva > 0`, `tax: [{ id }]` en la línea base; el impuesto Alegra viene del mapeo `impuesto_tax` por fila de `impuestos_legalizacion` ([GET /taxes](https://developer.alegra.com/reference/get_taxes)). Alegra calcula el IVA; el total del bill debe cuadrar con `gasto.valor` (valor pagado en caja).
   - **Retefuente:** si `valor_rte > 0` y no es asumida, `retentions[]` con `id` del mapeo `impuesto_retention` por concepto local ([GET /retentions](https://developer.alegra.com/reference/get_retentions)) y `amount` = `valor_rte`.
   - Rete asumida: no se envía `retentions[]`; el total del bill es subtotal + IVA = `valor`.
2. Tras enviar todos los bills del reembolso → un `POST /journals` (`CajaLegalizationJournalBuilder`).
   - Cada línea CxP lleva `associatedDocument: { idResource, resourceType: "bill" }` con el id del bill creado.
   - La **cuenta CxP** (`entries[].id` débito) se resuelve al enviar el bill: la respuesta de `POST /bills` **no incluye** `journal`; entonces `GET /bills/{id}?fields=journal` y, si aún falta, `GET /contacts/{provider.id}?fields=accounting` (`debtToPay.id`). Se guarda en `response.__cxp_category_id`. Último respaldo al armar el journal: `caja_cxp` / `default_cxp`.
   - Crédito único a la cuenta de caja (`caja_credit` por `cuentas_pagos`).

**Orden de envío:** el servicio envía todos los `caja_bill` antes que los `caja_journal` e inyecta `idResource` al enviar cada journal.

**Configuración:** Referencias → **Caja efectivo** (`caja_cuenta_cobro`, `caja_legalization_journal`, `caja_cxp`, `caja_credit` por caja, tabla **Impuestos legalización → Alegra** con mapeos `impuesto_tax` / `impuesto_retention` por fila de `impuestos_legalizacion`).

**API mapeo impuestos:** `GET /references/caja-impuestos?empresa=` · `POST /references/save-impuesto-mapping` (`kind`: `tax` | `retention`).

**Campo en gasto:** `gastos_caja.tipo_documento_soporte` — obligatorio para preview válido (formulario Caja efectivo o menú contextual «Tipo de soporte»).

La exportación Excel SIIGO (`interf_reemb`) se mantiene hasta retirarla en fase posterior.

---

## Egresos

Builder: `ExpensePaymentBuilder` (`builders.py`).

Fuentes en lote `expense`:

- `Pagos` (`fecha_pago`, `empresa`, `nroradicado`, `cuenta`)
- `Anticipos`
- `transferencias_companias` (sale/entra, cuentas, valor)

### Pagos (`accounting.Pagos`)

**Misma empresa** (radicado.empresa = banco.nit_empresa): `POST /payments`

Payload base (`_base_payment`):

```json
{
  "type": "out",
  "date": "2026-05-05",
  "bankAccount": { "id": "<mapeo cuenta>" },
  "paymentMethod": "transfer",
  "client": { "id": "<contacto>" },
  "numberTemplate": { "id": "<opcional expense_payment>" },
  "observations": "PAGO FACT ..."
}
```

**Destino del valor (uno de dos):**

```mermaid
flowchart TD
  A[Pago + factura] --> B{Intercompany?}
  B -->|sí| J[Journal por empresa]
  B -->|no| C{bill_for_factura?}
  C -->|sí| D["bills[].amount"]
  C -->|no| E{journal / detalle?}
  E -->|sí| F["categories[].price por PUC journal"]
  E -->|no| G{cuenta_por_pagar?}
  G -->|sí| H["categories[].price por interfaz cxp_credito_1"]
  G -->|no| X[Error preview]
```

1. **`bills`**: factura tipo `bill` con id Alegra (webhook o mapeo).
2. **`categories`**: radicado manual, journal, o sin bill — `price` = `pago.valor`, `quantity` = 1.
3. **Sin `amount` en raíz** del JSON.

Tras envío: `Pagos.alegra_payment_id` = id Alegra (`pago_link.py`).

### Anticipos

Igual `POST /payments` + `categories` vía `tipo_anticipo` → `anticipo_debito_1` o `default_anticipo`.

### Transferencias misma empresa

`POST /bank-accounts/{id_origen}/transfer`

- **Path `{id}`** = cuenta **origen** (`cuenta_sale` mapeada).
- **Body `idDestination`** = cuenta **destino** (`cuenta_entra`).
- `amount`, `date`, `observations` (ej. `TRANSFERENCIA 230-… → 234-…`).

Ref: [bankaccounttransfer](https://developer.alegra.com/reference/bankaccounttransfer) (el texto del parámetro `id` en la doc Alegra puede decir “destino”; el error API y la respuesta usan **origen** en el path).

### Pagos y transferencias intercompany

Cuando `empresa_sale != empresa_entra` o pago con banco de otra empresa:

- **`POST /journals`** (un documento por empresa del lote)
- Payload como recibos: **`numberTemplate`** (`interco_journal`), **`status: open`**, `entries` con `debit`/`credit` y 0 en el lado opuesto
- Referencias: `INTERCO-PAGO-<id>` / `INTERCO-TRANSF-<id>`
- Mapeos en `cuentas_intercompanias`: `interco_cxc:<nit_hacia>`, `interco_cxp:<nit_desde>` (UI Referencias → Egresos)
- **`client` en líneas intercompany** = contacto Alegra de la **empresa contraparte del grupo** (`andinasoft.empresas.pk` = NIT), mismo criterio que `interco_cxc:<nit>` / `interco_cxp:<nit>` en mapeos de categoría. **No** es el proveedor del radicado.

| Movimiento | Empresa del lote | NIT contraparte (`client`) | Fuente del NIT |
|------------|------------------|----------------------------|----------------|
| Transferencia in | `empresa_entra` | `empresa_sale_id` | `transferencias_companias.empresa_sale` |
| Transferencia out | `empresa_sale` | `empresa_entra_id` | `transferencias_companias.empresa_entra` |
| Pago interco (banco) | `empresa_pago` | `empresa_origen_id` | `factura.empresa` (dueña del gasto) |
| Pago interco (gasto) | `empresa_origen` | `empresa_pago_id` en línea interco | `pago.cuenta.nit_empresa_id` (dueña del banco) |

- **Transferencia:** todas las líneas del journal llevan `client` = empresa contraparte.
- **Pago intercompany:** solo la línea **interco** lleva `client` contraparte; la línea de **concepto CxP** (débito) lleva el proveedor del radicado (`factura.idtercero`); el banco (crédito) sin `client`.

Relación contable: `cuentas_intercompanias` con `empresa_desde` → `empresa_hacia` según dirección del flujo (ver builders).

Lado **empresa que paga** (banco): débito CxC interco (`client` = NIT origen gasto), crédito banco.

Lado **empresa del gasto**: débito concepto CxP (`client` = proveedor), crédito CxP interco (`client` = NIT empresa que pagó).

---

## Mapeos esperados (resumen)

### Bancos

`bank_account` + `cuentas_pagos.pk`. Auto-mapeo categoría contable del banco vía `GET /bank-accounts/{id}?fields=category`.

### Categorías / interfaces

- Por código PUC: `local_code=<puc>`
- Por concepto: `local_model=accounting.info_interfaces`, `local_pk=<id_doc>`, `local_code=cxp_credito_1` | `anticipo_debito_1`
- Respaldo: `default_cxp`, `default_anticipo`

### Numeraciones (`numeration`)

| `local_code` | Uso | Campo en payload journal |
|--------------|-----|---------------------------|
| `receipt_cash` | Recibos · numeración | `numberTemplate` |
| `receipt_debit` + `local_model=andinasoft.formas_pago` + `local_pk=<forma>` | Recibos · débito por forma de pago | `entries[].id` |
| `receipt_client_advance` | Recibos · crédito anticipo | `entries[].id` |
| `interco_journal` | Intercompany | `numberTemplate` |
| `commission_journal` | Comisión interna (journal) | `numberTemplate` |
| `commission_support_document` | Comisión externa (documento soporte) | `numberTemplate.id` en bills |
| `gtt_support_document` | GTT | `numberTemplate.id` en bills |
| `caja_cuenta_cobro` | Caja · cuenta de cobro | `numberTemplate.id` en bills (solo cuenta de cobro) |
| `caja_legalization_journal` | Caja · comprobante cierre | `numberTemplate` (string) en journals |
| `caja_cxp` | Caja · CxP journal (respaldo) | `entries[].id` débito si el bill no trae CxP |
| `caja_credit` + `cuentas_pagos.pk` | Caja · crédito journal | `entries[].id` crédito |
| `impuesto_tax` + `impuestos_legalizacion.pk` | Caja · IVA en bill | `purchases.categories[].tax[].id` |
| `impuesto_retention` + `impuestos_legalizacion.pk` | Caja · retefuente en bill | `retentions[].id` |
| `commission_amount_source_external` | Base valor documento soporte | — (config CATEGORY) |
| `commission_amount_source_internal` | Base valor journal interno | — (config CATEGORY) |
| `commission_expense` | Gasto en documento soporte | `purchases.categories` |
| `commission_debit` / `commission_credit` | Asiento interno | `entries` |
| `commission` (cost_center) | Centro de costo por proyecto | `costCenter` en bill / entries |
| `commission_retefuente` | Retención (modo bruto) | `retentions[].id` |
| `expense_payment`, `expense_anticipo` | Opcional en payments | `numberTemplate.id` |

### Bills

`bill` + `Facturas.pk` o id parseado de `alegra_bill_id` tipo bill.

---

## Cliente REST

`https://api.alegra.com/api/v1`

Operaciones: `create_journal`, `create_out_payment`, `bank_account_transfer`, `create_bill`, `get_bill`, `get_journal`, catálogos, webhooks.

---

## Comandos de verificación y mantenimiento

```bash
python manage.py check
python manage.py test alegra_integration accounting.test_journal_cxp --noinput
```

| Comando | Propósito |
|---------|-----------|
| `backfill_alegra_bill_sync` | PDF + enrich radicados bill existentes |
| `backfill_alegra_journal_detalle` | Rellena `alegra_journal_detalle` desde GET journal |
| `backfill_webhook_inbound` | Reprocesa logs webhook |

Migraciones accounting relevantes: `0085_facturas_alegra_document_type`, `0086_pagos_alegra_payment_id`.

---

## Cómo extender

1. Tipo en `AlegraSyncBatch.DOCUMENT_TYPES`.
2. Builder en `builders.py`.
3. Fuente en `_build_documents`.
4. Rama en `_send_document`.
5. Mapeos en Referencias + tests.

No: llamar Alegra desde builders; inventar IDs; cambiar `local_key`; degradar `sent`.

---

## Referencias externas

- [Alegra API](https://developer.alegra.com/)
- [POST /journals](https://developer.alegra.com/reference/journalscreate)
- [POST /payments](https://developer.alegra.com/reference/post_payments)
- [Transferencia bancaria](https://developer.alegra.com/reference/bankaccounttransfer)
- Ejemplo webhook: `docs/samples/alegra-webhook-new-bill-payload.json`
