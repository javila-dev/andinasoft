# Estado de cuenta — snapshot (antes de optimización ORM)

Fecha de referencia: trabajo en rama `main` post `informe_cartera_orm`.

## Puntos de entrada

| Ruta / acción | Archivo | Template PDF |
|---------------|---------|--------------|
| POST `impEstadodeCuenta` en detalle adj | `andinasoft/views.py` → `detalle_adjudicacion` | `pdf/statement_of_account.html` |
| GET `/andinasoftajx/estadodecuenta` | `ajax_print_estado_cuenta` | mismo |
| CRM acta | `crm/views.py` → URL ajax anterior | mismo |
| MCP tool `adjudicacion_estado_cuenta` | `mcp_server/tools/adjudicaciones.py` | mismo |
| Portal clientes | `client_portal/services/documents.py` | por proyecto en `STATEMENT_TEMPLATE_BY_PROJECT` |
| Fractal (ajax ventas) | `andinasoft/views.py` ~9645 | `pdf/Fractal/statement_of_account.html` |

## Flujo común (código duplicado en 4+ sitios)

1. `Adjudicacion.objects.using(proyecto).get(pk=adj)`
2. `PlanPagos` con `fecha <= hoy` ordenado → bucle:
   - `q.pendiente()` → `pagado()` → **1 aggregate** en `recaudos` por cuota
   - si pendiente > 0: `q.mora()` → `pendiente()` otra vez + **2–3 aggregates** más por cuota
3. `PlanPagos` futuras (hoy < fecha <= hoy+30)
4. `pdf_gen(template, context, filename)` → xhtml2pdf (pisa)

## Plantilla `statement_of_account.html` (carga extra en render)

Además del bucle Python, el PDF accede a propiedades de `adj` que disparan más SQL:

- `adj.titulares` → hasta **4×** `clientes.objects.get` por titular
- `adj.recaudo_detallado` → aggregates en `recaudos`
- `adj.saldos_por_cartera` → **~8 aggregates** en `saldos_adj`
- `adj.extra_info` → `Vista_Adjudicacion.get`
- `adj.tiempos_pagos` → **3 consultas** en `plan_pagos`
- `{% for quota in cuotas_futuras %}{% if quota.is_pending %}` → **2 queries por cuota futura** (`is_pending` + `pendiente` en template)

## Causa probable de timeout / OOM

- Adjudicación con **muchas cuotas** (ej. 120–360): bucle inicial ≈ **4–5 queries × N cuotas** (cientos–miles de round-trips).
- Render PDF: **decenas de queries** adicionales vía `adj.*` y cuotas futuras.
- `pdf_gen` arma HTML completo en memoria + pisa (pesado con tablas largas).

## Modelos clave

- `PlanPagos` → `plan_pagos`; métodos `pendiente()`, `mora()`, `pagado()`, `is_pending()`
- `Recaudos` → `recaudos` (detalle por `idcta` / `idadjudicacion`)
- `saldos_adj` → vista `saldos_cuotas` para resumen capital
- `Vista_Adjudicacion` → `info_adjudicaciones`

## Parámetros de mora (hardcoded en `PlanPagos.mora`)

- `tasamv = 2`, días de gracia 15, fórmula sobre `pendiente` y fechas de último pago en `recaudos`.

## Optimización aplicada (posterior)

- Módulo: `andinasoft/estado_cuenta_service.py` → `build_estado_cuenta_context(proyecto, adj_id, user)`.
- **1 consulta** de `recaudos` por adjudicación (índice por `idcta`); pendiente/mora en Python.
- **Adj para template** precalculado (titulares, recaudo_detallado, saldos_por_cartera, tiempos_pagos, logo) sin N+1 en render.
- Cuotas futuras con `is_pending` y `pendiente` precalculados (el template ya no llama métodos del modelo).
- Vistas unificadas: `detalle_adjudicacion`, `ajax_print_estado_cuenta`, Fractal ajax, `client_portal`, MCP.

## Rollback

Si la optimización falla, revertir `andinasoft/estado_cuenta_service.py` y restaurar bucles con `q.pendiente()` / `q.mora()` en las vistas listadas arriba.
