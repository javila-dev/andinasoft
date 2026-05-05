# Integración Alegra

Este documento describe el módulo `alegra_integration`: qué hace, cómo se usa, y cuáles son las reglas/mapeos para mantener la integración estable.

## Objetivo

Reemplazar gradualmente las interfaces contables tipo Excel/SIIGO por envío directo a Alegra, **sin eliminar los flujos viejos**.

Hoy existe un frontend interno (Dashboard + Referencias) para operar y configurar mapeos, además de los endpoints backend.

Documentos cubiertos:

- **Recibos de caja** por proyecto desde `andinasoft.shared_models.Recaudos_general` (se envían como comprobante contable).
- **Comisiones** por proyecto desde `andinasoft.shared_models.Pagocomision` (internos: comprobante; externos: documento soporte).
- **Pagos/Egresos** por empresa desde modelos de `accounting` (pagos a facturas/categorías).

Idea central: **no** mandar códigos contables legacy directamente. Alegra opera con IDs internos (banco, categoría/cuenta, contacto, centro de costo, numeración, retención, factura, etc.). Por eso existe una capa de mapeo (`AlegraMapping`) y un resolver (`MappingResolver`).

## Puntos de entrada (UI + Endpoints)

Las rutas viven bajo:

```text
/accounting/alegra/
```

### UI (interno)

- `GET /accounting/alegra/` (dashboard: preview, send, historial, enlace manual)
- `GET /accounting/alegra/references` (referencias + configuración recibos)

### Operación

- `POST /accounting/alegra/preview`
- `POST /accounting/alegra/send`
- `GET  /accounting/alegra/batches/` (listado; incluye `created_by`, contadores y `summary` cuando aplica)
- `GET  /accounting/alegra/batches/<id>` (detalle; el objeto `batch` incluye los mismos contadores, `summary` y `created_by`)
- `POST /accounting/alegra/reference-sync` (sincronizar referencias)

### Webhooks (suscripción en Alegra)

- `GET  /accounting/alegra/webhooks/` — consola: empresa (`alegra_enabled` + token), tipo de evento (`new-bill`, `edit-bill`, etc.), **host** (ej. `ibex-daring-molly.ngrok-free.app`; también acepta URL con `https://` y se normaliza) y **Suscribir**. Llama a Alegra `POST /webhooks/subscriptions` con la misma Basic Auth que el cliente REST.
- `POST /accounting/alegra/webhooks/subscribe` — JSON: `{ "empresa": "<NIT>", "event": "new-bill", "domain": "https://..." }` o `"domain": "host.sin.scheme"`. **Alegra no acepta** `http://` ni `https://` en el campo `url` del API: el backend envía `host + /accounting/alegra/webhooks/bills/`. La respuesta JSON incluye `callback_url` (como en Alegra) y `callback_url_https` (para probar en navegador).
- `GET|HEAD|POST /accounting/alegra/webhooks/bills/` — endpoint público (stub) para validación de URL; ingesta de eventos, aparte.

Cada intento de suscripción queda en **`AlegraWebhookSubscriptionLog`** (`response_json`, `response_status`, `success`).

Cada **POST** de Alegra al endpoint de ingesta se guarda en **`AlegraWebhookInboundLog`** (`payload` JSON, `raw_body` si el JSON no parseó, IP, fecha). Consúltalo en Admin o en la tabla «Recepciones desde Alegra» de `/accounting/alegra/webhooks/`.

**Forma del payload (new-bill):** raíz con `subject` (p. ej. `new-bill`) y `message.bill` (objeto factura de compra: `id`, fechas, `state`, `client` con `identification`/`name`, importes `subtotal`/`total`/`balance`, `numberTemplate.number`, `items`, etc.). Ejemplo anotado en el repo: [`docs/samples/alegra-webhook-new-bill-payload.json`](docs/samples/alegra-webhook-new-bill-payload.json).

**PDF de la factura en Alegra:** el webhook no trae el archivo. Tras crear/actualizar el radicado, en segundo plano (tras el `commit`) se llama a `GET /bills/{id}` con `fields=url,stampFiles,stamp,attachments` (ver [get_bills-id](https://developer.alegra.com/reference/get_bills-id)), se recorre la respuesta JSON en busca de URLs `http(s)` (estructura variable por país; PDF o timbre a veces anidados), se descarga y se guarda en **`Facturas.soporte_radicado`**. Lógica en `alegra_integration/bill_pdf.py`. Si no hay una URL descargable o el binario no empieza por `%PDF`, se deja constancia en log y no se adjunta.

**Adjuntos y documentación Alegra (referencia):**

- **`GET /bills/{id}`** — El parámetro `fields` admite, entre otros, `url`, `stamp`, `stampFiles`, `xml`, `additionalInfoStamp` (documento soporte electrónico en Colombia: archivos del timbre, etc.). La respuesta completa del API puede incluir propiedades adicionales (p. ej. un arreglo de adjuntos) que no siempre aparecen en el enum del OpenAPI; por eso el backend solicita también `attachments` y usa un extractor recursivo.
- **`POST /bills/{id}/attachment`** — Adjunta un archivo a la factura de proveedor; la respuesta documentada incluye `id`, `name` y **`url`** del archivo (descarga vía esa URL). Ver [post_bills-id-attachment](https://developer.alegra.com/reference/post_bills-id-attachment).
- **`DELETE /bills/attachment/{attachment_id}`** — Elimina un adjunto por id ([delete_bills-attachment-attachment-id](https://developer.alegra.com/reference/delete_bills-attachment-attachment-id)); no sustituye a una URL de lectura.

No hay en la documentación pública de **`api/v1`** un endpoint tipo “descargar adjunto solo con `attachment_id`” aparte de la **`url`** devuelta al adjuntar o la que exponga `GET /bills/{id}` en los objetos anidados. Si en producción solo llegan identificadores sin URL, conviene capturar un JSON de ejemplo en logs y escalar con soporte Alegra; el producto **e-provider** / facturación electrónica documenta rutas distintas para archivos (p. ej. [getinvoicefile](https://e-provider-docs.alegra.com/reference/getinvoicefile)), que no son el mismo flujo que `bill_pdf.py`.

**Mapeo a `accounting.Facturas`** (implementado en `alegra_integration/webhook_bills.py`): la URL de ingesta incluye `?empresa=<NIT>` al suscribir. Se guarda `alegra_bill_id = "{NIT}:{id_bill}"` para idempotencia global. Campos: `nrofactura` / `nrocausa` ← `numberTemplate.number` (o `ALEGRA-{id}`); `idtercero` / `nombretercero` ← `client.identification` / `client.name`; `valor` y `pago_neto` ← `total` o `subtotal`; `fechafactura` / `fechacausa` ← `date`; `fechavenc` ← `dueDate`; `descripcion` ← `observations` o texto por defecto; `origen` = `Alegra`. `cuenta_por_pagar`, `secuencia_cxp`, `oficina` quedan vacíos (completar después o vía otro flujo). `edit-bill` actualiza la misma fila; `delete-bill` borra si no hay `Pagos`, si no marca `alegra_bill_deleted`. Historial: usuario vía `ALEGRA_WEBHOOK_HISTORY_USERNAME` / `ALEGRA_WEBHOOK_HISTORY_USER_ID` en settings o primer usuario activo.

En el dashboard, la tabla **Lotes recientes** muestra: **Total** con desglose `(Env · OK · Err)` donde **Err** son envíos a Alegra que no quedaron OK (`enviados − OK`); columna **Usuario** = quien generó el lote (`created_by.username`).

Payload base para `preview`/`send`:

```json
{
  "empresa": "901018375",
  "proyecto": "Oasis",
  "document_type": "commission",
  "fecha_desde": "2026-04-01",
  "fecha_hasta": "2026-04-30"
}
```

`proyecto` es obligatorio para `receipt` y `commission`. Para `expense` el alcance principal es por empresa.

Tipos:

- `receipt`
- `commission`
- `expense`

### Referencias y mapeos

- `GET  /accounting/alegra/references/data?empresa=<nit>&type=banks|categories|cost_centers|number_templates`
- `GET  /accounting/alegra/references/mappings?...` (ver mapeos en BD; soporta `proyecto` + `include_null=1`)
- `GET  /accounting/alegra/references/local-accounts?empresa=<nit>` (cuentas bancarias locales)
- `POST /accounting/alegra/references/save-bank-mapping`
- `POST /accounting/alegra/references/save-category-mapping`
- `POST /accounting/alegra/references/save-numeration-mapping`
- `GET  /accounting/alegra/references/categories/search?empresa=<nit>&q=<texto>` (búsqueda server-side de catálogo contable)
- `GET  /accounting/alegra/references/interfaces?empresa=<nit>` (lista `accounting.info_interfaces` por empresa; mapeo de cuentas CXP / anticipos)
- `GET  /accounting/alegra/references/intercompany?empresa=<nit>` (lista `accounting.cuentas_intercompanias` donde la empresa es **desde** o **hacia**)

### Contactos (sincronización + enlace manual)

- `POST /accounting/alegra/contact-sync` (progresivo con cache)
- `POST /accounting/alegra/contact-link` (crear/actualizar mapeo manual)
- `GET  /accounting/alegra/contact-link/lookup-local` (trae nombre del tercero local por PK)
- `GET  /accounting/alegra/contact-link/validate-alegra` (valida que el ID no esté usado y muestra nombre en Alegra)

## Credenciales

El token de Alegra vive en `andinasoft.models.empresas`:

- `alegra_enabled`
- `alegra_token`

El cliente no permite enviar si la empresa no está habilitada o no tiene token.

Autenticación: Basic Auth usando `email:token` (codificado en base64). El cliente valida el formato y reintenta en casos comunes (429/502/503/504/timeouts).

## Estructura del módulo

Archivos principales:

- `alegra_integration/models.py`: modelos de mapeo, lote y documento.
- `alegra_integration/mapping.py`: resolución de IDs de Alegra (scoping empresa/proyecto según tipo).
- `alegra_integration/builders.py`: transforma objetos legacy en payloads Alegra.
- `alegra_integration/client.py`: cliente REST (preferido) con reintentos.
- `alegra_integration/services.py`: orquesta preview, envío, idempotencia y lotes.
- `alegra_integration/views.py`: endpoints internos + UI.

## Modelos

### `AlegraMapping`

Guarda equivalencias entre datos locales e IDs de Alegra.

Campos importantes:

- `empresa`
- `proyecto` opcional
- `mapping_type`
- `local_model`
- `local_pk`
- `local_code`
- `alegra_id`
- `alegra_payload`
- `active`

Tipos soportados:

- `bank_account`
- `category`
- `contact`
- `cost_center`
- `numeration`
- `retention`
- `payment_method`
- `bill`

Regla: si un builder necesita un ID de Alegra y no existe mapeo, debe fallar en `preview`; no debe inventar IDs ni usar codigos contables legacy como IDs de Alegra.

### `AlegraSyncBatch`

Representa una ejecución por rango de fechas.

- `created_by`: usuario Django que ejecutó el preview (y es el dueño “lógico” del lote en la UI). Puede ser `null` en datos viejos.

Estados:

- `pending`
- `preview`
- `processing`
- `done`
- `failed`
- `partial`

### `AlegraContactIndex`

Tabla auxiliar poblada al sincronizar contactos desde Alegra: identificación normalizada, tipo (`client` / `provider`), `alegra_id` y nombre. Sirve para resolver contactos cuando el origen local no encaja en `clientes` / `empresas` / `asesores`.

### `AlegraDocument`

Representa cada documento local transformado hacia Alegra.

Campos importantes:

- `empresa`
- `proyecto`
- `document_type`
- `alegra_operation`
- `transport`
- `source_model`
- `source_pk`
- `local_key`
- `payload`
- `response`
- `alegra_id`
- `status`
- `error`

`local_key` es la llave de idempotencia. Debe ser estable y especifica, por ejemplo:

- `receipt:Oasis:RC-123`
- `commission:internal:Oasis:77`
- `commission:external:Oasis:88`
- `expense:pago:1201`
- `banktransfer:<id_transferencia>:<nit_empresa>` (transferencia bancaria misma empresa vía `POST /bank-accounts/{id}/transfer`)
- `interco:transfer:<id>:<nit_empresa>:in|out` (transferencia intercompany por journal, un documento por empresa)

No cambiar el formato de llaves existentes sin migración de datos.

## Flujo Preview

`AlegraIntegrationService.preview(...)`:

1. Valida empresa, proyecto, tipo y fechas.
2. Consulta los objetos legacy.
3. Ejecuta el builder correspondiente.
4. Si el builder produce payload, guarda/actualiza `AlegraDocument` como `valid`.
5. Si falta mapeo o dato, guarda `AlegraDocument` como `invalid`.
6. Crea un `AlegraSyncBatch` con resumen.

Preview no llama a Alegra.

## Flujo Send

`AlegraIntegrationService.send(...)`:

1. Ejecuta `preview`.
2. Recorre documentos del lote.
3. Omite documentos ya enviados.
4. No envia documentos invalidos.
5. Envia segun `alegra_operation`.
6. Guarda `response`, `alegra_id`, `status` y `sent_at`.

Idempotencia:

- Si ya existe un documento `sent` para la misma `empresa + document_type + local_key`, no debe reenviarse.
- Un preview posterior no debe degradar un documento `sent` a `valid`.

## Mapeos Esperados

### Bancos

Local:

- `andinasoft.cuentas_pagos.pk`

Mapeo:

```text
mapping_type = bank_account
local_model = andinasoft.cuentas_pagos
local_pk = <idcuenta>
alegra_id = <bankAccount.id>
```

Usado en:

- Recibos de caja
- Egresos

Al guardar el mapeo de banco (`POST .../save-bank-mapping`), el backend intenta leer `GET /bank-accounts/<id>?fields=category` y, si existe categoría contable en Alegra, **crea o actualiza** un mapeo `category` con `local_code = <nro_cuentacontable>` de la cuenta local. Así los journals que usan la cuenta contable del banco encuentran el ID de categoría sin un paso manual extra.

### Categorias / Cuentas Contables

Local:

- Codigos en `consecutivos`
- Codigos en `info_interfaces`
- `cuentas_pagos.nro_cuentacontable`

Mapeo:

```text
mapping_type = category
local_code = <codigo_contable_legacy>
alegra_id = <category/account id>
```

Usado en:

- `entries[].id` de journals
- `categories[].id` de payments (egresos)
- `purchases.categories[].id` de bills/documentos soporte

### Contactos

Clientes:

```text
mapping_type = contact
local_model = andinasoft.clientes
local_pk = <idTercero>
alegra_id = <contact.id>
```

Asesores:

```text
mapping_type = contact
local_model = andinasoft.asesores
local_pk = <cedula>
alegra_id = <contact/provider.id>
```

Empresas:

```text
mapping_type = contact
local_model = andinasoft.empresas
local_pk = <Nit>
alegra_id = <contact.id>
```

### Centros De Costo

Por proyecto:

```text
mapping_type = cost_center
local_model = andinasoft.proyectos
local_pk = <nombre_proyecto>
alegra_id = <costCenter.id>
```

Para egresos sin proyecto, si se requiere uno por defecto:

```text
mapping_type = cost_center
local_code = company_default
alegra_id = <costCenter.id>
```

### Numeraciones

Mapeo por código funcional:

```text
mapping_type = numeration
local_code = receipt_cash
alegra_id = <numberTemplate.id>
```

Codigos usados:

- `receipt_cash`
- `commission_journal`
- `support_document`
- `expense_payment`, `expense_anticipo` (numeración opcional en `POST /payments`)
- `interco_journal` (numeración opcional en journals intercompany: pagos y transferencias entre empresas)

Se pueden agregar nuevos codigos cuando aparezcan nuevos documentos.

Regla de alcance:

- Por defecto `numeration` es a nivel empresa.
- Para recibos (`local_code` que empieza con `receipt_`) se permite **por proyecto con fallback a empresa**.

### Retenciones

Ejemplo para comisiones:

```text
mapping_type = retention
local_code = commission_retefuente
alegra_id = <retention.id>
```

### Metodos De Pago

Mapeo desde descripcion local a enum Alegra:

```text
mapping_type = payment_method
local_code = TRANSFERENCIA
alegra_id = transfer
```

Valores Alegra esperados:

- `cash`
- `check`
- `transfer`
- `deposit`
- `credit-card`
- `debit-card`

### Facturas / Bills

Si una factura local ya existe en Alegra:

```text
mapping_type = bill
local_model = accounting.Facturas
local_pk = <nroradicado>
alegra_id = <bill.id>
```

Si no existe este mapeo, los egresos caen a pago por categoria cuando el builder puede resolver la cuenta.

## Reglas Por Documento

### Recibos De Caja

Fuente:

- `Recaudos_general.objects.using(proyecto).filter(fecha__range=...)`

Builder:

- `ReceiptPaymentBuilder`

Operacion:

- REST `POST /journals` (comprobante contable)

Payload:

- `date`
- `reference`
- `observations`
- `idNumeration` (según configuración del proyecto/empresa)
- `entries`

Regla clave: el valor del recibo se **divide entre titulares de la adjudicación**.

- 1 entry de **débito** (banco/caja) por el total
- N entries de **crédito** (misma cuenta configurada “Anticipo de clientes”) divididos por titular
- Cada crédito lleva su `client` (contacto Alegra del titular)

La cuenta “Anticipo de clientes” se configura en la UI de Referencias por proyecto (con fallback a empresa).

### Comisiones

Fuente:

- `CALL detalle_comisiones_fecha(desde, hasta)` en la base del proyecto.

Builder principal:

- `CommissionBuilder`

Regla:

- Si `asesor.tipo_asesor == "Interno"`: asiento contable de anticipo.
- Si `asesor.tipo_asesor == "Externo"`: documento soporte.
- Si no existe asesor o no tiene tipo valido: documento invalido en preview.

#### Internos

Builder:

- `InternalCommissionAdvanceBuilder`

Operacion:

- REST `POST /journals`

Payload:

- `date`
- `reference`
- `observations`
- `idNumeration`
- `entries`

Entradas:

- Debito a `consecutivos.cuenta_aux1` por `pagoneto`.
- Credito a `consecutivos.cuenta_inmora` por `pagoneto`.
- Contacto: asesor.
- Centro de costo: proyecto, si esta mapeado.

#### Externos

Builder:

- `ExternalCommissionSupportDocumentBuilder`

Operacion:

- REST `POST /bills`

Payload:

- `date`
- `dueDate`
- `provider`
- `numberTemplate`
- `purchases.categories`
- `retentions` si hay retefuente
- `costCenter` opcional

Categoria de gasto:

- `consecutivos.cuenta_capital`

Retencion:

- `commission_retefuente`

## Egresos

Fuente:

- `accounting.Pagos`
- `accounting.Anticipos`
- `accounting.transferencias_companias`

Builder:

- `ExpensePaymentBuilder`

### Pagos y anticipos (misma empresa)

Operación habitual:

- REST `POST /payments`

Payload base:

- `type = out`
- `date`
- `bankAccount`
- `paymentMethod`
- `client` cuando aplique
- `bills` si existe mapeo a bill
- `categories` si no hay bill y se puede resolver categoría

Categoría CXP / anticipo:

- Prioridad por **interface**: `mapping_type=category`, `local_model=accounting.info_interfaces`, `local_pk=<id_doc>`, `local_code=cxp_credito_1` o `anticipo_debito_1`.
- Luego por código de cuenta legacy; fallback `default_cxp` / `default_anticipo` (mapeos `local_code` dedicados).

Contacto: además de mapeos por modelo local, puede resolverse por **identificación** usando `AlegraContactIndex` + `MappingResolver.contact_by_identification()`.

### Pagos intercompany (cuenta banco de otra empresa)

Si el gasto corresponde a la empresa del radicado pero el pago sale de banco de otra empresa, no se usa un solo `POST /payments` “mixto”: se generan **journals** (uno por empresa en el lote), con `reference` tipo `INTERCO-PAGO-<idPago>` y observaciones con nombre del proveedor. Cada lado usa la relación `accounting.cuentas_intercompanias` y mapeos de categoría **interco** (ver más abajo).

### Transferencias entre cuentas

- **Misma empresa** (`empresa_sale == empresa_entra`): `POST /bank-accounts/{cuenta_origen_alegra}/transfer` con `idDestination`, `amount`, `date`, `observations`. Sin numeraciones separadas entrada/salida en el payload.
- **Distinta empresa**: journals con `INTERCO-TRANSF-<id>`, una pata por empresa. La relación intercompany se busca en la **dirección del movimiento**: para el asiento en la empresa que **recibe** (`empresa_entra`), la fila es `empresa_desde = empresa_sale` y `empresa_hacia = empresa_entra` (dinero que “sale” de A y “entra” en B).

En el journal intercompany, una línea usa la **cuenta contable del banco** (`nro_cuentacontable` de la cuenta local) mapeada como `category` + `local_code=<código>`; la otra línea usa CxC/CxP intercompany mapeados en UI.

### Mapeos intercompany (UI Referencias → Egresos)

Relación: `accounting.cuentas_intercompanias` con `empresa_desde` / `empresa_hacia`.

Los mapeos se guardan como `category` con `local_model=accounting.cuentas_intercompanias` y `local_pk=<pk de la relación>`:

- **CxC** (lado empresa **desde**): búsqueda de categorías en Alegra con credenciales de **empresa_desde**; registro en BD con `empresa = empresa_desde`, `local_code=interco_cxc:<nit_empresa_hacia>`.
- **CxP** (lado empresa **hacia**): búsqueda en **empresa_hacia**; registro con `empresa = empresa_hacia`, `local_code=interco_cxp:<nit_empresa_desde>`.

El builder usa esas mismas llaves (`interco_cxc:<contraparte>` / `interco_cxp:<contraparte>`). Si hay varias filas para el mismo par de NITs, se elige la primera relación que **tenga** mapeo guardado antes de caer al fallback por código contable local.

### Envío multi-empresa en un lote

Si un lote incluye documentos con `empresa_id` distinto (intercompany), `send()` instancia un cliente Alegra **por empresa** según el token de cada NIT.

## Cliente Alegra

`AlegraMCPClient` opera principalmente por REST contra:

- `https://api.alegra.com/api/v1`

Endpoints usados (según builders/servicios):

- `POST /journals` (recibos, comisiones internas, egresos intercompany)
- `POST /payments` (egresos)
- `POST /bank-accounts/<id>/transfer` (transferencia entre cuentas misma empresa)
- `POST /bills` (documento soporte)
- Referencias:
  - `GET /bank-accounts` / `GET /bank-accounts/<id>` (incl. `?fields=category` para auto-mapeo contable del banco)
  - `GET /categories?format=plain`
  - `GET /cost-centers`
  - `GET /number-templates?documentType=...`
  - `GET /contacts` y `GET /contacts/<id>`

Notas:

- Se implementaron reintentos para 429 y errores transitorios (502/503/504) + timeouts.
- Para catálogos grandes (categorías/cuentas) la UI usa búsqueda server-side con cache.

## Como Extender

Para agregar un nuevo documento:

1. Agregar tipo en `AlegraSyncBatch.DOCUMENT_TYPES`.
2. Crear builder en `builders.py`.
3. Agregar consulta de fuente en `AlegraIntegrationService._build_documents`.
4. Agregar operacion en `_send_document`.
5. Definir los mapeos requeridos.
6. Agregar tests unitarios del builder y del servicio.

Reglas:

- No llamar Alegra desde builders.
- No usar IDs legacy como IDs Alegra.
- No degradar documentos `sent`.
- No reusar `local_key` para otro significado.
- Mantener las interfaces Excel viejas hasta que el frontend dedicado y la operacion nueva esten estabilizados.

## Comandos De Verificacion

```bash
python manage.py check
python manage.py test alegra_integration --noinput
python manage.py makemigrations alegra_integration --check --dry-run
```

Nota: en el estado actual del repo puede haber cambios de migracion pendientes en otras apps, por ejemplo `crm`, que no pertenecen a esta integracion.
