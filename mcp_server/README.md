# MCP Server — Andinasoft

Servidor MCP (Model Context Protocol) integrado en Django para el bot **Andi** (WhatsApp via n8n).
Expone herramientas para consultar inventario de lotes, movimientos bancarios, comisiones de asesores y adjudicaciones.

---

## Transporte

| Endpoint | Método | Descripción |
|---|---|---|
| `/mcp/` | POST / GET | **Streamable HTTP** — recomendado (MCP 2025) |
| `/mcp/sse` | GET | SSE legacy — deprecated |
| `/mcp/messages` | POST | Mensajes JSON-RPC legacy |
| `/mcp/health` | GET | Health check |

**Autenticación:** `Authorization: Token <api-key>` en todos los endpoints.

---

## Tools disponibles

### 1. `lotes_list`

Consulta el inventario de lotes/inmuebles de un proyecto.

| Parámetro | Tipo | Requerido | Descripción |
|---|---|---|---|
| `proyecto` | string | ✅ | Nombre del proyecto (ej: `"Fractal"`, `"Casas de Verano"`) |
| `estado` | string | — | `Libre` · `Bloqueado` · `Sin Liberar` · `Adjudicado` · `Reservado`. Default: `Libre` |
| `manzana` | string | — | Manzanas separadas por coma: `"1,2,3"` |
| `idinmueble` | string | — | ID exacto de un lote. Si se envía, ignora `estado` y `manzana` |

**Respuesta:**
```json
{
  "count": 12,
  "data": [
    {
      "idinmueble": "F-001",
      "estado": "Libre",
      "manzana": "1",
      "lote": "5",
      "area_privada": 120.5,
      "precio_m2": 850000.0,
      "valor_lote": 102000000,
      "motivo_bloqueo": null,
      "usuario_bloqueo": null,
      "relacion": null
    }
  ]
}
```

> `relacion` solo aparece en lotes `Adjudicado` o `Reservado` e incluye `tipo`, `referencia` y `cliente`.

---

### 2. `lotes_change_status`

Cambia el estado de un lote entre `Libre`, `Bloqueado` y `Sin Liberar`.

| Parámetro | Tipo | Requerido | Descripción |
|---|---|---|---|
| `proyecto` | string | ✅ | Nombre del proyecto |
| `idinmueble` | string | ✅ | ID del lote |
| `estado` | string | ✅ | Nuevo estado: `Libre` · `Bloqueado` · `Sin Liberar` |
| `motivo_bloqueo` | string | Cond. | Obligatorio si `estado = Bloqueado` |

> No se puede cambiar el estado de lotes `Adjudicado` o `Reservado`.

**Respuesta:**
```json
{
  "idinmueble": "F-001",
  "estado_anterior": "Libre",
  "estado_actual": "Bloqueado"
}
```

---

### 3. `bank_movements_list`

Consulta movimientos bancarios por cuenta y/o empresa en un rango de fechas.

| Parámetro | Tipo | Requerido | Descripción |
|---|---|---|---|
| `fecha_desde` | string | ✅ | Fecha inicio `YYYY-MM-DD` |
| `fecha_hasta` | string | ✅ | Fecha fin `YYYY-MM-DD` |
| `cuenta` | integer | Cond. | ID de la cuenta bancaria |
| `cuenta_numero` | string | Cond. | Número de la cuenta (alternativo a `cuenta`) |
| `empresa` | string | Cond. | NIT o nombre de la empresa |
| `estado` | string | — | `CONCILIADO` · `SIN CONCILIAR` |
| `usado_agente` | boolean | — | Filtrar por uso del agente |
| `valor_positivo` | boolean | — | Solo ingresos (valor > 0) |
| `descripcion` | string | — | Búsqueda difusa en descripción (~70% similitud) |
| `page` | integer | — | Página (default: `1`) |
| `page_size` | integer | — | Tamaño de página (default: `100`, máx: `500`) |

> Se requiere al menos uno de: `cuenta`, `cuenta_numero` o `empresa`.

**Respuesta:**
```json
{
  "filters": { "empresa": "900123456", "cuenta": 3, "fecha_desde": "2026-02-01", "fecha_hasta": "2026-02-24" },
  "pagination": { "page": 1, "page_size": 100, "total_pages": 1, "total_records": 45 },
  "movimientos": [
    {
      "id_mvto": 1821,
      "empresa": "900123456",
      "cuenta": 3,
      "cuenta_verbose": "1234-5678-9012",
      "fecha": "2026-02-10",
      "descripcion": "Transferencia recaudo cliente",
      "referencia": "REF-001",
      "valor": 5000000.0,
      "estado": "SIN CONCILIAR",
      "usado_agente": false,
      "match_pct": null
    }
  ]
}
```

---

### 4. `bank_movements_create`

Carga movimientos bancarios en lote (transacción atómica).

| Parámetro | Tipo | Requerido | Descripción |
|---|---|---|---|
| `movimientos` | array | ✅ | Lista de movimientos a crear |
| `cuenta` | integer | Cond. | ID de la cuenta |
| `cuenta_numero` | string | Cond. | Número de la cuenta (alternativo a `cuenta`) |
| `empresa` | integer | — | ID de la empresa (se infiere de la cuenta si está asociada) |

Cada objeto en `movimientos`:

| Campo | Tipo | Requerido | Descripción |
|---|---|---|---|
| `fecha` | string | ✅ | `YYYY-MM-DD` |
| `descripcion` | string | ✅ | Descripción del movimiento |
| `valor` | number | ✅ | Valor (distinto de cero) |
| `referencia` | string | — | Referencia bancaria |
| `estado` | string | — | `CONCILIADO` · `SIN CONCILIAR` (default: `SIN CONCILIAR`) |
| `pago_id` | integer | — | ID de pago asociado |
| `anticipo_id` | integer | — | ID de anticipo asociado |
| `transferencia_id` | integer | — | ID de transferencia asociada |
| `external_id` | string | — | ID externo para trazabilidad |

**Respuesta:**
```json
{
  "empresa": "900123456",
  "cuenta": 3,
  "total_movimientos": 2,
  "movimientos": [
    { "id_mvto": 1822, "external_id": "EXT-001" },
    { "id_mvto": 1823, "external_id": "EXT-002" }
  ]
}
```

---

### 5. `bank_movements_mark_used`

Marca o desmarca un movimiento como usado por el agente de conciliación.

| Parámetro | Tipo | Requerido | Descripción |
|---|---|---|---|
| `movement_id` | integer | ✅ | ID del movimiento |
| `usado_agente` | boolean | ✅ | `true` = marcar · `false` = desmarcar |
| `recibo_asociado_agente` | string | — | Número de recibo vinculado |
| `proyecto_asociado_agente` | string | — | Nombre del proyecto vinculado |

**Respuesta:**
```json
{
  "id_mvto": 1821,
  "usado_agente": true,
  "fecha_uso_agente": "2026-02-24 10:30:00",
  "recibo_asociado_agente": "R-2026-001",
  "proyecto_asociado_agente": "Casas de Verano",
  "mensaje": "Movimiento marcado como usado"
}
```

---

### 6. `bank_movements_for_receipt`

Busca movimientos bancarios candidatos para asociar a un recibo, en un rango de ±1 día respecto a la fecha de pago.

| Parámetro | Tipo | Requerido | Descripción |
|---|---|---|---|
| `proyecto` | string | ✅ | Nombre del proyecto |
| `fecha_pago` | string | ✅ | Fecha de pago `YYYY-MM-DD` |
| `recibo_asociado` | string | — | Número de recibo (para buscar movimiento ya vinculado) |

**Respuesta:**
```json
{
  "cuenta": 3,
  "cuenta_numero": "1234-5678-9012",
  "movimiento_asociado_id": 1821,
  "fecha_desde": "2026-02-09",
  "fecha_hasta": "2026-02-11",
  "total_movimientos": 3,
  "movimientos": [ ... ]
}
```

---

### 7. `comisiones_list`

Consulta comisiones liquidadas por proyecto, rango de fechas y/o asesor.

| Parámetro | Tipo | Requerido | Descripción |
|---|---|---|---|
| `proyecto` | string | ✅ | Nombre del proyecto |
| `fecha_desde` | string | — | Fecha inicio `YYYY-MM-DD`. Default: primer día del mes actual |
| `fecha_hasta` | string | — | Fecha fin `YYYY-MM-DD`. Default: hoy |
| `asesor` | string | — | Nombre o cédula del asesor. **Omitir** cuando el usuario pregunte por sus propias comisiones — el sistema las detecta automáticamente desde el perfil del usuario autenticado |

**Búsqueda de asesor (3 etapas):**
1. Cédula exacta
2. Nombre completo (`icontains`)
3. Cada palabra del nombre por separado (AND)

**Respuesta:**
```json
{
  "proyecto": "Casas de Verano",
  "fecha_desde": "2026-02-01",
  "fecha_hasta": "2026-02-24",
  "asesor_buscado": "Sebastian Briceño",
  "asesores_encontrados": [
    { "cedula": "1037588511", "nombre": "JUAN SEBASTIAN BRICEÑO GOMEZ" }
  ],
  "total_registros": 3,
  "resumen_por_fecha": [
    { "fecha": "2026-02-10", "comision": 1500000.0, "retefuente": 150000.0, "pagoneto": 1350000.0, "registros": 1 }
  ],
  "totales": {
    "comision": 4500000.0,
    "retefuente": 450000.0,
    "pagoneto": 4050000.0
  },
  "detalle": [
    {
      "id_pago": 501,
      "fecha": "2026-02-10",
      "asesor": "JUAN SEBASTIAN BRICEÑO GOMEZ",
      "cedula": "1037588511",
      "idadjudicacion": "CV-2025-001",
      "comision": 1500000.0,
      "retefuente": 150000.0,
      "pagoneto": 1350000.0
    }
  ]
}
```

---

### 8. `adjudicacion_estado_cuenta`

Genera el PDF de estado de cuenta de una adjudicación y retorna su URL pública + resumen financiero.

| Parámetro | Tipo | Requerido | Descripción |
|---|---|---|---|
| `proyecto` | string | ✅ | Nombre del proyecto |
| `idadjudicacion` | string | Cond. | ID exacto de la adjudicación (ej: `"ADJ152"`) |
| `cliente` | string | Cond. | Nombre parcial o cédula del cliente titular (ej: `"Juan García"` o `"1037588511"`) |

> Se requiere al menos uno de `idadjudicacion` o `cliente`. Si el nombre devuelve múltiples adjudicaciones, el tool las lista para que el agente pida confirmación al usuario.

**Búsqueda normalizada (4 etapas para nombre/cédula):**
1. ID exacto de adjudicación
2. Nombre completo (`icontains`) en `clientes.nombrecompleto` → cruza cédulas con `idtercero1`–`idtercero4`
3. `nombres` o `apellidos` por separado → mismo cruce
4. Cada palabra del nombre (AND) → mismo cruce
5. Fuzzy Levenshtein ≥ 0.82 por palabra (maneja typos: `"anderson"` → `"ANDERSSON"`) → mismo cruce
6. Si ninguna etapa encuentra por nombre, trata el valor como cédula directa

**Respuesta:**
```json
{
  "idadjudicacion": "ADJ152",
  "proyecto": "Carmelo Reservado",
  "pdf_url": "https://app.somosandina.co/media/tmp/Estado_de_cuenta_ADJ152_Carmelo%20Reservado.pdf",
  "resumen": {
    "titulares": ["JUAN GARCIA LOPEZ"],
    "inmueble": "CR-001",
    "valor_contrato": 120000000.0,
    "cuotas_vencidas_count": 2,
    "total_capital_vencido": 4500000.0,
    "total_mora": 90000.0,
    "total_a_pagar": 4590000.0,
    "cuotas_proximas_count": 1,
    "total_proximo_30dias": 2250000.0
  }
}
```

> El PDF se genera en `MEDIA_ROOT/tmp/` usando la misma lógica que `ajax_print_estado_cuenta`. La URL usa `DIR_DOWNLOADS` (absoluta en producción) con el filename URL-encoded.

---

### 9. `adjudicacion_documentos`

Lista los documentos cargados para una adjudicación (cédulas, contratos, soportes, etc.) con URL pública de cada archivo.

| Parámetro | Tipo | Requerido | Descripción |
|---|---|---|---|
| `proyecto` | string | ✅ | Nombre del proyecto |
| `idadjudicacion` | string | Cond. | ID exacto de la adjudicación |
| `cliente` | string | Cond. | Nombre parcial o cédula del cliente titular |

> Misma lógica de búsqueda normalizada que `adjudicacion_estado_cuenta`.

**Respuesta:**
```json
{
  "idadjudicacion": "ADJ152",
  "proyecto": "Carmelo Reservado",
  "total_documentos": 2,
  "documentos": [
    {
      "descripcion": "cedula_Juan_2025-01-15",
      "fecha_carga": "2025-01-15",
      "usuario_carga": "admin",
      "url": "/media/docs_andinasoft/doc_contratos/Carmelo%20Reservado/ADJ152/cedula_Juan_2025-01-15.pdf"
    }
  ]
}
```

> Las URLs tienen cada segmento URL-encoded (espacios → `%20`). Los archivos están en `MEDIA_ROOT/docs_andinasoft/doc_contratos/{proyecto}/{adj}/`.

---

## Proyectos disponibles

| Alias Django | Proyecto |
|---|---|
| `Fractal` | Fractal |
| `Casas de Verano` | Casas de Verano |
| `Sandville Beach` | Sandville Beach |
| `Carmelo Reservado` | Carmelo Reservado |
| `Alttum` | Alttum |
| `Tesoro Escondido` | Tesoro Escondido |
| `Vegas de Venecia` | Vegas de Venecia |
| `Perla del Mar` | Perla del Mar |
| `Sotavento` | Sotavento |

La resolución de proyectos es tolerante a coincidencias parciales. Si el nombre enviado coincide con exactamente un proyecto, se usa ese. Si hay ambigüedad, el tool devuelve un error con las opciones.

---

## Autenticación de usuario

El servidor autentica cada request via token (`Authorization: Token <api-key>`).
El usuario Django autenticado se pasa internamente a cada tool para:

- Verificar acceso al proyecto (`Usuarios_Proyectos`)
- Detectar automáticamente el asesor en `comisiones_list` via `Profiles.identificacion`

---

## Logs

Los logs del servidor se emiten bajo el namespace `mcp_server` a nivel `INFO`.
Útil para depuración:

```bash
docker logs <container> 2>&1 | grep "\[DEBUG"
```
