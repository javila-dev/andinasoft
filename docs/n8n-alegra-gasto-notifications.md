# Notificaciones n8n — gastos Alegra

Webhooks **salientes** desde Django hacia n8n para avisar contables y aprobadores en el flujo de gastos con origen Alegra.

Los flujos de email/WhatsApp/Slack los construyes en n8n; acá solo se define el contrato JSON y los puntos de disparo.

## Variables de entorno

| Variable | Descripción | Default (dev) |
|----------|-------------|---------------|
| `N8N_BASE_URL` | Base n8n | `http://localhost:5678` |
| `N8N_WEBHOOK_ALEGRA_GASTO_PENDIENTE_ASIGNACION` | URL webhook contables | `{N8N_BASE_URL}/webhook/alegra-gasto-pendiente-asignacion` |
| `N8N_WEBHOOK_ALEGRA_GASTO_PENDIENTE_APROBACION` | URL webhook aprobador | `{N8N_BASE_URL}/webhook/alegra-gasto-pendiente-aprobacion` |
| `N8N_ALEGRA_NOTIFICATIONS_ENABLED` | Activa/desactiva envíos | `False` en dev, `True` si `LIVE=1` |
| `ANDINA_PUBLIC_BASE_URL` | Base para links en el payload | vacío → paths relativos |
| `N8N_WEBHOOK_AUTH_TOKEN` | Token outbound (Andina → n8n), header `Authorization` | vacío → sin header (como antes) |
| `N8N_WEBHOOK_AUTH_PREFIX` | `Bearer` o `Token` | `Bearer` |
| `N8N_WEBHOOK_GASTO_APROBACION_SECRET` | Inbound opcional (`X-Andina-Webhook-Secret`) | o `Authorization: Token` con APIToken |

## Destinatarios

### Contables (`pendiente_asignacion`)

Configurar en Django Admin → **Notificaciones contables gasto Alegra** (`GastoContableNotificacion`): usuario + empresa + activo.

Si no hay filas activas para la empresa, **no se envía** el webhook (se registra warning en logs).

### Aprobadores (`pendiente_aprobacion`)

El destinatario es el usuario asignado en `asignar_gasto_alegra` (modelo `GastoAprobador` autoriza quién puede ser asignado). En Admin, complete **Teléfono** en la fila del aprobador (misma empresa o global); n8n lo recibe en `recipients[0].telefono` (formato sugerido: `573001234567`, sin `+`).

## Cuándo se dispara cada evento

| Evento | Dispara | No dispara |
|--------|---------|------------|
| `gasto_alegra.pendiente_asignacion` | Webhook Alegra `new-bill` crea radicado nuevo | `new-bill` idempotente (bill ya existía en mismo estado) |
| | Import `import_factura_from_alegra_bill` crea radicado | Import reconcilia existente |
| | `new-bill` idempotente que pasa de `no_aplica` → `pendiente_asignacion` | `edit-bill`, `delete-bill` |
| `gasto_alegra.pendiente_aprobacion` | Contabilidad asigna oficina **con** aprobador | Asignación sin aprobador (auto-aprobado) |
| Aprobación WhatsApp | n8n → `POST /accounting/webhooks/n8n/gasto-aprobacion` | UI web con sesión (`/ajax/gastos-alegra/aprobar`) |

**PDF:** puede descargarse en un `on_commit` posterior. El payload incluye `factura.soporte_pdf_listo` y, si ya hay archivo, `factura.soporte_pdf_url` + `links.soporte_pdf` apuntan a **Andina** (no al bucket S3 privado):

`GET {ANDINA_PUBLIC_BASE_URL}/accounting/webhooks/n8n/gastos-alegra/soporte-pdf/<radicado>`

En n8n, nodo **HTTP Request** GET con el **mismo** header `Authorization: Bearer <N8N_WEBHOOK_AUTH_TOKEN>` que el webhook saliente (o `X-Andina-Webhook-Secret` / `Token` APIToken). La app lee el PDF con credenciales AWS y lo devuelve en streaming.

Opcional: `N8N_ALEGRA_ENSURE_SOPORTE_BEFORE_NOTIFY=True` en `.env` para intentar bajar el PDF de Alegra antes del POST.

## POST entrante — Aprobar desde n8n (Andina recibe)

**URL:** `POST https://<andina>/accounting/webhooks/n8n/gasto-aprobacion`  
**Auth:** `Authorization: Bearer <N8N_WEBHOOK_AUTH_TOKEN>` (mismo que saliente) **o** `Authorization: Token <APIToken>` **o** `X-Andina-Webhook-Secret: <N8N_WEBHOOK_GASTO_APROBACION_SECRET>`

**Saliente (Andina → n8n):** `Authorization: {N8N_WEBHOOK_AUTH_PREFIX} {N8N_WEBHOOK_AUTH_TOKEN}` en todos los POST (mismo token que el Header Auth del Webhook en n8n).

**Descarga PDF (n8n → Andina):** `GET .../webhooks/n8n/gastos-alegra/soporte-pdf/<radicado>` con la misma auth (ver `links.soporte_pdf` en el payload).

```json
{
  "accion": "aprobar",
  "radicado": 17369,
  "aprobador_user_id": 5,
  "canal": "WhatsApp"
}
```

- `radicado` = `factura.pk` del webhook `pendiente_aprobacion`
- `aprobador_user_id` = `recipients[0].user_id` del mismo evento

Contrato completo y respuestas: [`alegra_api.md`](../alegra_api.md) (sección *Aprobar desde n8n / WhatsApp*).

## POST saliente 1 — Pendiente asignación

**URL:** `N8N_WEBHOOK_ALEGRA_GASTO_PENDIENTE_ASIGNACION`  
**Content-Type:** `application/json`

```json
{
  "event": "gasto_alegra.pendiente_asignacion",
  "occurred_at": "2026-05-21T15:30:00-05:00",
  "trigger": "webhook_new_bill",
  "empresa": {
    "nit": "901018375",
    "nombre": "Empresa ejemplo"
  },
  "factura": {
    "pk": 17369,
    "nrofactura": "FCII327559",
    "nombretercero": "PROVEEDOR SA",
    "idtercero": "800144355",
    "fechafactura": "2026-05-04",
    "fecharadicado": "2026-05-21",
    "valor": 142456,
    "descripcion": "...",
    "origen": "Alegra",
    "alegra_bill_id": "901018375:1",
    "alegra_id": "1",
    "alegra_document_type": "bill",
    "gasto_aprobacion_estado": "pendiente_asignacion",
    "oficina": "",
    "soporte_pdf_listo": false
  },
  "alegra_bill": {
    "id": "1",
    "total": 142456,
    "state": "open",
    "provider_name": "PROVEEDOR SA",
    "provider_identification": "800144355",
    "number": "FCII327559"
  },
  "recipients": [
    {
      "role": "contabilidad",
      "user_id": 12,
      "username": "contable1",
      "email": "contable1@empresa.co",
      "name": "María Contable"
    }
  ],
  "links": {
    "asignar": "https://app.example/accounting/gastos-alegra/asignar/"
  }
}
```

Valores de `trigger`: `webhook_new_bill`, `import_bill`.

`alegra_bill` puede omitirse si no hay snapshot del bill (p. ej. algunos imports).

## POST saliente 2 — Pendiente aprobación

**URL:** `N8N_WEBHOOK_ALEGRA_GASTO_PENDIENTE_APROBACION`

```json
{
  "event": "gasto_alegra.pendiente_aprobacion",
  "occurred_at": "2026-05-21T16:00:00-05:00",
  "trigger": "asignacion_contable",
  "empresa": {
    "nit": "901018375",
    "nombre": "Empresa ejemplo"
  },
  "factura": {
    "pk": 17369,
    "nrofactura": "FCII327559",
    "nombretercero": "PROVEEDOR SA",
    "valor": 142456,
    "oficina": "MEDELLIN",
    "gasto_aprobacion_estado": "pendiente_aprobacion",
    "gasto_aprobacion_comentario_contable": "Revisar soporte",
    "alegra_bill_id": "901018375:1",
    "alegra_id": "1",
    "soporte_pdf_listo": true
  },
  "assigned_by": {
    "role": "contabilidad",
    "user_id": 8,
    "username": "contable1",
    "email": "contable1@empresa.co",
    "name": "María Contable"
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
    "aprobar": "https://app.example/accounting/gastos-alegra/aprobar/"
  }
}
```

## Código relacionado

- Despacho: [`accounting/gasto_n8n_notify.py`](../accounting/gasto_n8n_notify.py)
- Hooks ingesta Alegra: [`alegra_integration/webhook_bills.py`](../alegra_integration/webhook_bills.py)
- Asignación/aprobación: [`accounting/gasto_aprobacion.py`](../accounting/gasto_aprobacion.py)
- Admin destinatarios contables: `GastoContableNotificacion` en Django Admin

## Notas para n8n

1. Los POST son fire-and-forget (timeout 5 s); errores HTTP se loguean en Django, no reintentan automáticamente.
2. Puedes ramificar por `event` aunque las URLs ya sean distintas.
3. Si `ANDINA_PUBLIC_BASE_URL` está vacío, `links.*` vendrá como path relativo (`/accounting/gastos-alegra/...`).
