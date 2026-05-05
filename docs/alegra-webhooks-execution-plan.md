# Plan de ejecución — Webhooks Alegra → Radicado + causación (`accounting`)

Documento **chequeable**: marca `[x]` cuando completes cada ítem. Stack **solo `accounting`**. Integración saliente actual **sin cambios** en esta fase. `buildingcontrol` **fuera de alcance**.

**URL pública de desarrollo (ngrok):** `https://ibex-daring-molly.ngrok-free.app`  
**URL final del webhook (ejemplo):** `https://ibex-daring-molly.ngrok-free.app` + `<path que definas>`, p. ej. `/accounting/webhooks/alegra/bills/`

**Referencia Alegra:** [POST /webhooks/subscriptions](https://developer.alegra.com/reference/post_webhooks-subscriptions) — eventos: `new-bill`, `edit-bill`, `delete-bill`.

---

## Fase 0 — Acuerdos y acceso

**Estado (última actualización):** Fase 0 **completa** (incl. ejemplo de payload `new-bill`).

- [x] **0.1** Credenciales por empresa: el token vive en `andinasoft.models.empresas` (`alegra_token`, `alegra_enabled`). Detalle en [`alegra_api.md`](../alegra_api.md) (sección del token / cliente). Crear suscripción de webhook en Alegra cuando toque la Fase 7.
- [x] **0.2** Payload real `new-bill` documentado: [`docs/samples/alegra-webhook-new-bill-payload.json`](samples/alegra-webhook-new-bill-payload.json) y nota en `alegra_api.md`. Estructura: `subject` + `message.bill` (`id`, `client`, totales, `numberTemplate.number`, …).
- [x] **0.3** Autenticación / uso del API documentado y probado contra endpoints: [`alegra_api.md`](../alegra_api.md) (Basic Auth `email:token`, token en `empresas`). Ajustar el handler del webhook si Alegra exige validación adicional **solo** en el callback (documentar diferencia si la hay).
- [x] **0.4** Túnel ngrok operativo: `https://ibex-daring-molly.ngrok-free.app`. Cuando exista la ruta del webhook en Django, verificar `POST` real desde Alegra (Fase 7).

---

## Fase 1 — Modelo y migración

- [ ] **1.1** Añadir en `accounting.Facturas` el campo **`alegra_bill_id`** (tipo acorde al ID Alegra), **`unique=True`**, `null=True`/`blank=True` si conviven facturas sin Alegra.
- [ ] **1.2** Añadir campos para **`delete-bill` cuando hay pagos** (no se borra la fila): p. ej. `alegra_bill_deleted_at` (DateTime null) y/o `alegra_bill_deleted` (Boolean), según convención del proyecto.
- [ ] **1.3** Generar y revisar **migración** Django; aplicar en dev.
- [ ] **1.4** Si en producción existe la vista SQL **`info_facturas`**: planificar script SQL para exponer la nueva semántica (opcional en dev hasta que existan datos de prueba).

---

## Fase 2 — Mapeo negocio: Bill Alegra → `Facturas`

- [ ] **2.1** Tabla escrita **campo Alegra → campo Django** (`nrofactura`, `idtercero`, `nombretercero`, `valor`, `pago_neto`, `fechafactura`, `fechacausa`, `nrocausa`, `cuenta_por_pagar`, `secuencia_cxp`, `empresa`, `oficina`, `origen`, etc.).
- [ ] **2.2** Definir **valores por defecto** obligatorios que el bill no traiga (`empresa`, `oficina`, `origen`).
- [ ] **2.3** Estrategia para **`UniqueConstraint(idtercero, nrofactura)`**: prefijos, normalización NIT, o deduplicación ante `edit-bill`.
- [ ] **2.4** Definir texto de **`history_facturas`** para altas/ediciones/borrado lógico automáticas (usuario sistema o técnico acordado).

---

## Fase 3 — Endpoint webhook

- [ ] **3.1** Crear vista **CSRF-exenta** (p. ej. `@csrf_exempt` + validación propia) o mecanismo recomendado por Django para webhooks externos.
- [ ] **3.2** Registrar **URL** en el `urlpatterns` de `accounting` (y `include` desde `andina` si aplica).
- [ ] **3.3** Implementar **validación de origen** (firma/token/documentado).
- [ ] **3.4** Parser de evento: discriminar `new-bill` / `edit-bill` / `delete-bill` (y desconocidos → log + 200 o 400 según política).
- [ ] **3.5** Respuestas HTTP: rápidas, sin fugas de trazas internas en JSON de error.

---

## Fase 4 — Lógica por evento

### `new-bill`

- [ ] **4.1** Si existe `Facturas` con mismo **`alegra_bill_id`** → **no crear** (idempotencia); opcionalmente reconciliar con payload.
- [ ] **4.2** Si no existe → **`Facturas.objects.create(...)`** con todos los campos acordados en Fase 2 + `alegra_bill_id`.
- [ ] **4.3** Crear registro en **`history_facturas`** coherente con el flujo actual.

### `edit-bill`

- [ ] **4.4** Localizar por **`alegra_bill_id`**; actualizar solo campos permitidos; respetar pagos ya existentes (no romper montos críticos sin regla de negocio).

### `delete-bill`

- [ ] **4.5** Si **no** hay `Pagos` asociados: **borrar** fila `Facturas` **o** solo marcar eliminación (elegir una política y documentarla aquí: _política elegida: ___ ).
- [ ] **4.6** Si hay **`Pagos`**: **no** borrar; setear **`alegra_bill_deleted` / `alegra_bill_deleted_at`**; opcional `history_facturas`.
- [ ] **4.7** Manejar idempotencia de `delete-bill` repetido (ya marcado → no-op).

---

## Fase 5 — Pagos e integración existente

- [ ] **5.1** Verificar que **no** se modificó `Pagos` ni firmas de vistas de pago usadas en producción.
- [ ] **5.2** Caso manual: radicado creado por webhook → registrar pago como hoy → interfaces/listados sin error.
- [ ] **5.3** No tocar **`alegra_integration`** saliente (builders, dashboard send) en esta fase — checklist de revisión de PR.

---

## Fase 6 — UI mínima

- [ ] **6.1** En lista o detalle de facturas (`accounting` templates o APIs JSON que alimentan DataTables), mostrar indicador si **`alegra_bill_deleted`** (o equivalente).
- [ ] **6.2** (Opcional) Filtro o badge “Anomalía Alegra”.

---

## Fase 7 — Suscripción en Alegra y pruebas E2E

- [ ] **7.1** Con ngrok activo, crear suscripción en Alegra apuntando a **`https://ibex-daring-molly.ngrok-free.app<path-webhook>`** para `new-bill`, `edit-bill`, `delete-bill`.
- [ ] **7.2** **E2E:** crear bill en Alegra → aparece `Facturas` con `alegra_bill_id` y campos de causación/radicado correctos.
- [ ] **7.3** **E2E:** editar bill → cambios reflejados localmente.
- [ ] **7.4** **E2E:** eliminar bill **sin** pagos → comportamiento acordado en 4.5.
- [ ] **7.5** **E2E:** eliminar bill **con** pago → fila permanece, marca visible, usuario puede operar según manual interno.

---

## Fase 8 — Cierre

- [ ] **8.1** Documentar en README o wiki interna: URL de **producción** del webhook, variables de entorno (secretos), y procedimiento si bill borrada en Alegra con pagos locales.
- [ ] **8.2** PR con migración + vista + tests; revisión de seguridad del endpoint.
- [ ] **8.3** Actualizar vista SQL **`info_facturas`** en entornos donde aplique (script aparte si no va en el repo).

---

## Checklist rápido “antes de merge”

- [ ] Migraciones aplican limpio desde cero en CI/local.
- [ ] Tests unitarios: `new-bill` idempotente, `delete-bill` con/sin pagos.
- [ ] Sin cambios no intencionados en `alegra_integration` saliente ni en `buildingcontrol`.
- [ ] `alegra_bill_id` único a nivel BD.

---

## Notas

- El hostname **ngrok** cambia si reinician el plan gratuito; habrá que **actualizar la suscripción** en Alegra o usar dominio reservado de ngrok.
- Si Alegra envía el header de advertencia de ngrok en el navegador, validar que el **webhook del servidor** llegue igual (suele ser distinto al navegador).
