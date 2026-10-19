# Telefonía: llamadas salientes desde el panel de Chatwoot (Twilio)

App `telefonia`. El agente pulsa **Llamar** (el botón verde redondo) en el panel de Andinasoft dentro de Chatwoot y llama al cliente desde el navegador, con una línea de Andinasoft como identificador. Al colgar, la llamada queda como nota privada en la conversación y el resultado, con un clic, como seguimiento del negocio.

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
6. **Resultado en un clic.** Al colgar, el agente elige: No contestó, Compromiso de pago (fecha y valor), Volver a llamar, Dice que ya pagó, Número equivocado u Otro, con un comentario opcional. `api/llamadas/<id>/resultado/` hace esto **una sola vez por llamada**:
   - guarda el resultado en la `Llamada`;
   - crea el seguimiento del negocio elegido en el panel: forma «LLamada», tipo «Cobro» («Anotacion» si el número es equivocado), con el compromiso si lo hay;
   - deja una nota privada en la conversación.

   El negocio tiene que ser del cliente de la llamada y de un proyecto del usuario. Si en el panel no se eligió negocio, el resultado queda en la llamada y en la nota, y el botón «Completar en el panel» abre la pestaña Seguimiento.
7. **Número equivocado.** Queda en *Números descartados*, para ese cliente o, si salió de Chatwoot, para ese contacto, y el softphone deja de ofrecerlo. Para volver a ofrecerlo, se borra en el admin.

## Links de pago Wompi (panel, pestaña Cartera)

Botón **«Enviar link de pago»**. Aparece si el proyecto tiene un comercio Wompi configurado. Usa el mismo permiso del panel («Puede usar el panel de Chatwoot»): no hay permisos aparte. No aparece en negocios desistidos.

- El agente pone el valor (por defecto el vencido; atajos «Vencido» y «Cancelar hoy») y elige **Enviar al cliente** o **Solo crear el link**.
- El servidor rechaza valores por debajo de `WOMPI_LINK_VALOR_MINIMO` o por encima de lo que el negocio cancela hoy, con las mismas cifras del estado de cuenta.
- El link es de **un solo pago**, con valor fijo, `sku` = ADJ y vencimiento a `WOMPI_LINK_VIGENCIA_HORAS` (72 h).
- El mensaje se envía por la API de Chatwoot. En WhatsApp, si pasaron más de 24 h desde el último mensaje del cliente, Chatwoot no lo entrega: el panel lo avisa y ofrece copiar el link o el mensaje.
- Cada link queda en *Links de pago Wompi* (proyecto, ADJ, valor, agente, conversación). Su `link_id` es el `id_link_pago` que trae `WompiMovement` al conciliar, así se sabe a qué negocio corresponde el pago.

Configuración:
1. Variable `WOMPI_LLAVES_PRIVADAS="alias1=prv_prod_…;alias2=prv_prod_…"`, una llave privada por comercio Wompi. Con `prv_test_…` se usa el sandbox.
2. En **Admin → Panel de Chatwoot → Comercios Wompi**, crear cada comercio con su alias y elegir sus proyectos de la lista. A cada proyecto se le puede subir su **logo**: se guarda en el almacenamiento público y va como `image_url` en el link, así el cliente ve el logo del proyecto en la página de pago. Sin S3, la URL se completa con `ANDINA_PUBLIC_BASE_URL`, que tiene que ser `https`; si no, el link sale sin logo.
3. Los agentes solo necesitan el permiso del panel («Puede usar el panel de Chatwoot»).
4. Opcional: `WOMPI_LINK_REDIRECT_URL`, la página a la que vuelve el cliente después de pagar.

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

Permiso: **un solo permiso para todo el panel**, «Puede usar el panel de Chatwoot» (`chatwoot_panel.usar_panel_chatwoot`). Quien lo tiene ve la cartera, llama y envía links de pago; no hay permisos individuales.

### Líneas salientes (varios números)

Las líneas se configuran en **Admin → Telefonía → Líneas salientes**, cada una con nombre, número E.164, si está activa y su orden. Cada número tiene que estar **comprado o verificado en Twilio**; si no, Twilio rechaza la llamada y queda como fallida.

- **La línea siempre es automática**: el agente no la elige. El servidor usa la línea activa que lleva más tiempo sin usarse, así las llamadas se reparten entre todas. El softphone muestra por cuál salió.
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
