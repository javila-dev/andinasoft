  API Accounting
  ==============

  ## Movimientos bancarios

  ### POST /accounting/api/bank-movements
  - **Descripción:** carga movimientos bancarios en egresos de tesorería (conciliables) en lote.
  - **Auth/perm:** sesión + `accounting.add_egresos_banco`
  - **Requiere:** `cuenta` (ID) o `cuenta_numero` (número bancario normalizado) para asociar la cuenta; `empresa` es opcional si la cuenta ya tiene empresa asociada.
  - **Body JSON:**  
    ```json
    {
      "empresa": <id>,
      "cuenta": <id>,            // o usa "cuenta_numero": "1234-567890"
      "movimientos": [
        {
          "fecha": "YYYY-MM-DD",
          "descripcion": "texto",
          "valor": 1234.56,
          "referencia": "opcional",
          "estado": "CONCILIADO|SIN CONCILIAR",
          "pago_id": 1,
          "anticipo_id": 2,
          "transferencia_id": 3,
          "external_id": "opcional"
        }
      ]
    }
    ```
  - **Response 201 (schema):**
    ```json
    {
      "empresa": <id>,
      "cuenta": <id>,
      "total_movimientos": <int>,
      "movimientos": [
        {
          "id_mvto": <int>,
          "external_id": "string|null"
        }
      ]
    }
    ```
  - **Ejemplo curl:**
    ```bash
    curl -X POST https://tu-dominio/accounting/api/bank-movements \
      -H "Authorization: Token <API_KEY>" \
      -H "Content-Type: application/json" \
      -d '{
        "empresa": 3,
        "cuenta_numero": "1234-567-890",
        "movimientos": [
          {
            "fecha": "2024-05-25",
            "descripcion": "Pago proveedores",
            "valor": 1543200.75,
            "referencia": "BATCH-982",
            "estado": "SIN CONCILIAR"
          }
        ]
      }'
    ```

  ### GET /accounting/api/bank-movements/list
  - **Descripción:** consulta movimientos bancarios por cuenta (ID o número) y/o empresa en un rango de fechas, con filtros opcionales.
  - **Auth/perm:** sesión + `accounting.view_egresos_banco`
  - **Query params:** `cuenta` (ID), `cuenta_numero` (número libre de espacios/puntos/guiones) o `empresa` (NIT o nombre de empresa, al menos uno), `fecha_desde`*, `fecha_hasta`*, `estado`, `usado_agente` (true/false/1/0), `valor_positivo` (true/false/1/0), `descripcion` (búsqueda difusa ~70% similitud, insensible a mayúsculas y diacríticas), `page`, `page_size (<=500)`
  - **Response 200 (schema):**
    ```json
    {
      "filters": {
        "empresa": <id|null>,
        "cuenta": <id|null>,
        "fecha_desde": "YYYY-MM-DD",
        "fecha_hasta": "YYYY-MM-DD",
        "estado": "CONCILIADO|SIN CONCILIAR|null",
        "usado_agente": "true|false|null",
        "valor_positivo": "true|false|null",
        "descripcion": "string|null"
      },
      "pagination": {
        "page": <int>,
        "page_size": <int>,
        "total_pages": <int>,
        "total_records": <int>
      },
      "movimientos": [
        {
          "id_mvto": <int>,
          "empresa": <id>,
          "cuenta": <id>,
          "cuenta_verbose": "string",  // Descripción legible de la cuenta (ej: "Bancolombia 1234567890")
          "fecha": "YYYY-MM-DD",
          "descripcion": "string",
          "referencia": "string|null",
          "valor": <float>,
          "estado": "CONCILIADO|SIN CONCILIAR",
          "conciliacion_id": <int|null>,
          "pago_id": <int|null>,
          "anticipo_id": <int|null>,
          "transferencia_id": <int|null>,
          "usado_agente": <bool>,
          "fecha_uso_agente": "YYYY-MM-DD HH:MM:SS|null",
          "recibo_asociado_agente": "string|null",
          "proyecto_asociado_agente": "string|null",
          "info_relacionada": {  // Solo presente cuando valor <= 0 (egresos) y tiene asociación
            "tipo": "pago|anticipo|transferencia",
            // Si tipo es "pago":
            "radicado": {
              "nro": <int>,
              "descripcion": "string",
              "tercero": "string",
              "valor": <int>,
              "soporte_radicado_url": "string|null"
            },
            "pago": {
              "valor": <int>,
              "fecha_pago": "YYYY-MM-DD",
              "soporte_pago_url": "string|null"
            },
            // Si tipo es "anticipo":
            "anticipo": {
              "descripcion": "string",
              "tercero": "string",
              "valor": <int>,
              "fecha_pago": "YYYY-MM-DD",
              "tipo_anticipo": "string|null",
              "soporte_pago_url": "string|null"
            },
            // Si tipo es "transferencia":
            "transferencia": {
              "fecha": "YYYY-MM-DD",
              "empresa_sale": "string",
              "cuenta_sale": "string",
              "empresa_entra": "string",
              "cuenta_entra": "string",
              "valor": <int>,
              "soporte_pago_url": "string|null"
            }
          }
        }
      ]
    }
    ```
  - **Errores comunes (retornan HTTP 200 con movimientos vacíos):**
    - ID de cuenta inválido (no numérico):
      ```json
      {
        "detail": "El ID de cuenta \"abc\" no es válido. Debe ser un número entero.",
        "cuenta_enviada": "abc",
        "filters": {},
        "pagination": {"page": 1, "page_size": 0, "total_pages": 0, "total_records": 0},
        "movimientos": []
      }
      ```
    - Cuenta no encontrada:
      ```json
      {
        "detail": "No se encontró ninguna cuenta bancaria con el ID 999.",
        "cuenta_enviada": "999",
        "filters": {},
        "pagination": {"page": 1, "page_size": 0, "total_pages": 0, "total_records": 0},
        "movimientos": []
      }
      ```
    - Cuenta por número no encontrada:
      ```json
      {
        "detail": "No se encontró ninguna cuenta bancaria con el número \"1234567890\".",
        "cuenta_enviada": "1234567890",
        "sugerencia": "Verifica que el número de cuenta sea correcto y esté registrado en el sistema.",
        "filters": {},
        "pagination": {"page": 1, "page_size": 0, "total_pages": 0, "total_records": 0},
        "movimientos": []
      }
      ```
    - Empresa no encontrada:
      ```json
      {
        "detail": "No se encontró ninguna empresa con el NIT o nombre \"999999999\".",
        "empresa_enviada": "999999999",
        "sugerencia": "Verifica que el NIT o nombre de la empresa sea correcto.",
        "filters": {},
        "pagination": {"page": 1, "page_size": 0, "total_pages": 0, "total_records": 0},
        "movimientos": []
      }
      ```
    - Cuenta no pertenece a la empresa:
      ```json
      {
        "detail": "La cuenta bancaria 1234-567890 no pertenece a la empresa Mi Empresa.",
        "cuenta": 5,
        "cuenta_numero": "1234-567890",
        "empresa_cuenta": "Otra Empresa",
        "empresa_solicitada": "Mi Empresa",
        "filters": {},
        "pagination": {"page": 1, "page_size": 0, "total_pages": 0, "total_records": 0},
        "movimientos": []
      }
      ```
    - **Nota importante**: Todos estos casos retornan HTTP 200 con `movimientos: []` para facilitar el manejo en agentes de IA. El campo `detail` indica el error específico.
  - **Ejemplos curl:**
    ```bash
    # Búsqueda básica por cuenta
    curl "https://tu-dominio/accounting/api/bank-movements/list?cuenta_numero=1234567890&fecha_desde=2024-05-01&fecha_hasta=2024-05-31&usado_agente=false" \
      -H "Authorization: Token <API_KEY>"

    # Búsqueda por empresa con filtro de descripción (insensible a mayúsculas y acentos)
    curl "https://tu-dominio/accounting/api/bank-movements/list?empresa=900123456&fecha_desde=2024-05-01&fecha_hasta=2024-05-31&descripcion=transferencia" \
      -H "Authorization: Token <API_KEY>"

    # Búsqueda con múltiples palabras - encuentra si TODAS las palabras están presentes
    curl "https://tu-dominio/accounting/api/bank-movements/list?empresa=900123456&fecha_desde=2024-05-01&fecha_hasta=2024-05-31&descripcion=jorge%20avila" \
      -H "Authorization: Token <API_KEY>"

    # El parámetro 'descripcion' usa búsqueda difusa (~70% similitud):
    # "transferencia" encontrará: "Transferencia", "TRANSFERENCIA", "Transferéncia", "transferenci", etc.
    # "jorge avila" encontrará: "Jorge Avila", "Jorge Mario Avila", "Pago a Avila Jorge", etc.
    # "nicolas pulgarin" encontrará: "nicolas pulgari", "nicolas pulgarín", "Nicolás Pulgarino", etc.
    # NO encontrará: "Jorge Perez" (falta "avila"), "Nicolas Rodriguez" (falta "pulgarin")
    ```
  - **Nota sobre búsqueda por `descripcion`:**
    - Usa **fuzzy matching** con ~70% de similitud (algoritmo de Levenshtein)
    - Tolera errores de tipeo, truncamientos y variaciones ortográficas
    - Ignora mayúsculas y diacríticas (acentos, tildes)
    - Busca todas las palabras (deben estar todas presentes con ~70% similitud)
    - Ejemplos de coincidencias:
      - "pulgarin" → "pulgari" (87.5% similitud) ✓
      - "rodriguez" → "rodrigez" (88.9% similitud) ✓
      - "nicolas" → "nicola" (85.7% similitud) ✓
      - "martinez" → "martines" (87.5% similitud) ✓
  - **Nota sobre `info_relacionada`:**
    - Este campo solo aparece cuando `valor <= 0` (egresos/salidas de dinero) y el movimiento tiene asociado un pago, anticipo o transferencia.
    - Contiene información detallada del documento asociado (radicado, factura) y los soportes digitales.
    - Los campos `soporte_radicado_url` y `soporte_pago_url` contienen las URLs relativas a los archivos cargados en el sistema.
    - Para movimientos con `valor > 0` (ingresos), este campo no está presente.

  ### PATCH /accounting/api/bank-movements/<id_mvto>/mark-used
  - **Descripción:** marca o desmarca un movimiento bancario (egreso banco) como usado por el agente de conciliación automática.
  - **Auth/perm:** sesión + `accounting.change_egresos_banco`
  - **Parámetros URL:** `<id_mvto>` - ID del movimiento bancario
  - **Body JSON:**
    ```json
    {
      "usado_agente": true|false,
      "recibo_asociado_agente": "4587",  // opcional
      "proyecto_asociado_agente": "Proyecto XYZ"  // opcional
    }
    ```
  - **Response 200:**
    ```json
    {
      "id_mvto": 123,
      "usado_agente": true,
      "fecha_uso_agente": "2025-12-15 10:30:45",
      "recibo_asociado_agente": "4587",
      "proyecto_asociado_agente": "Proyecto XYZ",
      "mensaje": "Movimiento marcado como usado"
    }
    ```
  - **Response 400:**
    ```json
    {
      "detail": "Debes enviar 'usado_agente'",
      "error_code": "MISSING_USADO"
    }
    ```
  - **Response 404:**
    ```json
    {
      "detail": "Movimiento no encontrado",
      "error_code": "NOT_FOUND"
    }
    ```
  - **Ejemplo curl:**
    ```bash
    curl -X PATCH "https://tu-dominio/accounting/api/bank-movements/123/mark-used" \
      -H "Authorization: Token <API_KEY>" \
      -H "Content-Type: application/json" \
      -d '{
        "usado_agente": true,
        "recibo_asociado_agente": "4587",
        "proyecto_asociado_agente": "Proyecto XYZ"
      }'
    ```

  ### GET /accounting/api/bank-movements/for-receipt
  - **Descripción:** obtiene movimientos bancarios relacionados con una solicitud de recibo. Si la solicitud tiene recibo asociado, busca el movimiento por recibo+proyecto y usa esa cuenta bancaria. Si no, busca la cuenta más común del proyecto. Retorna movimientos con valor positivo en rango ±1 día de la fecha de pago.
  - **Auth/perm:** sesión + `accounting.view_egresos_banco`
  - **Query params:** `proyecto` (nombre del proyecto)*, `fecha_pago` (YYYY-MM-DD)*, `recibo_asociado` (número de recibo, opcional)
  - **Response 200 (schema):**
    ```json
    {
      "cuenta": <id>,
      "cuenta_numero": "string",
      "movimiento_asociado_id": <int|null>,
      "fecha_desde": "YYYY-MM-DD",
      "fecha_hasta": "YYYY-MM-DD",
      "total_movimientos": <int>,
      "movimientos": [
        {
          "id_mvto": <int>,
          "empresa": <id>,
          "cuenta": <id>,
          "fecha": "YYYY-MM-DD",
          "descripcion": "string",
          "referencia": "string|null",
          "valor": <float>,
          "estado": "CONCILIADO|SIN CONCILIAR",
          "conciliacion_id": <int|null>,
          "pago_id": <int|null>,
          "anticipo_id": <int|null>,
          "transferencia_id": <int|null>,
          "usado_agente": <bool>,
          "fecha_uso_agente": "YYYY-MM-DD HH:MM:SS|null",
          "recibo_asociado_agente": "string|null",
          "proyecto_asociado_agente": "string|null"
        }
      ]
    }
    ```
  - **Ejemplo curl:**
    ```bash
    curl "https://tu-dominio/accounting/api/bank-movements/for-receipt?proyecto=Carmelo%20Reservado&fecha_pago=2025-11-17&recibo_asociado=4587" \
      -H "Authorization: Token <API_KEY>"
    ```

  ## Inventario de lotes

  ### GET /accounting/api/lotes
  - **Descripción:** consulta lotes por estado, con filtro opcional por lista de manzanas o por ID de inmueble. Si no se envía `estado` ni `idinmueble`, usa `Libre`.
  - **Auth/perm:** token API + acceso al proyecto (asignado al usuario).
  - **Query params:** `proyecto`* (nombre exacto del proyecto), `estado` (Libre|Bloqueado|Sin Liberar, case-insensitive), `manzana` (lista separada por comas), `idinmueble` (ID exacto del lote).
  - **Nota:** parámetros vacíos se ignoran. `proyecto` es obligatorio.
  - **Nota:** `relacion` solo se completa cuando se envía `idinmueble` y el lote está en estado `Adjudicado` o `Reservado`.
  - **Response 200 (schema):**
    ```json
    {
      "count": <int>,
      "data": [
        {
          "idinmueble": "string",
          "estado": "string|null",
          "manzana": "string|null",
          "lote": "string|null",
          "area_privada": <float|null>,
          "precio_m2": <float|null>,
          "valor_lote": <int>,
          "motivo_bloqueo": "string|null",
          "usuario_bloqueo": "string|null",
          "relacion": {
            "tipo": "adjudicacion|reserva",
            "referencia": "string|int",
            "cliente": "string|null"
          }
        }
      ]
    }
    ```
  - **Errores comunes:**
    - 400: falta `proyecto`
    - 400: estado inválido
    - 401: token inválido o no autenticado
    - 403: sin acceso al proyecto
    - 404: proyecto no encontrado
    - 500: error inesperado
  - **Ejemplo curl:**
    ```bash
    curl "https://tu-dominio/accounting/api/lotes?proyecto=Carmelo%20Reservado&manzana=1,2,3" \
      -H "Authorization: Token <API_KEY>"
    ```

  ### POST /accounting/api/lotes/estado
  - **Descripción:** cambia el estado de un lote entre `Libre`, `Bloqueado` y `Sin Liberar`.
  - **Auth/perm:** token API + acceso al proyecto (asignado al usuario).
  - **Body JSON:**
    ```json
    {
      "proyecto": "Nombre del proyecto",
      "idinmueble": "ID del lote",
      "estado": "Libre|Bloqueado|Sin Liberar",
      "motivo_bloqueo": "Requerido si estado=Bloqueado"
    }
    ```
  - **Response 200 (schema):**
    ```json
    {
      "idinmueble": "string",
      "estado_anterior": "string",
      "estado_actual": "Libre"
    }
    ```
  - **Errores comunes:**
    - 400: JSON inválido, falta `proyecto`, `idinmueble` o `estado`, o `motivo_bloqueo` al bloquear
    - 401: token inválido o no autenticado
    - 403: sin acceso al proyecto
    - 404: proyecto o lote no encontrado
    - 409: el lote ya está en el estado solicitado
    - 500: error inesperado
  - **Ejemplo curl:**
    ```bash
    curl -X POST "https://tu-dominio/accounting/api/lotes/estado" \
      -H "Authorization: Token <API_KEY>" \
      -H "Content-Type: application/json" \
      -d '{"proyecto": "Carmelo Reservado", "idinmueble": "INM123", "estado": "Libre"}'
    ```
    ```bash
    curl -X POST "https://tu-dominio/accounting/api/lotes/estado" \
      -H "Authorization: Token <API_KEY>" \
      -H "Content-Type: application/json" \
      -d '{"proyecto": "Carmelo Reservado", "idinmueble": "INM123", "estado": "Bloqueado", "motivo_bloqueo": "Reserva interna"}'
    ```

  ## Recaudos y recibos

  ### GET /finance/api/pending-receipts
  - **Descripción:** lista solicitudes de recibos internos aún sin recibo asociado (pendientes de recaudo). Excluye automáticamente las solicitudes marcadas con `requiere_revision_manual=True`.
  - **Auth/perm:** sesión + `finance.view_recibos_internos` (usuarios sin `andinasoft.add_recaudos_general` solo ven sus solicitudes).
  - **Query params (opcionales):** `fecha_desde`, `fecha_hasta` (YYYY-MM-DD, default último mes), `proyecto` (id o "todos"), `cliente`, `abono_capital` (`true|1`), `fecha_pago_hasta` (YYYY-MM-DD, filtra fecha_pago <= valor).
  - **Response 200 (schema):**
    ```json
    {
      "filters": {
        "fecha_desde": "YYYY-MM-DD",
        "fecha_hasta": "YYYY-MM-DD",
        "proyecto": "id|null",
        "cliente": "string|null",
        "solo_abonos": true|false,
        "fecha_pago_hasta": "YYYY-MM-DD|null"
      },
      "total": <int>,
      "results": [
        {
          "id": <int>,
          "proyecto": <id>,
          "proyecto_nombre": "string",
          "cliente": "string",
          "valor": <int>,
          "condonacion": <float>,
          "abono_capital": true|false,
          "fecha_solicitud": "YYYY-MM-DD",
          "fecha_pago": "YYYY-MM-DD",
          "usuario_solicita": "string",
          "soporte_url": "url|null",
          "requiere_revision_manual": true|false
        }
      ]
    }
    ```
  - **Ejemplo curl:**
    ```bash
    curl "https://tu-dominio/finance/api/pending-receipts?proyecto=todos&fecha_desde=2024-05-01&fecha_hasta=2024-05-31&fecha_pago_hasta=2024-05-15" \
      -H "Authorization: Token <API_KEY>"
    ```

  ### PATCH /finance/api/receipt-request/<id>/status
  - **Descripción:** cambia el estado de una solicitud de recibo interno o marca/desmarca la solicitud para revisión manual. Permite anular solicitudes pendientes, reactivar solicitudes anuladas, o marcar solicitudes que requieren revisión manual antes de procesar.
  - **Auth/perm:** token API + sesión + uno de los siguientes permisos según la operación:
    - Para **anular**: `finance.delete_recibos_internos` o `andinasoft.add_recaudos_general`
    - Para **reactivar**: `finance.change_recibos_internos` o `andinasoft.add_recaudos_general`
    - Para **marcar revisión**: `finance.change_recibos_internos` o `andinasoft.add_recaudos_general`
    - Usuarios sin permiso global (`andinasoft.add_recaudos_general`) solo pueden modificar sus propias solicitudes
  - **Parámetros URL:** `<id>` - ID de la solicitud de recibo
  - **Body JSON (opción 1 - cambiar estado):**
    ```json
    {
      "estado": "anulado|activo"
    }
    ```
  - **Body JSON (opción 2 - marcar para revisión manual):**
    ```json
    {
      "requiere_revision_manual": true|false
    }
    ```
  - **Body JSON (opción 3 - combinar ambos):**
    ```json
    {
      "estado": "anulado|activo",
      "requiere_revision_manual": true|false
    }
    ```
  - **Estados válidos:**
    - `"anulado"`: Anula una solicitud pendiente (marca `anulado=True`)
    - `"activo"`: Reactiva una solicitud anulada (marca `anulado=False`)
  - **Flag de revisión manual:**
    - `requiere_revision_manual: true`: Marca la solicitud para que requiera revisión manual antes de procesar. Útil para resaltar en el frontend solicitudes que necesitan atención especial.
    - `requiere_revision_manual: false`: Desmarca la solicitud como lista para procesar normalmente.
  - **Restricciones:**
    - No se puede anular una solicitud que ya tiene `recibo_asociado`
    - No se puede reactivar una solicitud que tiene `recibo_asociado`
    - No se puede marcar para revisión una solicitud que ya tiene `recibo_asociado`
    - No se puede marcar para revisión una solicitud anulada
    - Solo el usuario que creó la solicitud o usuarios con permisos globales pueden modificar el estado
  - **Response 200 (éxito - cambio de estado):**
    ```json
    {
      "id": 123,
      "estado": "anulado|activo",
      "mensaje": "Solicitud anulada exitosamente",
      "proyecto": "Tesoro Escondido",
      "cliente": "12345",
      "valor": 1500000,
      "fecha_solicitud": "2024-06-01",
      "fecha_pago": "2024-06-01"
    }
    ```
  - **Response 200 (éxito - marcado para revisión):**
    ```json
    {
      "id": 123,
      "requiere_revision_manual": true,
      "mensaje": "Solicitud marcada para revisión manual",
      "proyecto": "Tesoro Escondido",
      "cliente": "12345",
      "valor": 1500000,
      "fecha_solicitud": "2024-06-01",
      "fecha_pago": "2024-06-01"
    }
    ```
  - **Response 400 (errores de validación):**
    ```json
    {
      "detail": "No se puede anular una solicitud que ya tiene recibo asociado",
      "error_code": "HAS_RECEIPT",
      "recibo_asociado": "4587"
    }
    ```
  - **Response 403 (sin permisos):**
    ```json
    {
      "detail": "No tienes permiso para anular solicitudes",
      "error_code": "PERMISSION_DENIED"
    }
    ```
  - **Response 404 (no encontrada):**
    ```json
    {
      "detail": "Solicitud de recibo no encontrada",
      "error_code": "NOT_FOUND"
    }
    ```
  - **Códigos de error:**
    - `INVALID_JSON`: El body no es JSON válido
    - `MISSING_ESTADO`: Falta el campo "estado" en el body (cuando no se proporciona `requiere_revision_manual`)
    - `INVALID_ESTADO`: El estado proporcionado no es válido
    - `PERMISSION_DENIED`: Usuario sin permisos suficientes
    - `NOT_FOUND`: Solicitud no existe
    - `HAS_RECEIPT`: La solicitud ya tiene recibo asociado
    - `IS_ANULADO`: La solicitud está anulada (no se puede marcar para revisión)
    - `ALREADY_ANULADO`: La solicitud ya está anulada
    - `ALREADY_ACTIVE`: La solicitud ya está activa
  - **Ejemplos curl:**
    ```bash
    # Anular una solicitud
    curl -X PATCH "https://tu-dominio/finance/api/receipt-request/123/status" \
      -H "Authorization: Token <API_KEY>" \
      -H "Content-Type: application/json" \
      -d '{"estado": "anulado"}'

    # Reactivar una solicitud anulada
    curl -X PATCH "https://tu-dominio/finance/api/receipt-request/123/status" \
      -H "Authorization: Token <API_KEY>" \
      -H "Content-Type: application/json" \
      -d '{"estado": "activo"}'

    # Marcar una solicitud para revisión manual
    curl -X PATCH "https://tu-dominio/finance/api/receipt-request/123/status" \
      -H "Authorization: Token <API_KEY>" \
      -H "Content-Type: application/json" \
      -d '{"requiere_revision_manual": true}'

    # Desmarcar una solicitud de revisión manual
    curl -X PATCH "https://tu-dominio/finance/api/receipt-request/123/status" \
      -H "Authorization: Token <API_KEY>" \
      -H "Content-Type: application/json" \
      -d '{"requiere_revision_manual": false}'
    ```
  - **Casos de uso:**
    - Anular una solicitud creada por error antes de que se genere el recibo
    - Corregir solicitudes anuladas incorrectamente
    - Marcar solicitudes que requieren verificación adicional por montos elevados o casos especiales
    - Destacar en el frontend solicitudes que necesitan atención especial del equipo de tesorería
    - Gestión del ciclo de vida de solicitudes pendientes

  ### POST /api/receipts/validate
  - **Descripción:** replica la validación del formulario de `nuevo_recaudo`, devolviendo alertas y el detalle de cuotas que se aplicarán antes de crear el recibo.
  - **Auth/perm:** token API + sesión + `andinasoft.add_recaudos_general`.
  - **Body JSON:**
    ```json
    {
      "proyecto": "Tesoro Escondido",
      "adj": "12345",
      "fecha": "2024-06-01",
      "fecha_pago": "2024-06-01",
      "valor": "1500000",
      "forma_pago": "Transferencia",
      "abono_capital": "true",
      "condonacion_mora": "1",
      "concepto": "Abono plan de pagos",
      "numsolicitud": "789",
      "form_token": "opcional, úsalo para la creación"
    }
    ```
  - **Notas:** `abono_capital` acepta `"true"` o `"false"` (se convierten internamente). `condonacion_mora` acepta `1` o `0`; cuando vale `1`, el porcentaje de condonación se fija automáticamente en 100%.
  - **Ejemplo curl:**
    ```bash
    curl -X POST "https://tu-dominio/api/receipts/validate" \
      -H "Authorization: Token <API_KEY>" \
      -H "Content-Type: application/json" \
      -d '{
            "proyecto": "Tesoro Escondido",
            "adj": "12345",
            "fecha": "2024-06-01",
            "fecha_pago": "2024-06-01",
            "valor": "1500000",
            "forma_pago": "Transferencia",
            "abono_capital": "true",
            "condonacion_mora": "1",
            "concepto": "Abono plan de pagos",
            "numsolicitud": "789"
          }'
    ```
  - **Response 200:**
    ```json
    {
      "alerts": [
        {"code": "MANY_FUTURE_INSTALLMENTS", "message": "Este pago se esta aplicando a muchas cuotas futuras, revisalo!", "severity": "warning"}
      ],
      "form_token": "c9d02d2cf8...",
      "verif_valor": true,
      "count_cuota": 3,
      "detalle_recaudo": [
        {
          "fecha": "2024-06-01",
          "cuota_id": "FN120123",
          "capital": 1200000,
          "interes_corriente": 200000,
          "dias_mora": 0,
          "valor_mora": 0,
          "total_aplicado": 1400000
        }
      ],
      "totales": {
        "capital": 1200000,
        "interes_corriente": 200000,
        "mora": 0,
        "total": 1400000
      },
      "valor_recibo": "1,400,000",
      "abono_capital": true,
      "condonacion": "No",
      "procentaje_condonado": "0"
    }
    ```
  - **Códigos de alerta posibles:**
    - `AMOUNT_EXCEEDS_PLAN` (error): El valor a pagar excede el saldo pendiente del plan de pagos.
    - `MANY_FUTURE_INSTALLMENTS` (warning): El pago se está aplicando a más de 2 cuotas futuras (sin mora).
    - `CAPITAL_PAYMENT_WITH_PENDING_CI` (error): Se está intentando hacer un abono a capital cuando aún hay cuotas iniciales (CI) pendientes de pago.
  - **Errores comunes:** `400` (JSON inválido o sin `proyecto/adj`), `404` cuando la adjudicación no existe en el proyecto indicado.

  ### POST /api/receipts/create
  - **Descripción:** crea el recibo y enlaza la solicitud existente usando la misma lógica de `nuevo_recaudo`. Requiere el `form_token` retornado por `validate` para garantizar idempotencia.
  - **Auth/perm:** token API + sesión + `andinasoft.add_recaudos_general`.
  - **Body JSON:** igual al endpoint de validación, incluyendo `form_token`.
  - **Mapeo automático de forma_pago:** el campo `forma_pago` acepta el nombre de la forma de pago (ej: "Transferencia", "Wompi", "Efectivo") y el sistema automáticamente lo mapea a la forma de pago configurada en el proyecto. La búsqueda es case-insensitive y soporta coincidencias parciales. Si no encuentra la forma de pago, devuelve un error 400 sugiriendo usar `/api/formas-pago` para ver las opciones disponibles.
  - **Response 201:**
    ```json
    {
      "alerts": [],
      "nro_recibo": "4587",
      "pdf_url": "/downloads/Recibo_caja_4587_Tesoro Escondido.pdf",
      "ruta_recibo": "/tmp/export/Recibo_caja_4587_Tesoro Escondido.pdf",
      "mensaje": "Descarga el recibo aquí",
      "redirect": "/tesoreria/adjudicaciones/Tesoro Escondido",
      "form_token": "nuevo_token"
    }
    ```
  - **Errores comunes:** `400` con `alerts` cuando la solicitud ya tiene recibo, el token ya se usó o hay cuotas CI pendientes en un abono a capital.
  - **Ejemplo curl:**
    ```bash
    curl -X POST "https://tu-dominio/api/receipts/create" \
      -H "Authorization: Token <API_KEY>" \
      -H "Content-Type: application/json" \
      -d '{
            "proyecto": "Tesoro Escondido",
            "adj": "12345",
            "fecha": "2024-06-01",
            "fecha_pago": "2024-06-01",
            "valor": "1500000",
            "forma_pago": "Transferencia",
            "abono_capital": "true",
            "condonacion_mora": "1",
            "concepto": "Abono plan de pagos",
            "numsolicitud": "789",
            "form_token": "c9d02d2cf8..."
          }'
    ```

  ### GET /api/formas-pago
  - **Descripción:** obtiene las formas de pago disponibles para un proyecto específico. Útil para que agentes de IA decidan qué forma de pago usar al crear recibos.
  - **Auth/perm:** token API + sesión + `andinasoft.add_recaudos_general`.
  - **Query params:** `proyecto` (nombre del proyecto).
  - **Response 200:**
    ```json
    {
      "proyecto": "Tesoro Escondido",
      "total": 5,
      "formas_pago": [
        {
          "id": "Efectivo",
          "descripcion": "Efectivo",
          "cuenta_banco": "1234567890",
          "cuenta_contable": "110505"
        },
        {
          "id": "Transferencia",
          "descripcion": "Transferencia",
          "cuenta_banco": "9876543210",
          "cuenta_contable": "110510"
        }
      ]
    }
    ```
  - **Ejemplo curl:**
    ```bash
    curl "http://localhost:8000/api/formas-pago?proyecto=Tesoro%20Escondido" \
      -H "Authorization: Token <API_KEY>"
    ```
  - **Notas de uso:**
    - El campo `id` es el que debes enviar en el parámetro `forma_pago` al crear o validar un recibo.
    - Un agente de IA puede usar este endpoint para obtener las opciones y elegir la más apropiada según el soporte del pago (ej: si ve "transferencia" en el documento, usa la forma de pago "Transferencia").

  ## Adjudicaciones

  ### GET /api/adjudicaciones
  - **Descripción:** consulta adjudicaciones (ventas adjudicadas) de un proyecto. Si no se envía `id`, retorna un listado con información básica. Si se envía `id`, retorna el detalle completo con titulares, inmueble y datos sagrilaft.
  - **Auth/perm:** token API.
  - **Query params:**
    - `proyecto`* (nombre del proyecto)
    - `id` (opcional, ID de adjudicación ej: "ADJ001" o "001")
    - **Paginación:**
      - `page` (número de página, default: 1)
      - `page_size` o `limit` (registros por página, default: 100, max: 500)
      - `offset` (alternativa a page, número de registros a saltar)
    - **Filtros incrementales:**
      - `updated_since` (timestamp ISO 8601, ej: "2024-01-15T00:00:00")
      - `since_id` (ID de adjudicación para paginación por cursor, retorna > since_id)
    - **Ordenamiento:**
      - `order` (valores: `fecha`, `-fecha`, `idadjudicacion`, `-idadjudicacion`, default: `-fecha`)
  - **Filtro de estado:** Solo retorna adjudicaciones en estado `Aprobado` o `Pagado`.
  - **Response 200 (listado básico):**
    ```json
    {
      "proyecto": "Tesoro Escondido",
      "pagination": {
        "page": 1,
        "page_size": 100,
        "total_pages": 2,
        "total_records": 150
      },
      "filters": {
        "updated_since": null,
        "since_id": null,
        "order": "-fecha"
      },
      "total": 100,
      "adjudicaciones": [
        {
          "id": "ADJ001",
          "fecha": "2024-01-15T10:00:00",
          "tipo_contrato": "Compraventa",
          "contrato": "CV-001",
          "estado": "Aprobado",
          "inmueble_id": "M1L01",
          "titulares": [
            {"id": "123456789", "nombre": "Juan Pérez García"},
            {"id": "987654321", "nombre": "María López Ruiz"}
          ]
        }
      ]
    }
    ```
  - **Response 200 (detalle con id):**
    ```json
    {
      "proyecto": "Tesoro Escondido",
      "adjudicacion": {
        "id": "ADJ001",
        "fecha": "2024-01-15T10:00:00",
        "tipo_contrato": "Compraventa",
        "contrato": "CV-001",
        "estado": "Aprobado",
        "fecha_radicacion": "2024-01-10",
        "fecha_contrato": "2024-01-15",
        "fecha_desistimiento": null,
        "origen_venta": "Sala de ventas",
        "tipo_origen": "Directo",
        "oficina": "Principal",
        "es_juridico": false,
        "titulares": [
          {
            "posicion": 1,
            "id": "123456789",
            "tipo_documento": "13",
            "nombre_completo": "Juan Pérez García",
            "nombres": "Juan",
            "apellidos": "Pérez García",
            "celular": "3001234567",
            "celular2": null,
            "telefono": "6011234567",
            "email": "juan@email.com",
            "domicilio": "Calle 123 #45-67",
            "ciudad": "Bogotá",
            "pais": "Colombia",
            "departamento": "Cundinamarca",
            "ciudad_nombre": "Bogotá D.C.",
            "fecha_nacimiento": "1985-06-15",
            "lugar_nacimiento": "Bogotá",
            "nacionalidad": "Colombiano",
            "ocupacion": "DEPENDIENTE",
            "estado_civil": "Casado",
            "sagrilaft": {
              "empresa_labora": "Empresa XYZ",
              "cargo_actual": "Gerente",
              "origen_ingresos": "Salario",
              "declara_renta": true,
              "tiene_rut": true,
              "codigo_ciuu": "4711",
              "es_peps": false,
              "peps_desde": null,
              "peps_hasta": null,
              "peps_entidad": null,
              "peps_cargo": null,
              "peps_familiar": false,
              "peps_familiar_parentesco": null,
              "peps_familiar_entidad": null,
              "peps_familiar_cargo": null,
              "referencia_familiar": "María Pérez - Hermana",
              "referencia_familiar_telefono": "3009876543",
              "referencia_personal": "Carlos Gómez - Amigo",
              "referencia_personal_telefono": "3005551234"
            }
          }
        ],
        "inmueble": {
          "id": "M1L01",
          "etapa": "1",
          "manzana": "1",
          "lote": "01",
          "matricula": "001-12345",
          "estado": "Adjudicado",
          "area_privada": 120.50,
          "area_construida": 85.00,
          "area_lote": 150.00,
          "area_manzana": 5000.00
        }
      }
    }
    ```
  - **Errores comunes:**
    - 400: falta `proyecto`
    - 401: token inválido o no autenticado
    - 404: proyecto no encontrado o adjudicación no encontrada/no está en estado válido
    - 500: error inesperado
  - **Ejemplos curl:**
    ```bash
    # Listado básico (primera página, 100 registros)
    curl "https://tu-dominio/api/adjudicaciones?proyecto=Tesoro%20Escondido" \
      -H "Authorization: Token <API_KEY>"

    # Paginación: página 2 con 50 registros por página
    curl "https://tu-dominio/api/adjudicaciones?proyecto=Tesoro%20Escondido&page=2&page_size=50" \
      -H "Authorization: Token <API_KEY>"

    # Filtro incremental: solo adjudicaciones desde una fecha
    curl "https://tu-dominio/api/adjudicaciones?proyecto=Tesoro%20Escondido&updated_since=2024-01-15T00:00:00" \
      -H "Authorization: Token <API_KEY>"

    # Paginación por cursor: adjudicaciones después de un ID específico
    curl "https://tu-dominio/api/adjudicaciones?proyecto=Tesoro%20Escondido&since_id=ADJ100&order=idadjudicacion" \
      -H "Authorization: Token <API_KEY>"

    # Ordenar por ID ascendente para fetch incremental consistente
    curl "https://tu-dominio/api/adjudicaciones?proyecto=Tesoro%20Escondido&order=idadjudicacion" \
      -H "Authorization: Token <API_KEY>"

    # Detalle de una adjudicación específica
    curl "https://tu-dominio/api/adjudicaciones?proyecto=Tesoro%20Escondido&id=ADJ001" \
      -H "Authorization: Token <API_KEY>"

    # También acepta el ID sin prefijo ADJ
    curl "https://tu-dominio/api/adjudicaciones?proyecto=Tesoro%20Escondido&id=001" \
      -H "Authorization: Token <API_KEY>"
    ```
  - **Notas:**
    - El campo `sagrilaft` en cada titular será `null` si el cliente no tiene información sagrilaft registrada.
    - El inmueble no incluye información de colindantes ni linderos, solo datos básicos, matrícula y áreas.
    - Una adjudicación puede tener de 1 a 4 titulares, cada uno con su `posicion` (1-4).
    - El `id` de adjudicación acepta formatos "ADJ001", "adj001" o simplemente "001".
  - **Notas sobre paginación y fetch incremental:**
    - Para sincronización inicial: usa `page` y `page_size` iterando hasta `total_pages`.
    - Para sincronización incremental: usa `updated_since` con el timestamp de la última sincronización.
    - Para paginación por cursor (más eficiente en datasets grandes): usa `since_id` + `order=idadjudicacion`.
    - El máximo de `page_size` es 500 registros por request.

  ## Terceros

  ### GET /api/terceros
  - **Descripción:** consulta terceros (clientes). Si no se envía `id`, retorna un listado paginado con información básica. Si se envía `id`, retorna el detalle completo con datos personales y sagrilaft.
  - **Auth/perm:** token API.
  - **Query params:**
    - `id` (opcional, cédula/NIT del tercero)
    - **Paginación:**
      - `page` (número de página, default: 1)
      - `page_size` o `limit` (registros por página, default: 15, max: 15)
      - `offset` (alternativa a page, número de registros a saltar)
    - **Filtros:**
      - `search` (busca por nombre, parcial, case-insensitive)
    - **Ordenamiento:**
      - `order` (valores: `nombrecompleto`, `-nombrecompleto`, `idTercero`, `-idTercero`, `fecha_actualizacion`, `-fecha_actualizacion`, default: `nombrecompleto`)
  - **Response 200 (listado paginado):**
    ```json
    {
      "pagination": {
        "page": 1,
        "page_size": 15,
        "total_pages": 10,
        "total_records": 142
      },
      "total": 15,
      "terceros": [
        {
          "id": "123456789",
          "tipo_documento": "13",
          "nombre_completo": "Juan Pérez García",
          "celular": "3001234567",
          "email": "juan@email.com",
          "ciudad": "Bogotá"
        }
      ]
    }
    ```
  - **Response 200 (detalle con id):**
    ```json
    {
      "tercero": {
        "id": "123456789",
        "tipo_documento": "13",
        "nombre_completo": "Juan Pérez García",
        "nombres": "Juan",
        "apellidos": "Pérez García",
        "celular": "3001234567",
        "celular2": null,
        "telefono": "6011234567",
        "email": "juan@email.com",
        "domicilio": "Calle 123 #45-67",
        "ciudad": "Bogotá",
        "pais": "Colombia",
        "departamento": "Cundinamarca",
        "ciudad_nombre": "Bogotá D.C.",
        "fecha_nacimiento": "1985-06-15",
        "lugar_nacimiento": "Bogotá",
        "nacionalidad": "Colombiano",
        "ocupacion": "DEPENDIENTE",
        "estado_civil": "Casado",
        "sagrilaft": {
          "empresa_labora": "Empresa XYZ",
          "cargo_actual": "Gerente",
          "origen_ingresos": "Salario",
          "declara_renta": true,
          "tiene_rut": true,
          "codigo_ciuu": "4711",
          "es_peps": false,
          "peps_desde": null,
          "peps_hasta": null,
          "peps_entidad": null,
          "peps_cargo": null,
          "peps_familiar": false,
          "peps_familiar_parentesco": null,
          "peps_familiar_entidad": null,
          "peps_familiar_cargo": null,
          "referencia_familiar": "María Pérez - Hermana",
          "referencia_familiar_telefono": "3009876543",
          "referencia_personal": "Carlos Gómez - Amigo",
          "referencia_personal_telefono": "3005551234"
        }
      }
    }
    ```
  - **Errores comunes:**
    - 401: token inválido o no autenticado
    - 404: tercero no encontrado
    - 500: error inesperado
  - **Ejemplos curl:**
    ```bash
    # Listado básico (primera página, 15 registros)
    curl "https://tu-dominio/api/terceros" \
      -H "Authorization: Token <API_KEY>"

    # Paginación: página 2
    curl "https://tu-dominio/api/terceros?page=2" \
      -H "Authorization: Token <API_KEY>"

    # Buscar por nombre
    curl "https://tu-dominio/api/terceros?search=Juan%20Pérez" \
      -H "Authorization: Token <API_KEY>"

    # Detalle de un tercero específico
    curl "https://tu-dominio/api/terceros?id=123456789" \
      -H "Authorization: Token <API_KEY>"
    ```
  - **Notas:**
    - El campo `sagrilaft` será `null` si el cliente no tiene información sagrilaft registrada.
    - El `id` del tercero es su número de documento (cédula, NIT, etc.).
    - El máximo de `page_size` es 15 registros por request.

  ## Movimientos Plink

  ### POST /accounting/api/plink-movements
  - **Descripción:** registra movimientos conciliados descargados de Plink (tarjetas) para una empresa.
  - **Auth/perm:** sesión + `accounting.add_plinkmovement`
  - **Body JSON:**
    ```json
    {
      "empresa": <id>,
      "cuenta": "1234567890",  // opcional
      "movimientos": [
        {
          "NIT": "900993044",
          "CODIGO ESTABLECIMIENTO": "15970825",
          "ORIGEN DE LA COMPRA": "Electronico",
          "TIPO TRANSACCION": "COMPRA",
          "FRANQUICIA": "VISA",
          "IDENTIFICADOR DE RED": "CREDIBANCO",
          "FECHA DE TRANSACCION": "20251202",
          "FECHA DE CANJE": "20251203",
          "CUENTA DE CONSIGNACION": "23479333939",
          "VALOR COMPRA": "1353000.00",
          "VALOR PROPINA": "0.00",
          "VALOR IVA": "0.00",
          "VALOR IMPOCONSUMO": "0.00",
          "VALOR TOTAL": "1353000.00",
          "VALOR COMISION": "-32336.70",
          "VALOR RETEFUENTE": "-20295.00",
          "VALOR RETE IVA": "0.00",
          "VALOR RTE ICA": "-6765.00",
          "VALOR PROVISION": "0.00",
          "VALOR NETO": "1293603.30",
          "CODIGO AUTORIZACION": "955494",
          "TIPO TARJETA": "CREDITO NACIONAL",
          "NO TERMINAL": "49544",
          "TARJETA": "************4614",
          "COMISION PORCENTUAL": "2.39%",
          "COMISION BASE": "0.00",
          "FECHA DE COMPENSACION": "20251202"
        }
      ]
    }
    ```
  - **Response 201 (schema):**
    ```json
    {
      "empresa": <id>,
      "total": <int>,
      "movimientos": [
        {
          "id": <int>,
          "codigo_autorizacion": "string|null",
          "fecha_transaccion": "YYYY-MM-DD"
        }
      ]
    }
    ```

  ### GET /accounting/api/plink-movements/list
  - **Descripción:** consulta movimientos Plink guardados para una empresa en un rango de fechas (fecha de transacción).
  - **Auth/perm:** sesión + `accounting.view_plinkmovement`
  - **Query params:** `empresa`*, `fecha_desde`*, `fecha_hasta`*, `usado_agente` (opcional: `true|false|1|0`)
  - **Response 200 (schema):**
    ```json
    {
      "empresa": <id>,
      "total": <int>,
      "movimientos": [
        {
          "id": <int>,
          "fecha_transaccion": "YYYY-MM-DD",
          "fecha_canje": "YYYY-MM-DD|null",
          "codigo_autorizacion": "string|null",
          "valor_total": <float>,
          "valor_neto": <float>,
          "cuenta_consignacion": "string|null",
          "cuenta_normalizada": "string|null",
          "tipo_transaccion": "string|null",
          "franquicia": "string|null",
          "usado_agente": true|false,
          "fecha_uso_agente": "YYYY-MM-DD HH:MM:SS|null",
          "recibo_asociado_agente": "string|null"
        }
      ]
    }
    ```
  - **Nota:** Los campos `usado_agente`, `fecha_uso_agente` y `recibo_asociado_agente` indican si el movimiento ya fue utilizado por el agente de conciliación automática, cuándo y con qué recibo. Esto es útil para evitar duplicados cuando hay múltiples movimientos con el mismo valor.

  ### PATCH /accounting/api/plink-movements/<id>/mark-used
  - **Descripción:** marca o desmarca un movimiento Plink como usado por el agente de conciliación automática.
  - **Auth/perm:** sesión + `accounting.change_plinkmovement`
  - **Parámetros URL:** `<id>` - ID del movimiento Plink
  - **Body JSON:**
    ```json
    {
      "usado_agente": true|false,
      "recibo_asociado_agente": "4587"  // opcional
    }
    ```
  - **Response 200:**
    ```json
    {
      "id": 123,
      "usado_agente": true,
      "fecha_uso_agente": "2025-12-15 10:30:45",
      "recibo_asociado_agente": "4587",
      "mensaje": "Movimiento marcado como usado"
    }
    ```
  - **Response 400:**
    ```json
    {
      "detail": "Debes enviar 'usado_agente'",
      "error_code": "MISSING_USADO"
    }
    ```
  - **Response 404:**
    ```json
    {
      "detail": "Movimiento no encontrado",
      "error_code": "NOT_FOUND"
    }
    ```
  - **Ejemplo curl:**
    ```bash
    # Marcar movimiento como usado
    curl -X PATCH "https://tu-dominio/accounting/api/plink-movements/123/mark-used" \
      -H "Authorization: Token <API_KEY>" \
      -H "Content-Type: application/json" \
      -d '{"usado_agente": true, "recibo_asociado_agente": "4587"}'
    
    # Desmarcar movimiento
    curl -X PATCH "https://tu-dominio/accounting/api/plink-movements/123/mark-used" \
      -H "Authorization: Token <API_KEY>" \
      -H "Content-Type: application/json" \
      -d '{"usado_agente": false}'
    ```

  ## Movimientos Wompi

  ### POST /accounting/api/wompi-movements
  - **Descripción:** registra movimientos recibidos desde Wompi (links de pago, recaudos tarjeta) para una empresa.
  - **Auth/perm:** sesión + `accounting.add_wompimovement`
  - **Body JSON:**
    ```json
    {
      "empresa": <id>,
      "cuenta": "1234567890",  // opcional
      "movimientos": [
        {
          "id de la transaccion": "1109322-1764705038-66334",
          "fecha": "2025-12-02 14:52:12",
          "referencia": "MIppTF_1764704833167_sx16dvc0mdr",
          "monto": "10000000.00",
          "iva": "0.00",
          "impuesto al consumo": "0.00",
          "moneda": "COP",
          "medio de pago": "CARD",
          "email del pagador": "beatrizeqa@hotmail.com",
          "nombre del pagador": "QUINTERO ARIAS BEATRIZ ELENA",
          "telefono del pagador": "+573147941455",
          "id conciliacion": "R08981",
          "id link de pago": "MIppTF",
          "documento del pagador": "43043085",
          "tipo de documento del pagador": "CC",
          "ref. 1 nombre": "Lote",
          "ref. 1": "Lote beatriz elena quintero 43043085"
        }
      ]
    }
    ```
  - **Response 201:** igual a Plink pero con `transaction_id` y `fecha`.

  ### GET /accounting/api/wompi-movements/list
  - **Descripción:** consulta movimientos Wompi por empresa y rango de fechas (fecha de la transacción).
  - **Auth/perm:** sesión + `accounting.view_wompimovement`
  - **Query params:** `empresa`*, `fecha_desde`*, `fecha_hasta`*, `usado_agente` (opcional: `true|false|1|0`)
  - **Response 200 (schema):**
    ```json
    {
      "empresa": <id>,
      "total": <int>,
      "movimientos": [
        {
          "id": <int>,
          "transaction_id": "string",
          "fecha": "YYYY-MM-DD HH:MM:SS",
          "referencia": "string",
          "monto": <float>,
          "medio_pago": "string",
          "email_pagador": "string|null",
          "id_conciliacion": "string|null",
          "cuenta_normalizada": "string|null",
          "usado_agente": true|false,
          "fecha_uso_agente": "YYYY-MM-DD HH:MM:SS|null",
          "recibo_asociado_agente": "string|null"
        }
      ]
    }
    ```
  - **Nota:** Los campos `usado_agente`, `fecha_uso_agente` y `recibo_asociado_agente` indican si el movimiento ya fue utilizado por el agente de conciliación automática, cuándo y con qué recibo. Esto es útil para evitar duplicados cuando hay múltiples movimientos con el mismo valor.

  ### PATCH /accounting/api/wompi-movements/<id>/mark-used
  - **Descripción:** marca o desmarca un movimiento Wompi como usado por el agente de conciliación automática.
  - **Auth/perm:** sesión + `accounting.change_wompimovement`
  - **Parámetros URL:** `<id>` - ID del movimiento Wompi
  - **Body JSON:**
    ```json
    {
      "usado_agente": true|false,
      "recibo_asociado_agente": "4587"  // opcional
    }
    ```
  - **Response 200:**
    ```json
    {
      "id": 456,
      "usado_agente": true,
      "fecha_uso_agente": "2025-12-15 10:30:45",
      "recibo_asociado_agente": "4587",
      "mensaje": "Movimiento marcado como usado"
    }
    ```
  - **Response 400:**
    ```json
    {
      "detail": "Debes enviar 'usado_agente'",
      "error_code": "MISSING_USADO"
    }
    ```
  - **Response 404:**
    ```json
    {
      "detail": "Movimiento no encontrado",
      "error_code": "NOT_FOUND"
    }
    ```
  - **Ejemplo curl:**
    ```bash
    # Marcar movimiento como usado
    curl -X PATCH "https://tu-dominio/accounting/api/wompi-movements/456/mark-used" \
      -H "Authorization: Token <API_KEY>" \
      -H "Content-Type: application/json" \
      -d '{"usado_agente": true, "recibo_asociado_agente": "4587"}'
    
    # Desmarcar movimiento
    curl -X PATCH "https://tu-dominio/accounting/api/wompi-movements/456/mark-used" \
      -H "Authorization: Token <API_KEY>" \
      -H "Content-Type: application/json" \
      -d '{"usado_agente": false}'
    ```
