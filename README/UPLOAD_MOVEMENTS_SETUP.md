# Setup: Carga de Movimientos Bancarios

## ✅ Implementación completada

Se ha implementado exitosamente el sistema de carga masiva de movimientos bancarios con las siguientes características:

### 📁 Archivos modificados/creados:

1. **[andina/settings.py](andina/settings.py#L382-L394)** - Configuración de webhooks n8n
2. **[accounting/views.py](accounting/views.py#L5793-L6027)** - 3 nuevas funciones view
3. **[accounting/views.py](accounting/views.py#L6033-L6035)** - 3 nuevas URLs agregadas
4. **[accounting/templates/upload_movements.html](accounting/templates/upload_movements.html)** - Template principal

---

## 🚀 Configuración necesaria

### 1. Variables de entorno (.env)

Agrega las siguientes variables a tu archivo `.env`:

```bash
# Webhooks de n8n para carga de movimientos
N8N_WEBHOOK_UPLOAD_MOVEMENTS=https://n8n.tudominio.com/webhook/upload-movements
N8N_WEBHOOK_WOMPI_COUNT=https://n8n.tudominio.com/webhook/wompi-count
N8N_WEBHOOK_PLINK_COUNT=https://n8n.tudominio.com/webhook/plink-count
```

**Nota:** Si estás en desarrollo local, los valores por defecto apuntan a `http://localhost:5678/webhook/...`

---

## 🔄 Flujos n8n necesarios

Debes crear **3 webhooks** en n8n:

### A. Webhook: Wompi Count
```
GET /webhook/wompi-count?empresa_id=1

Response esperado (últimos 3 días):
{
  "2026-01-05": 23,
  "2026-01-04": 18,
  "2026-01-03": 12
}
```

**O formato alternativo:**
```json
{
  "movimientos": [
    {"fecha": "2026-01-05", "count": 23},
    {"fecha": "2026-01-04", "count": 18},
    {"fecha": "2026-01-03", "count": 12}
  ]
}
```

**Flujo sugerido:**
1. Webhook Trigger (GET)
2. Google Sheets Node - Lookup en Sheet "Wompi"
3. Function Node - Filtrar por `empresa_id` y agrupar por fecha (últimos 3 días)
4. Function Node - Contar movimientos por fecha
5. Response con JSON

---

### B. Webhook: Plink Count
```
GET /webhook/plink-count?empresa_id=1

Response esperado (últimos 3 días):
{
  "2026-01-05": 12,
  "2026-01-04": 8,
  "2026-01-03": 5
}
```

**O formato alternativo:**
```json
{
  "movimientos": [
    {"fecha": "2026-01-05", "count": 12},
    {"fecha": "2026-01-04", "count": 8},
    {"fecha": "2026-01-03", "count": 5}
  ]
}
```

**Flujo sugerido:**
1. Webhook Trigger (GET)
2. Google Sheets Node - Lookup en Sheet "Plink"
3. Function Node - Filtrar por `empresa_id` y agrupar por fecha_transaccion (últimos 3 días)
4. Function Node - Contar movimientos por fecha
5. Response con JSON

---

### C. Webhook: Upload Movements
```
POST /webhook/upload-movements
Content-Type: multipart/form-data

FormData:
  - empresa: <id>
  - archivo_banco: <file> (opcional)
  - archivo_wompi: <file> (opcional)
  - archivo_plink: <file> (opcional)
```

**Response esperado (éxito):**
```json
{
  "success": true,
  "message": "Movimientos cargados exitosamente",
  "detalles": {
    "banco": 45,
    "wompi": 23,
    "plink": 12
  }
}
```

**Response esperado (con rechazos):**
```json
{
  "success": false,
  "message": "15 movimientos fueron rechazados",
  "archivo_rechazados": "<base64_del_excel>",
  "nombre_archivo": "rechazados_2026-01-02_143045.xlsx"
}
```

**Flujo sugerido:**
1. Webhook Trigger (POST, multipart/form-data)
2. Switch Node - Separar por tipo de archivo
3. Para cada archivo:
   - Parse Excel/CSV
   - Validar datos
   - **BANCO:** Llamar a `POST /accounting/api/bank-movements`
   - **WOMPI:** Agregar filas a Google Sheet "Wompi"
   - **PLINK:** Agregar filas a Google Sheet "Plink"
4. Consolidar resultados
5. Si hay errores:
   - Generar Excel con rechazados
   - Convertir a base64
6. Response con JSON

---

## 🌐 URLs disponibles

Después del despliegue, las siguientes URLs estarán disponibles:

- **Página principal:** `https://app.somosandina.co/accounting/upload-movements`
- **API resumen:** `https://app.somosandina.co/accounting/api/movements-summary?empresa=<id>`
- **API upload:** `https://app.somosandina.co/accounting/api/upload-movements`

---

## 🔐 Permisos requeridos

Para acceder a la funcionalidad, el usuario debe tener:

- **Vista página:** `accounting.add_egresos_banco`
- **API resumen:** `accounting.view_egresos_banco`
- **API upload:** `accounting.add_egresos_banco`

---

## 📊 Flujo de usuario

1. Usuario accede a `/accounting/upload-movements`
2. Selecciona empresa del dropdown
3. **Automáticamente** se carga resumen de últimos 5 días:
   - Banco (consulta Django DB)
   - Wompi (consulta n8n → Sheets)
   - Plink (consulta n8n → Sheets)
4. Usuario selecciona uno o más archivos (Banco, Wompi, Plink)
5. Click en "Cargar Movimientos"
6. Django envía archivos a n8n
7. n8n procesa y:
   - Banco → API Django `/accounting/api/bank-movements`
   - Wompi/Plink → Google Sheets
8. n8n retorna resultado a Django
9. Django retorna resultado al frontend
10. Frontend muestra:
    - **Éxito:** Mensaje de confirmación + recarga automática del resumen
    - **Rechazos:** Mensaje + descarga automática de archivo Excel con rechazados

---

## 🧪 Testing

### Probar el resumen (sin n8n):

```bash
# Asegúrate de tener al menos una empresa y movimientos en egresos_banco
curl -X GET "http://localhost:8000/accounting/api/movements-summary?empresa=1" \
  -H "Cookie: sessionid=<tu_session_id>"
```

**Nota:** Wompi y Plink retornarán `0` si n8n no está configurado, pero Banco debería funcionar.

### Probar el upload (necesita n8n):

```bash
curl -X POST "http://localhost:8000/accounting/api/upload-movements" \
  -H "Cookie: sessionid=<tu_session_id>" \
  -F "empresa=1" \
  -F "archivo_banco=@/ruta/a/archivo.xlsx"
```

---

## 🎨 Características del UI

- ✅ Iconos animados con Lord Icon
- ✅ Selector de empresa con búsqueda
- ✅ Tabla responsive con últimos 5 días
- ✅ Upload de múltiples archivos simultáneamente
- ✅ Loading states y spinners
- ✅ Alertas de éxito/error
- ✅ Descarga automática de archivos rechazados
- ✅ Recarga automática del resumen después de upload exitoso
- ✅ Validación client-side

---

## 📝 Estructura de archivos esperados

### Banco (Excel/CSV)
Debe ser compatible con el endpoint existente `POST /accounting/api/bank-movements`

### Wompi (Excel/CSV)
Debe contener las columnas según la estructura en Sheets

### Plink (Excel/CSV)
Debe contener las columnas según la estructura en Sheets

---

## 🐛 Troubleshooting

### Error: "Error al cargar el resumen de movimientos"
- Verifica que los webhooks de n8n estén activos
- Revisa los logs de Django para ver el error específico
- Si Banco funciona pero Wompi/Plink no, es problema de n8n

### Error: "El procesamiento está tomando demasiado tiempo"
- Reduce la cantidad de movimientos por archivo
- Aumenta el timeout en `accounting/views.py` línea 6003

### Error: "No se encontró ninguna empresa"
- Verifica que el ID de empresa sea correcto
- Asegúrate de que la empresa exista en la base de datos

---

## 🔧 Personalización

### Cambiar el timeout de procesamiento:

Edita [accounting/views.py](accounting/views.py#L6003):
```python
timeout=300  # 5 minutos por defecto
```

### Cambiar cantidad de días en el resumen:

Edita [accounting/views.py](accounting/views.py#L5851):
```python
for i in range(5):  # Cambia 5 por la cantidad deseada
```

---

## 📚 Referencias

- **API Documentation:** [API_accounting.md](API_accounting.md)
- **Base Template:** [templates/base.html](templates/base.html)
- **Accounting Templates:** [accounting/templates/](accounting/templates/)

---

## ✨ Siguiente paso: Configurar n8n

Ahora debes crear los 3 webhooks en n8n según las especificaciones arriba.

¿Necesitas ayuda con los flujos de n8n? Puedo diseñarlos en detalle.
