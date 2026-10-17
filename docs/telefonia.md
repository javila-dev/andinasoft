# Telefonía: llamadas salientes desde el panel de Chatwoot (Twilio)

App `telefonia`. El agente pulsa **📞 Llamar** en el panel de Andinasoft dentro de Chatwoot y llama al cliente desde el navegador, con el número de Andinasoft como identificador. Al colgar, la llamada queda como nota privada en la conversación y, si el agente quiere, como seguimiento del negocio.

Por ahora solo hay llamadas **salientes** y solo a Colombia (celulares 3XX y fijos 60X).

## Cómo funciona

1. **Panel (iframe de Chatwoot).** Botón «Llamar» junto al cliente. Abre la ventana `/telefonia/softphone/` y le pasa por `postMessage` la conversación, el contacto y la cédula del cliente identificado. El iframe de Chatwoot no tiene permiso de micrófono (`allow="microphone"`), por eso la llamada no puede vivir ahí.
2. **Softphone (ventana de primer nivel).** Usa la sesión normal de Andinasoft, con cookie y CSRF, como `/chatwoot/conectar/`. Pide los números a `api/destinos/`: el servidor confirma la conversación con la API de Chatwoot y ofrece el número de la conversación y los teléfonos del cliente en `clientes`, enmascarados. **El navegador solo elige un id; el número lo pone el servidor.**
3. **`api/llamar/`.**
   - Valida el permiso, el límite por hora, la conversación y el destino.
   - Crea la `Llamada` (estado `iniciando`).
   - Devuelve un token de Twilio que sirve solo para llamadas salientes y dura 10 minutos.
4. **Twilio → `twilio/voz/`.** Solo marca si la `Llamada` existe, es de ese usuario, sigue en `iniciando`, se pidió hace menos de 2 minutos y no se usó antes. Responde `<Dial callerId=TELEFONIA_CALLER_ID>` al número guardado.
5. **Twilio → `twilio/estado/`.** Recibe los estados `initiated`, `answered` y `completed` del tramo hacia el cliente, más el estado del tramo del navegador, configurado en la TwiML App. Cierra la llamada **una sola vez** (completada, ocupado, no contestó, cancelada o fallida) y deja la nota privada en la conversación.
6. **Fin.** El softphone muestra el resultado y ofrece «Registrar seguimiento». El panel abre la pestaña Seguimiento con «Llamada» como forma de contacto.

Todos los webhooks de Twilio exigen la firma `X-Twilio-Signature`. Twilio firma la URL pública exacta, así que hay que configurar `TELEFONIA_PUBLIC_BASE_URL` (o `ANDINA_PUBLIC_BASE_URL`) con el `https://dominio` que ve Twilio.

## Configuración en Twilio (una vez)

1. **Cuenta pagada.** Con una cuenta de prueba (trial) solo se puede llamar a números verificados.
2. **Voice → Settings → Geo permissions:** dejar habilitado **solo Colombia**. Así se evita el fraude de llamadas internacionales.
3. **Billing:** recarga automática con límite.
4. **Número para el identificador (caller ID)**, una de dos opciones:
   - **Comprar un número colombiano en Twilio:** es lo más confiable. Pide un *regulatory bundle* con el certificado de Cámara de Comercio y un comprobante de dirección local.
   - **Verificar un número propio de Andinasoft** en *Phone Numbers → Verified Caller IDs*. No requiere trámite, pero Twilio no garantiza que el operador lo muestre.

   Antes de decidir, probar con celulares Claro, Movistar y Tigo qué número le aparece al cliente.
5. **API Key:** *Account → API keys → Create*, tipo Standard. Guardar el SID (`SK…`) y el secreto.
6. **TwiML App:** *Voice → TwiML Apps → Create*.
   - Voice Request URL: `https://<andinasoft>/telefonia/twilio/voz/` (HTTP POST)
   - Status Callback URL: `https://<andinasoft>/telefonia/twilio/estado/`

## Configuración en Andinasoft

Variables de entorno (`.env`):

| Variable | Valor |
|---|---|
| `TWILIO_ACCOUNT_SID` | `AC…` |
| `TWILIO_AUTH_TOKEN` | Auth token de la cuenta (valida la firma de los webhooks) |
| `TWILIO_API_KEY_SID` / `TWILIO_API_KEY_SECRET` | API Key del paso 5 |
| `TWILIO_TWIML_APP_SID` | `AP…` del paso 6 |
| `TELEFONIA_CALLER_ID` | Respaldo: número que ve el cliente (`+57…`) si no hay líneas activas en el admin |
| `TELEFONIA_PUBLIC_BASE_URL` | `https://dominio-publico` (vacío = `ANDINA_PUBLIC_BASE_URL`) |
| `TELEFONIA_GRABAR` | `false` por defecto. Con `true` se graba y el cliente oye «Esta llamada puede ser grabada» al contestar (Ley 1581) |
| `TELEFONIA_MAX_LLAMADAS_HORA` | Límite por usuario (40) |
| `TELEFONIA_DURACION_MAXIMA` | Segundos máximos por llamada (3600) |
| `TWILIO_VOICE_SDK_URL` | Opcional. SDK de voz; por defecto `@twilio/voice-sdk@2.18.5` en jsDelivr |

Despliegue:

```bash
pip install -r requirements.txt
python manage.py migrate telefonia
```

Permiso: dar **«telefonia | Llamada | Puede hacer llamadas desde el panel de Chatwoot»** a los usuarios o grupos que llaman. El panel de Chatwoot sigue pidiendo su propio permiso.

### Líneas salientes (varios números)

Las líneas se configuran en **Admin → Telefonía → Líneas salientes**, cada una con nombre, número E.164, si está activa y su orden. Cada número tiene que estar **comprado o verificado en Twilio**; si no, Twilio rechaza la llamada y queda como fallida.

- En el softphone, **«Llamar desde»** ofrece **Automático (rota entre las líneas)** y cada línea activa. La elección se recuerda en el navegador del agente.
- En automático se usa la línea activa que lleva más tiempo sin usarse, así las llamadas se reparten.
- Cada llamada guarda el número y el nombre de la línea que vio el cliente, y la nota en Chatwoot dice «desde <línea>».
- Si no hay ninguna línea activa, se usa `TELEFONIA_CALLER_ID`.

Rotar números sirve para repartir carga. No cambia los límites de contacto para cobranza (Ley 2300 de 2023: horarios y frecuencia por deudor).

Nginx: las rutas `/telefonia/twilio/…` tienen que ser públicas (Twilio no inicia sesión) y no pueden pasar por una autenticación básica.

## Prueba local con ngrok

1. `ngrok http 8000` y `TELEFONIA_PUBLIC_BASE_URL=https://<id>.ngrok-free.app` en el `.env`.
2. En la TwiML App, apuntar las dos URL a ese dominio.
3. Abrir el panel en Chatwoot, conectar, abrir una conversación y pulsar «Llamar».

## Costos de referencia (Twilio Colombia, octubre de 2026)

- Saliente a celular: unos US$0.038/min, más el tramo del navegador.
- Saliente a fijo: unos US$0.07/min.
- Número local: unos US$14/mes.

Confirmar en <https://www.twilio.com/en-us/voice/pricing/co>.

## Pendiente / siguiente fase

- Escuchar las grabaciones desde Andinasoft. Hoy se guarda el `RecordingSid` y se escuchan en la consola de Twilio.
- Llamar desde la ficha del cliente, fuera de Chatwoot.
- Llamadas entrantes.
- Las `Llamada` que se quedan en `iniciando` son intentos que el navegador no llegó a marcar, por ejemplo porque se negó el micrófono. No cuestan nada.
