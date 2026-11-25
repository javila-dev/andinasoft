# Tests del abono a capital

La lógica vive en `andinasoft/abono_capital_service.py` y la usan el recibo nuevo
(`_guardar_recaudo`) y la reaplicación de recaudos pendientes (`detalle_adjudicacion`,
`todo == 'reaplicar_recaudos'`).

## Cómo correrlos

Los tests son `SimpleTestCase` (sin BD: la BD de prueba no se puede crear desde las
migraciones). Dentro del contenedor:

```bash
docker exec andina_stable-web-1 python manage.py test andinasoft.tests --noinput
```

## Qué cubren

- `RecalcularCuotasTests`: el recálculo del plan tras el abono.
  - Acorta el plazo con la misma cuota fija y cierra en la última cuota.
  - Da exactamente lo mismo que el algoritmo anterior cuando no hay anticipos
    (300 planes aleatorios).
  - Con anticipos en cuotas futuras: ninguna cuota queda por debajo de lo pagado,
    nunca se borra una cuota con recaudos y el capital total se conserva.
  - Falla si una cuota no cubre su interés o si las cuotas no alcanzan.
- `DistribuirEnVencidasTests`: el pago de cuotas vencidas (mora, interés, capital).
- `GuardarRecaudoAbonoTests`: si el abono se rechaza, el recibo nuevo no se crea.

## Lo que no cubren (verificar en desarrollo)

El flujo completo contra la BD (crear la cuota CO, validar el plan, restaurar
`plan_pagos` si algo falla) se prueba con scripts contra la BD local, restaurando el
contrato al final. `plan_pagos` es MyISAM: `transaction.atomic` no lo revierte, por eso
el servicio guarda una foto del plan y la restaura si el abono falla.
