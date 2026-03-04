# Tests para Abono a Capital

## 📋 Descripción

Tests completos para la funcionalidad de Abono a Capital, cubriendo:
- ✅ Validaciones de integridad post-proceso
- ✅ Transacciones atómicas con rollback
- ✅ Casos de éxito y fallo
- ✅ Verificación de que no quedan registros huérfanos

**IMPORTANTE:**
- Estos tests usan el alias **'Casas de Verano'** como proyecto de prueba
- Django crea automáticamente la base de datos `test_developer_casasdeverano` para los tests
- Los tests **NO afectan la base de datos de producción** (`developer_casasdeverano`)
- Django hace rollback automático después de cada test

---

## 🚀 Cómo ejecutar los tests

### **Ejecutar TODOS los tests del módulo:**
```bash
python manage.py test andinasoft.tests
```

### **Ejecutar una clase específica de tests:**
```bash
# Tests de validación
python manage.py test andinasoft.tests.AbonoCapitalValidacionTestCase

# Tests de integración
python manage.py test andinasoft.tests.AbonoCapitalIntegracionTestCase

# Tests de rollback
python manage.py test andinasoft.tests.AbonoCapitalRollbackTestCase
```

### **Ejecutar un test individual:**
```bash
# Test de validación exitosa
python manage.py test andinasoft.tests.AbonoCapitalValidacionTestCase.test_validacion_exitosa_plan_cuadrado

# Test de capital descuadrado
python manage.py test andinasoft.tests.AbonoCapitalValidacionTestCase.test_validacion_falla_capital_plan_no_coincide

# Test de cuotas descuadradas
python manage.py test andinasoft.tests.AbonoCapitalValidacionTestCase.test_validacion_falla_cuotas_descuadradas

# Test de rollback
python manage.py test andinasoft.tests.AbonoCapitalIntegracionTestCase.test_abono_capital_falla_validacion_rollback_completo
```

### **Ejecutar con más detalle (verbose):**
```bash
python manage.py test andinasoft.tests --verbosity=2
```

### **Ejecutar con cobertura de código:**
```bash
# Instalar coverage si no está instalado
pip install coverage

# Ejecutar tests con cobertura
coverage run --source='andinasoft' manage.py test andinasoft.tests

# Ver reporte
coverage report

# Ver reporte HTML
coverage html
# Abre htmlcov/index.html en el navegador
```

---

## 📦 Tests incluidos

### **1. AbonoCapitalValidacionTestCase** (Tests unitarios de validación)

#### `test_validacion_exitosa_plan_cuadrado`
- **Qué prueba:** Validación pasa cuando el plan está perfectamente cuadrado
- **Escenario:** Capital del plan = 100M, recaudado = 30M, pendiente = 70M, cuotas cuadradas
- **Resultado esperado:** `es_valido = True`, sin errores

#### `test_validacion_falla_capital_plan_no_coincide`
- **Qué prueba:** Validación falla cuando el capital del plan no coincide con saldos
- **Escenario:** Capital plan = 100M, capital saldos = 98M
- **Resultado esperado:** `es_valido = False`, error `CAPITAL_PLAN_MISMATCH`

#### `test_validacion_falla_cuotas_descuadradas`
- **Qué prueba:** Validación falla cuando hay cuotas descuadradas
- **Escenario:** Cuota con capital=500k, interés=25k, cuota=530k (debería ser 525k)
- **Resultado esperado:** `es_valido = False`, error `CUOTAS_DESCUADRADAS`

#### `test_validacion_falla_saldo_capital_negativo`
- **Qué prueba:** Validación falla cuando hay saldos de capital negativos
- **Escenario:** 2 cuotas con saldocapital < 0
- **Resultado esperado:** `es_valido = False`, error `SALDO_CAPITAL_NEGATIVO`

---

### **2. AbonoCapitalIntegracionTestCase** (Tests de integración)

#### `test_abono_capital_exitoso_simple`
- **Qué prueba:** Abono a capital exitoso sin cuotas vencidas
- **Escenario:** Recibo de 10M, sin vencidas, validación pasa
- **Resultado esperado:** `should_return = False`, backup creado, validación llamada

#### `test_abono_capital_falla_validacion_rollback_completo`
- **Qué prueba:** Cuando falla la validación, se hace rollback de TODO
- **Escenario:** Recibo de 10M, validación falla con error `CAPITAL_PLAN_MISMATCH`
- **Resultado esperado:**
  - `should_return = True` (aborta)
  - Alert con código `ABONO_CAPITAL_VALIDATION_FAILED`
  - Mensaje incluye "REVERTIDOS"
  - `context_updates['titulo'] = 'Abono a capital rechazado'`

---

### **3. AbonoCapitalRollbackTestCase** (Tests de rollback)

#### `test_rollback_no_deja_registros_huerfanos`
- **Qué prueba:** Si falla el abono, no quedan registros huérfanos
- **Escenario:** Validación falla después de crear registros
- **Resultado esperado:** Conteo de registros no aumenta

---

## 🧪 Cobertura de casos

| Caso | Test | Estado |
|------|------|--------|
| ✅ Validación exitosa | `test_validacion_exitosa_plan_cuadrado` | Implementado |
| ❌ Capital plan ≠ saldos | `test_validacion_falla_capital_plan_no_coincide` | Implementado |
| ❌ Cuotas descuadradas | `test_validacion_falla_cuotas_descuadradas` | Implementado |
| ❌ Saldo capital negativo | `test_validacion_falla_saldo_capital_negativo` | Implementado |
| ✅ Abono exitoso | `test_abono_capital_exitoso_simple` | Implementado |
| ❌ Rollback completo | `test_abono_capital_falla_validacion_rollback_completo` | Implementado |
| 🔄 Sin registros huérfanos | `test_rollback_no_deja_registros_huerfanos` | Implementado |

---

## 🔧 Tecnologías usadas

- **Django TestCase:** Framework de tests de Django
- **TransactionTestCase:** Para tests con múltiples bases de datos
- **unittest.mock:** Para simular objetos y comportamientos
- **patch:** Para reemplazar temporalmente objetos durante los tests

---

## 📝 Notas importantes

### **Bases de datos de prueba**
Django crea automáticamente bases de datos de prueba con el prefijo `test_`:
- `test_andinaso_web` (default)
- `test_developer_casasdeverano` (Casas de Verano) **← Usada en los tests**
- `test_andinaso_sandville` (Sandville Beach)
- etc.

Los tests usan específicamente el alias **'Casas de Verano'**, que apunta a:
- **Producción:** `developer_casasdeverano`
- **Tests:** `test_developer_casasdeverano` (creada automáticamente)

Estas bases de datos de prueba:
- Se crean antes de ejecutar los tests
- Se destruyen después de ejecutar los tests
- **NO afectan las bases de datos de producción**

### **Rollback automático**
Cada test se ejecuta dentro de una transacción que se revierte automáticamente al final, asegurando:
- ✅ Los tests no interfieren entre sí
- ✅ No quedan datos residuales
- ✅ Se puede ejecutar múltiples veces sin problemas

### **Mocks**
Los tests usan mocks (`unittest.mock.patch`) para simular:
- Objetos de modelo (PlanPagos, Recaudos, saldos_adj)
- Queries de base de datos
- Resultados de funciones

Esto permite:
- ✅ Tests más rápidos (no acceden a BD real)
- ✅ Control total del escenario de prueba
- ✅ Tests determinísticos (siempre el mismo resultado)

### **Alias de proyectos**
El sistema usa **database routers** para manejar múltiples bases de datos:
- Cada proyecto (Casas de Verano, Sandville Beach, etc.) tiene su propia BD
- Los modelos de `shared_models.py` usan el router para acceder a la BD correcta
- Durante los tests, Django crea automáticamente versiones de prueba de cada BD
- El parámetro `using='Casas de Verano'` en las queries indica qué BD usar

Ejemplo:
```python
# En producción:
PlanPagos.objects.using('Casas de Verano').filter(adj='ADJ001')
# Accede a: developer_casasdeverano

# En tests:
PlanPagos.objects.using('Casas de Verano').filter(adj='ADJ001')
# Accede a: test_developer_casasdeverano (creada automáticamente)
```

---

## 🐛 Troubleshooting

### **Error: "No module named 'andinasoft.tests'"**
```bash
# Asegúrate de estar en el directorio raíz del proyecto
cd /code
python manage.py test andinasoft.tests
```

### **Error: "Apps aren't loaded yet"**
```bash
# Asegúrate de tener Django configurado correctamente
python manage.py check
```

### **Error: "Database connection error"**
```bash
# Verifica la configuración de DATABASES en settings.py
# Asegúrate de que TEST esté configurado para cada base de datos
```

---

## 📚 Referencias

- [Django Testing Documentation](https://docs.djangoproject.com/en/stable/topics/testing/)
- [unittest.mock Documentation](https://docs.python.org/3/library/unittest.mock.html)
- [Django TransactionTestCase](https://docs.djangoproject.com/en/stable/topics/testing/tools/#transactiontestcase)

---

## ✅ Próximos pasos

Para expandir la cobertura de tests, considera agregar:
- Tests con cuotas vencidas (PASO 1)
- Tests con múltiples cuotas CO
- Tests de integración con API endpoints
- Tests de performance (tiempo de ejecución)
- Tests con datos reales (usando fixtures)
