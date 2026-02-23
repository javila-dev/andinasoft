# Sistema de Callback para Carga de Movimientos

## 📖 Descripción

Este sistema permite que n8n procese archivos de movimientos bancarios de forma **asíncrona** y notifique a Django cuando termine el procesamiento mediante un callback.

## 🔄 Flujo del Sistema

### 1. Usuario Sube Archivos
```
Usuario → Django → n8n (retorna inmediatamente)
         ↓
     job_id creado (status: processing)
         ↓
     Respuesta al frontend con job_id
```

### 2. N8n Procesa en Segundo Plano
```
n8n procesa archivos →  Banco API / Sheets → Callback a Django
                                                    ↓
                                            Actualiza job con resultado
```

### 3. Frontend Consulta Estado
```
Frontend polling → Django API → Retorna status del job
    ↓
Status: completed/failed/partial → Mostrar resultado
```

---

## 🔌 Endpoints Django

### A. Subir Archivos (Retorna Inmediatamente)
```
POST /accounting/api/upload-movements

FormData:
  - empresa: <id>
  - archivo_banco: <file> (opcional)
  - archivo_wompi: <file> (opcional)
  - archivo_plink: <file> (opcional)

Response Inmediata:
{
  "job_id": 123,
  "status": "processing",
  "message": "Los archivos se están procesando..."
}
```

### B. Consultar Estado del Job
```
GET /accounting/api/check-upload-status?job_id=123

Response (processing):
{
  "job_id": 123,
  "status": "processing",
  "empresa": 1,
  "created_at": "2026-01-06T10:30:00Z",
  "updated_at": "2026-01-06T10:30:05Z"
}

Response (completed):
{
  "job_id": 123,
  "status": "completed",
  "empresa": 1,
  "created_at": "2026-01-06T10:30:00Z",
  "updated_at": "2026-01-06T10:35:00Z",
  "completed_at": "2026-01-06T10:35:00Z",
  "mensaje": "Movimientos cargados exitosamente",
  "detalles": {
    "banco": 45,
    "wompi": 23,
    "plink": 12
  }
}

Response (partial - con rechazos):
{
  "job_id": 123,
  "status": "partial",
  "mensaje": "15 movimientos fueron rechazados",
  "detalles": { ... },
  "movimientos_rechazados": 15,
  "archivo_rechazados": "<base64>",
  "nombre_archivo": "rechazados_2026-01-06.xlsx"
}

Response (failed):
{
  "job_id": 123,
  "status": "failed",
  "mensaje": "Error al procesar movimientos",
  "error": "Detalle del error..."
}
```

### C. Callback desde N8n (IMPORTANTE)
```
POST /accounting/api/upload-callback

Headers:
  Content-Type: application/json

Body (éxito total):
{
  "job_id": 123,
  "success": true,
  "message": "Movimientos cargados exitosamente",
  "detalles": {
    "banco": 45,
    "wompi": 23,
    "plink": 12
  }
}

Body (con rechazos):
{
  "job_id": 123,
  "success": false,
  "message": "15 movimientos fueron rechazados",
  "movimientos_rechazados": 15,
  "detalles": {
    "banco": 40,
    "wompi": 20,
    "plink": 10
  },
  "archivo_rechazados": "<base64 del Excel con rechazados>",
  "nombre_archivo": "rechazados_2026-01-06_143045.xlsx"
}

Body (error total):
{
  "job_id": 123,
  "success": false,
  "message": "Error al procesar archivos",
  "error": "Detalle del error..."
}

Response:
{
  "status": "ok",
  "job_id": 123,
  "updated_status": "completed" // o "partial", "failed"
}
```

---

## 🎯 Configuración de N8n

### Flujo Modificado

**Antes** (síncrono - PROBLEMÁTICO):
```
Webhook → Procesar → Respond to Webhook
          (tarda mucho, timeout)
```

**Ahora** (asíncrono con callback - SOLUCIÓN):
```
┌─────────┐
│ Webhook │ ← Recibe: job_id, callback_url, archivos
└────┬────┘
     │
     ↓
┌──────────────────────┐
│ Respond to Webhook2  │ → Retorna inmediatamente (acepta el job)
└──────────────────────┘
     │
     ↓
┌─────────────────────┐
│ Switch por archivo  │
└────┬────────────────┘
     │
     ├─→ Banco  → API Django /accounting/api/bank-movements
     │
     ├─→ Wompi  → Google Sheets
     │
     └─→ Plink  → Google Sheets
     │
     ↓
┌──────────────────────┐
│ Consolidar Resultados│
└────┬─────────────────┘
     │
     ↓
┌──────────────────────────────────────┐
│ HTTP Request - Callback a Django     │
│ POST callback_url                     │
│ Body: {job_id, success, detalles...} │
└──────────────────────────────────────┘
```

### Pasos en N8n:

1. **Webhook Trigger Node**
   - Path: `/webhook/upload-movements-andinasoft`
   - HTTP Method: POST
   - Respond: Using 'Respond to Webhook' Node
   - **Response Mode: Immediately (When Workflow Starts)**

2. **Respond to Webhook2 Node** (colócalo justo después del Webhook)
   - Response Code: 200
   - Response Body:
   ```json
   {
     "message": "Workflow was started",
     "job_id": "{{ $json.job_id }}"
   }
   ```

3. **Nodos de Procesamiento** (Switch, Excel, API calls, etc.)

4. **HTTP Request Node - Callback** (al final del flujo)
   - Method: POST
   - URL: `{{ $node["Webhook"].json["body"]["callback_url"] }}`
   - Authentication: None
   - Body Content Type: JSON
   - Specify Body: Using Fields Below

   **Fields del Body:**

   | Field Name | Value (Expression) |
   |------------|-------------------|
   | `job_id` | `{{ $node["Webhook"].json["body"]["job_id"] }}` |
   | `success` | `{{ true }}` (o lógica condicional) |
   | `message` | `{{ "Movimientos cargados exitosamente" }}` |
   | `detalles` | `{{ {"banco": 45, "wompi": 23, "plink": 12} }}` |
   | `movimientos_rechazados` | `{{ 0 }}` (opcional, solo si hay) |
   | `archivo_rechazados` | `{{ $binary.data }}` (opcional, base64) |
   | `nombre_archivo` | `{{ "rechazados.xlsx" }}` (opcional) |

   **Ejemplo de Expression para `success`:**
   ```javascript
   // Si todos los archivos se procesaron sin errores
   {{ $node["Process Banco"].json["success"] &&
      $node["Process Wompi"].json["success"] &&
      $node["Process Plink"].json["success"] }}
   ```

   **Ejemplo de Expression para `message`:**
   ```javascript
   {{ $node["Process Banco"].json["success"] ?
      "Movimientos cargados exitosamente" :
      "Algunos movimientos fueron rechazados" }}
   ```

### Datos que N8n Recibe del Webhook:

**IMPORTANTE:** Django envía el `job_id` en el FormData desde el inicio, para que n8n lo tenga disponible durante todo el procesamiento.

```
FormData recibido por n8n:
- empresa: "1"
- job_id: "123"  ← ESTE ES EL ID QUE N8N DEBE USAR EN EL CALLBACK
- callback_url: "https://app.somosandina.co/accounting/api/upload-callback"
- Movimiento_Banco: <binary file> (si existe)
- Movimiento_Wompi: <binary file> (si existe)
- Movimiento_Plink: <binary file> (si existe)
```

**Acceso en n8n:**
```javascript
// En cualquier nodo después del Webhook
const jobId = $node["Webhook"].json["body"]["job_id"];
const callbackUrl = $node["Webhook"].json["body"]["callback_url"];
const empresaId = $node["Webhook"].json["body"]["empresa"];
```

---

## 💻 Implementación Frontend

### JavaScript con Polling:

```javascript
// 1. Subir archivos
const formData = new FormData();
formData.append('empresa', empresaId);
formData.append('archivo_banco', fileBanco);
// ... otros archivos

const response = await fetch('/accounting/api/upload-movements', {
    method: 'POST',
    body: formData
});

const data = await response.json();
const jobId = data.job_id;

// Mostrar mensaje "Procesando..."
mostrarMensaje('Procesando archivos...', 'info');

// 2. Hacer polling del estado
const checkStatus = async () => {
    const statusResponse = await fetch(
        `/accounting/api/check-upload-status?job_id=${jobId}`
    );
    const statusData = await statusResponse.json();

    if (statusData.status === 'processing') {
        // Sigue esperando
        setTimeout(checkStatus, 2000); // Check cada 2 segundos
    } else if (statusData.status === 'completed') {
        // Éxito
        mostrarMensaje(statusData.mensaje, 'success');
        recargarResumen();
    } else if (statusData.status === 'partial') {
        // Con rechazos
        mostrarMensaje(statusData.mensaje, 'warning');
        descargarRechazados(
            statusData.archivo_rechazados,
            statusData.nombre_archivo
        );
        recargarResumen();
    } else if (statusData.status === 'failed') {
        // Error
        mostrarMensaje(statusData.mensaje, 'error');
    }
};

// Iniciar polling
setTimeout(checkStatus, 2000);
```

---

## 📊 Estados del Job

| Estado | Descripción |
|--------|-------------|
| `pending` | Job creado pero no iniciado (raro, normalmente pasa directo a processing) |
| `processing` | N8n está procesando los archivos |
| `completed` | Procesamiento exitoso sin errores |
| `partial` | Completado pero con algunos movimientos rechazados |
| `failed` | Error total en el procesamiento |

---

## 🔍 Tabla de Base de Datos

```sql
CREATE TABLE accounting_upload_movements_job (
    id INT AUTO_INCREMENT PRIMARY KEY,
    empresa_id VARCHAR(255) NOT NULL,
    usuario_id INT NOT NULL,
    status VARCHAR(20) NOT NULL, -- pending, processing, completed, partial, failed

    -- Archivos enviados
    tiene_banco BOOLEAN NOT NULL,
    tiene_wompi BOOLEAN NOT NULL,
    tiene_plink BOOLEAN NOT NULL,

    -- Resultados
    movimientos_banco INT NULL,
    movimientos_wompi INT NULL,
    movimientos_plink INT NULL,
    movimientos_rechazados INT NULL,

    -- Archivos de rechazos
    archivo_rechazados LONGTEXT NULL, -- Base64
    nombre_archivo_rechazados VARCHAR(255) NULL,

    -- Mensajes
    mensaje LONGTEXT NULL,
    error_detail LONGTEXT NULL,

    -- Timestamps
    created_at DATETIME(6) NOT NULL,
    updated_at DATETIME(6) NOT NULL,
    completed_at DATETIME(6) NULL,

    FOREIGN KEY (empresa_id) REFERENCES andinasoft_empresas (Nit),
    FOREIGN KEY (usuario_id) REFERENCES auth_user (id)
);
```

---

## ⚠️ Consideraciones Importantes

### Job ID Disponible Desde el Inicio
- **CRÍTICO:** Django crea el `job_id` ANTES de enviar a n8n
- N8n lo recibe en `$node["Webhook"].json["body"]["job_id"]`
- Este `job_id` debe usarse en el callback al final del flujo
- Si n8n no encuentra el `job_id`, revisar que el webhook esté recibiendo FormData correctamente

### Seguridad
- El callback endpoint (`/accounting/api/upload-callback`) **NO requiere autenticación** porque n8n no puede enviar tokens de Django
- Esto es seguro porque:
  - Solo actualiza jobs que ya existen
  - No crea ni elimina datos
  - Solo n8n conoce la URL completa del callback
  - El `job_id` actúa como token de autenticación implícito

### Timeout
- Django envía el request a n8n con timeout de 10 segundos
- Si n8n no responde en 10 segundos, Django retorna `job_id` con status `processing`
- El frontend debe hacer polling del estado

### Polling Interval
- Recomendado: cada 2-3 segundos
- Máximo tiempo de polling: 5 minutos (configurablé en frontend)
- Después de 5 minutos, mostrar mensaje de timeout y permitir refresh manual

### Limpieza de Jobs
- Los jobs completados/fallidos se mantienen en BD para auditoría
- Se puede crear un cron job para eliminar jobs más antiguos de 30 días:
  ```python
  from django.utils import timezone
  from datetime import timedelta
  from accounting.models import upload_movements_job

  cutoff = timezone.now() - timedelta(days=30)
  upload_movements_job.objects.filter(
      created_at__lt=cutoff
  ).delete()
  ```

---

## ✅ Testing

### Test del Flujo Completo:

1. **Subir archivos:**
   ```bash
   curl -X POST http://localhost:8000/accounting/api/upload-movements \
     -H "Cookie: sessionid=<session>" \
     -F "empresa=1" \
     -F "archivo_banco=@movimientos.xlsx"
   ```

   Debe retornar:
   ```json
   {"job_id": 1, "status": "processing", "message": "..."}
   ```

2. **Consultar estado:**
   ```bash
   curl -X GET "http://localhost:8000/accounting/api/check-upload-status?job_id=1" \
     -H "Cookie: sessionid=<session>"
   ```

3. **Simular callback desde n8n:**
   ```bash
   curl -X POST http://localhost:8000/accounting/api/upload-callback \
     -H "Content-Type: application/json" \
     -d '{
       "job_id": 1,
       "success": true,
       "message": "Movimientos cargados",
       "detalles": {"banco": 10, "wompi": 5, "plink": 3}
     }'
   ```

4. **Verificar actualización:**
   ```bash
   curl -X GET "http://localhost:8000/accounting/api/check-upload-status?job_id=1" \
     -H "Cookie: sessionid=<session>"
   ```

   Debe mostrar status `completed`

---

## 📝 Logs Recomendados

En Django (`accounting/views.py`):
```python
import logging
logger = logging.getLogger(__name__)

# En api_upload_movements
logger.info(f"Job {job.id} created for empresa {empresa.nombre} by {request.user.username}")

# En api_upload_callback
logger.info(f"Callback received for job {job_id}: status={data.get('success')}")
```

En n8n:
- Agregar nodo "Stop and Error" para manejar errores
- Siempre enviar callback incluso si hay error

---

## 🎉 Ventajas del Sistema

✅ **No bloquea el navegador** - Usuario puede seguir trabajando
✅ **Soporta archivos grandes** - N8n tiene tiempo ilimitado para procesar
✅ **Mejor UX** - Feedback claro del progreso
✅ **Auditoría** - Todos los jobs quedan registrados en BD
✅ **Recuperable** - Si falla, se puede reintentar o revisar el job
✅ **Escalable** - N8n puede procesar múltiples jobs en paralelo

---

## 🐛 Troubleshooting del Callback

### Problema: "N8n no tiene el job_id"

**Síntoma:** El nodo HTTP Request de callback falla porque `job_id` es undefined

**Solución:**
1. Verificar que el webhook esté recibiendo FormData:
   ```javascript
   // En un nodo Function después del Webhook, verificar:
   console.log($node["Webhook"].json["body"]);
   // Debe mostrar: {empresa: "1", job_id: "123", callback_url: "..."}
   ```

2. Si no está recibiendo el body correctamente:
   - Verificar que el Webhook tenga "Binary Data" activado
   - Verificar que "Raw Body" esté desactivado
   - El Content-Type debe ser `multipart/form-data`

### Problema: "Django no recibe el callback"

**Síntoma:** El job queda en status `processing` indefinidamente

**Causas posibles:**
1. **N8n no está enviando el callback** - Verificar logs de n8n
2. **URL incorrecta** - Verificar que `callback_url` sea correcta
3. **Firewall bloqueando** - Verificar que n8n pueda hacer POST a Django

**Solución:**
```javascript
// En el nodo HTTP Request de callback, agregar error handling:
// Settings → Continue On Fail: true
// Luego agregar un nodo IF para verificar si funcionó:
{{ $node["HTTP Request"].json["status"] === "ok" }}
```

### Problema: "Callback se envía pero Django retorna 404"

**Causa:** El callback_url no incluye el dominio completo

**Verificar:**
```python
# En Django shell:
from django.test import RequestFactory
factory = RequestFactory()
request = factory.get('/')
print(request.build_absolute_uri('/accounting/api/upload-callback'))
# Debe retornar: https://app.somosandina.co/accounting/api/upload-callback
```

**Solución temporal:**
Hardcodear la URL en n8n:
```
URL: https://app.somosandina.co/accounting/api/upload-callback
```

### Problema: "Job se marca como completed pero sin detalles"

**Causa:** N8n está enviando el callback con estructura incorrecta

**Verificar el Body del callback:**
```json
{
  "job_id": 123,  // ← debe ser número o string
  "success": true,  // ← debe ser boolean
  "detalles": {  // ← debe ser objeto
    "banco": 45,
    "wompi": 23,
    "plink": 12
  }
}
```

**En n8n, usar "Specify Body: Using Fields" NO "Using JSON"**

### Problema: "N8n procesa pero no hace callback"

**Causa:** El flujo tiene error antes de llegar al nodo de callback

**Solución:**
1. Agregar nodo "Stop and Error" con manejo de errores
2. Siempre enviar callback incluso si hay error:
   ```
   IF Node → Success → Callback con success=true
          → Error → Callback con success=false, error=mensaje
   ```

---

## 🚀 Próximos Pasos

1. Configurar los 3 webhooks en n8n según las especificaciones
2. Modificar el flujo existente para usar el modo de respuesta inmediata
3. Agregar el nodo de callback al final del flujo
4. Probar con un archivo pequeño primero
5. Monitorear logs y ajustar timeouts si es necesario
