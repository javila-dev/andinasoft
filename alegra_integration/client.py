import base64
import json
import time

import requests
from django.conf import settings
from django.core.validators import validate_email
from django.core.exceptions import ValidationError

from alegra_integration.exceptions import AlegraClientError, AlegraConfigurationError


class AlegraMCPClient:
    MCP_URL = 'https://mcp.alegra.com/mcp'
    API_URL = 'https://api.alegra.com/api/v1'
    DEFAULT_GROUPS = 'banks,income-payments,ledger,accounting,contacts,resolutions,retentions'

    def __init__(self, empresa, timeout=90):
        self.empresa = empresa
        self.timeout = timeout
        self._mcp_session_id = None
        self._mcp_initialized = False
        if not getattr(empresa, 'alegra_enabled', False):
            raise AlegraConfigurationError(f'La empresa {empresa.pk} no tiene Alegra habilitado.')
        if not getattr(empresa, 'alegra_token', None):
            raise AlegraConfigurationError(f'La empresa {empresa.pk} no tiene token de Alegra configurado.')

    @property
    def token(self):
        return self.empresa.alegra_token.strip()

    def get_authorization_header(self):
        """Mismo encabezado que REST (Basic) para descargar adjuntos por URL de la API."""
        return self._rest_auth_header()

    def _auth_header(self):
        # MCP expects the same Basic auth format as the REST API.
        return self._rest_auth_header()

    def _rest_auth_header(self):
        raw = self.token
        if raw.lower().startswith('basic '):
            # Validate the credential format inside Basic if possible.
            try:
                b64 = raw.split(' ', 1)[1].strip()
                decoded = base64.b64decode(b64).decode('utf-8', errors='ignore')
                if ':' not in decoded:
                    raise AlegraConfigurationError(
                        'Credenciales Alegra inválidas: Basic auth debe ser base64("correo:token").'
                    )
            except AlegraConfigurationError:
                raise
            except Exception:
                # If we can't decode, let the request fail with Alegra's response.
                pass
            return raw
        try:
            base64.b64decode(raw, validate=True)
            # raw looks like base64; validate it decodes to "correo:token"
            try:
                decoded = base64.b64decode(raw).decode('utf-8', errors='ignore')
                if ':' not in decoded:
                    raise AlegraConfigurationError(
                        'Credenciales Alegra inválidas: el token base64 debe corresponder a "correo:token".'
                    )
            except AlegraConfigurationError:
                raise
            except Exception:
                # If decoding fails unexpectedly, still attempt as Basic.
                pass
            return f'Basic {raw}'
        except Exception:
            # raw is not base64. It must be "correo:token" (not just the token).
            if ':' not in raw:
                raise AlegraConfigurationError(
                    'Credenciales Alegra inválidas: configure `empresa.alegra_token` como '
                    '"correo@dominio.com:API_TOKEN" (o su base64), no solo el token.'
                )
            # Validate email part early to avoid opaque 401s.
            email_part = raw.split(':', 1)[0].strip()
            try:
                validate_email(email_part)
            except ValidationError:
                raise AlegraConfigurationError(
                    'Credenciales Alegra inválidas: el valor antes de ":" debe ser un correo válido '
                    '(el mismo que aparece en Alegra → Configuración → API - Integraciones).'
                )
            return f'Basic {base64.b64encode(raw.encode("utf-8")).decode("ascii")}'

    def call_tool(self, name, arguments):
        if not self._mcp_initialized:
            self._mcp_initialize()

        payload = {
            'jsonrpc': '2.0',
            'id': 1,
            'method': 'tools/call',
            'params': {'name': name, 'arguments': arguments},
        }

        response, decoded = self._request_with_retry(
            lambda: requests.post(self.MCP_URL, headers=self._mcp_headers(), json=payload, timeout=self.timeout),
            raw=True,
        )

        # Some deployments require initialize; if the session expired, re-init once and retry.
        if isinstance(decoded, dict) and decoded.get('error', {}).get('message') == 'Bad Request: Server not initialized':
            self._mcp_initialized = False
            self._mcp_session_id = None
            self._mcp_initialize()
            response, decoded = self._request_with_retry(
                lambda: requests.post(self.MCP_URL, headers=self._mcp_headers(), json=payload, timeout=self.timeout),
                raw=True,
            )

        self._capture_mcp_session_id(response)
        return self._handle_decoded_response(response, decoded)

    def list_tools(self):
        """Return MCP tools list (best-effort)."""
        if not self._mcp_initialized:
            self._mcp_initialize()
        payload = {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'}
        response, decoded = self._request_with_retry(
            lambda: requests.post(self.MCP_URL, headers=self._mcp_headers(), json=payload, timeout=self.timeout),
            raw=True,
        )
        self._capture_mcp_session_id(response)
        return self._handle_decoded_response(response, decoded)

    def _call_tool_any(self, names, arguments):
        """Try multiple tool names; fall back to dynamic lookup for renamed tools."""
        last_exc = None
        for n in names:
            try:
                return self.call_tool(n, arguments)
            except AlegraClientError as exc:
                last_exc = exc
                if 'Tool not found:' not in str(exc):
                    raise
        # Try to discover an available tool with similar prefix.
        try:
            tools_payload = self.list_tools()
            tools = []
            if isinstance(tools_payload, dict):
                tools = (tools_payload.get('result') or {}).get('tools') or tools_payload.get('tools') or []
            tool_names = []
            for t in tools:
                if isinstance(t, dict) and t.get('name'):
                    tool_names.append(t['name'])
            for n in names:
                prefix = n.split('__', 1)[0] + '__'
                for candidate in tool_names:
                    if candidate.startswith(prefix):
                        return self.call_tool(candidate, arguments)
        except Exception:
            pass
        if last_exc:
            raise last_exc
        raise AlegraClientError('Alegra MCP tool not found.')

    def _mcp_headers(self):
        headers = {
            'Authorization': self._auth_header(),
            'Content-Type': 'application/json',
            'mcp-groups': getattr(settings, 'ALEGRA_MCP_GROUPS', self.DEFAULT_GROUPS),
        }
        if self._mcp_session_id:
            headers['mcp-session-id'] = self._mcp_session_id
        return headers

    def _capture_mcp_session_id(self, response):
        sid = response.headers.get('mcp-session-id') or response.headers.get('Mcp-Session-Id')
        if sid:
            self._mcp_session_id = sid

    def _mcp_initialize(self):
        init_payload = {
            'jsonrpc': '2.0',
            'id': 0,
            'method': 'initialize',
            'params': {
                'protocolVersion': '2024-11-05',
                'capabilities': {},
                'clientInfo': {'name': 'andina-alegra', 'version': '1.0'},
            },
        }
        response, decoded = self._request_with_retry(
            lambda: requests.post(self.MCP_URL, headers=self._mcp_headers(), json=init_payload, timeout=self.timeout),
            raw=True,
        )
        self._capture_mcp_session_id(response)
        self._handle_decoded_response(response, decoded)
        self._mcp_initialized = True

    def rest(self, method, path, *, json_payload=None, files=None):
        headers = {'Authorization': self._rest_auth_header()}
        if files is None:
            headers['Content-Type'] = 'application/json'
        return self._request_with_retry(
            lambda: requests.request(
                method,
                f'{self.API_URL}{path}',
                headers=headers,
                json=json_payload,
                files=files,
                timeout=self.timeout,
            )
        )

    def create_income_payment(self, payload):
        # REST equivalent of MCP incomePayments__createIncomePayment
        return self.rest('POST', '/payments', json_payload=payload)

    def create_journal(self, payload):
        # REST equivalent of MCP accounting__createJournal
        return self.rest('POST', '/journals', json_payload=payload)

    def create_out_payment(self, payload):
        return self.rest('POST', '/payments', json_payload=payload)

    def bank_account_transfer(self, origin_bank_id, payload):
        """
        Transfer between bank accounts within the same Alegra company.
        Endpoint: POST /bank-accounts/{origin}/transfer with body including idDestination.
        """
        origin_bank_id = str(origin_bank_id or '').strip()
        if not origin_bank_id:
            raise AlegraConfigurationError('origin_bank_id es requerido para bank_account_transfer.')
        return self.rest('POST', f'/bank-accounts/{origin_bank_id}/transfer', json_payload=payload)

    def create_bill(self, payload):
        return self.rest('POST', '/bills', json_payload=payload)

    def get_bill(self, bill_id, *, fields=None):
        """
        GET /bills/{id} — opcionalmente ?fields=url,stampFiles,... (ver API Alegra).
        """
        bid = str(bill_id or '').strip()
        if not bid:
            raise AlegraConfigurationError('bill_id es requerido para get_bill.')
        path = f'/bills/{bid}'
        if fields:
            path = f'{path}?fields={fields}'
        return self.rest('GET', path)

    def post_webhooks_subscription(self, event, url):
        """
        POST /webhooks/subscriptions — crea suscripción; devuelve (status_code, body_json)
        sin lanzar error HTTP (para persistir respuestas 4xx en UI).
        """
        body = {'event': event, 'url': url}
        response, payload = self._request_with_retry(
            lambda: requests.post(
                f'{self.API_URL}/webhooks/subscriptions',
                headers={
                    'Authorization': self._rest_auth_header(),
                    'Content-Type': 'application/json',
                },
                json=body,
                timeout=self.timeout,
            ),
            raw=True,
        )
        return response.status_code, payload

    def list_webhooks_subscriptions(self):
        """
        GET /webhooks/subscriptions — lista suscripciones de webhooks.
        Devuelve lista de objetos {id,event,url} (o wrapper con data, según cuenta).
        """
        return self.rest('GET', '/webhooks/subscriptions')

    def delete_webhooks_subscription(self, subscription_id):
        """
        DELETE /webhooks/subscriptions/{id} — elimina una suscripción.
        """
        sid = str(subscription_id or '').strip()
        if not sid:
            raise AlegraConfigurationError('subscription_id es requerido para delete_webhooks_subscription.')
        return self.rest('DELETE', f'/webhooks/subscriptions/{sid}')

    def attach_bill_file(self, bill_id, file_obj):
        return self.rest('POST', f'/bills/{bill_id}/attachment', files={'file': file_obj})

    def get_contacts_page(self, start=0, limit=30, contact_type=None):
        qs = f'start={start}&limit={limit}'
        if contact_type:
            qs += f'&type={requests.utils.quote(str(contact_type))}'
        return self.rest('GET', f'/contacts?{qs}')

    def search_contacts(self, query, *, start=0, limit=30):
        qs = f'start={int(start)}&limit={int(limit)}&query={requests.utils.quote(str(query or ""))}'
        return self.rest('GET', f'/contacts?{qs}')

    def create_contact(self, payload):
        return self.rest('POST', '/contacts', json_payload=payload)

    def get_all_contacts(self, contact_type=None):
        """
        Returns contacts from Alegra.
        Some accounts/tools behave differently with providers vs clients, so when contact_type is None
        we fetch both 'client' and 'provider' explicitly and de-duplicate.
        """
        types = [contact_type] if contact_type else ['client', 'provider']
        by_id = {}

        for t in types:
            start = 0
            limit = 30
            while True:
                page = self.get_contacts_page(start=start, limit=limit, contact_type=t)
                if isinstance(page, dict) and 'data' in page:
                    page = page['data']
                if not isinstance(page, list) or not page:
                    break
                for c in page:
                    cid = str(c.get('id')) if isinstance(c, dict) else None
                    if cid:
                        by_id[cid] = c
                if len(page) < limit:
                    break
                start += limit

        return list(by_id.values())

    def _rest_list_all(self, path, *, limit=30, extra_params=None):
        """
        Fetches all pages for REST list endpoints that support start/limit.
        Works with both plain list responses and {metadata,data} wrappers.
        """
        extra_params = extra_params or {}
        items = []
        start = 0
        while True:
            params = {'start': start, 'limit': limit, **extra_params}
            qs = '&'.join([f'{k}={requests.utils.quote(str(v))}' for k, v in params.items() if v is not None])
            page = self.rest('GET', f'{path}?{qs}')
            if isinstance(page, dict) and 'data' in page:
                page = page['data']
            if not isinstance(page, list) or not page:
                break
            items.extend(page)
            if len(page) < limit:
                break
            start += limit
        return items

    def get_reference_data(self):
        # Prefer REST for reference data: it's more stable than MCP and has fixed endpoints.
        # NOTE: Not all endpoints support start/limit pagination. In particular, /categories is filter-based.
        categories = self.rest('GET', '/categories?format=plain')
        if isinstance(categories, dict) and 'data' in categories:
            categories = categories['data']
        if not isinstance(categories, list):
            categories = []
        return {
            'banks': self._rest_list_all('/bank-accounts'),
            'categories': categories,
            'cost_centers': self._rest_list_all('/cost-centers'),
            # Numeraciones contables (journals): Alegra usa idNumeration (no siempre coincide con number-templates).
            # No existe un endpoint público claro para listarlas, así que extraemos las numeraciones visibles
            # desde los comprobantes recientes con fields=numberTemplate,type.
            'journal_numerations': self._rest_journal_numerations(),
            # Numeraciones (incluye resolutionNumber, prefix, nextInvoiceNumber, etc.)
            'number_templates': {
                'invoice': self._rest_list_all('/number-templates', extra_params={'documentType': 'invoice'}),
                'estimate': self._rest_list_all('/number-templates', extra_params={'documentType': 'estimate'}),
                'transactionIn': self._rest_list_all('/number-templates', extra_params={'documentType': 'transactionIn'}),
                'transactionOut': self._rest_list_all('/number-templates', extra_params={'documentType': 'transactionOut'}),
                'creditNote': self._rest_list_all('/number-templates', extra_params={'documentType': 'creditNote'}),
                'debitNote': self._rest_list_all('/number-templates', extra_params={'documentType': 'debitNote'}),
                'incomeDebitNote': self._rest_list_all('/number-templates', extra_params={'documentType': 'incomeDebitNote'}),
            },
        }

    def _rest_journal_numerations(self, *, max_pages=120, stop_after_pages_without_new=10):
        """
        Best-effort list of journal numerations (idNumeration) by scanning recent journals.
        Returns unique numberTemplate objects: {id, name, prefix, nextNumber?, type?}.
        """
        by_id = {}
        start = 0
        limit = 30  # Alegra journals GET max is 30
        pages = 0
        no_new_pages = 0
        while pages < int(max_pages or 0):
            page = self.rest('GET', f'/journals?start={start}&limit={limit}&order_direction=DESC&fields=numberTemplate,type')
            if isinstance(page, dict) and 'data' in page:
                page = page['data']
            page = page if isinstance(page, list) else []
            if not page:
                break
            before = len(by_id)
            for j in page:
                nt = (j or {}).get('numberTemplate')
                if isinstance(nt, dict):
                    nid = nt.get('id')
                    if nid:
                        # include journal type (Ingresos/Impuestos/etc) if present
                        t = (j or {}).get('type')
                        obj = dict(nt)
                        if t and 'type' not in obj:
                            # Some responses include "type" as object; normalize to displayable string.
                            if isinstance(t, dict):
                                t = t.get('name') or t.get('label') or t.get('code') or str(t.get('id') or '')
                            obj['type'] = str(t)
                        by_id[str(nid)] = obj
            after = len(by_id)
            if after == before:
                no_new_pages += 1
            else:
                no_new_pages = 0
            if no_new_pages >= int(stop_after_pages_without_new or 0):
                break
            if len(page) < limit:
                break
            start += limit
            pages += 1
        return list(by_id.values())

    def _request_with_retry(self, make_request, *, max_retries=5, raw=False):
        """
        Alegra rate-limit can surface as:
        - HTTP 429
        - HTTP 400 with payload: {"code": 429, "message": "...", "headers": {"x-rate-limit-reset": <seconds>}}
        """
        attempt = 0
        while True:
            try:
                response = make_request()
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
                if attempt >= max_retries:
                    raise AlegraClientError(f'Alegra request failed after retries: {exc}')
                # Exponential backoff on transient network issues
                sleep_s = min(30.0, 2.0 ** attempt)
                time.sleep(sleep_s)
                attempt += 1
                continue
            try:
                payload = response.json()
            except json.JSONDecodeError:
                payload = {'raw': response.text}

            # Retry on transient gateway/service errors
            if response.status_code in (502, 503, 504) and attempt < max_retries:
                sleep_s = min(60.0, 2.0 ** attempt)
                time.sleep(sleep_s)
                attempt += 1
                continue

            retry_after = None
            if isinstance(payload, dict) and payload.get('code') == 429:
                retry_after = (payload.get('headers') or {}).get('x-rate-limit-reset')
            if response.status_code == 429:
                retry_after = retry_after or response.headers.get('Retry-After') or response.headers.get('x-rate-limit-reset')

            if retry_after is not None and attempt < max_retries:
                try:
                    sleep_s = float(retry_after)
                except Exception:
                    sleep_s = 1.0
                # Small backoff to reduce bursts
                sleep_s = max(1.0, sleep_s) + min(2.0, attempt * 0.5)
                time.sleep(sleep_s)
                attempt += 1
                continue

            if raw:
                return response, payload
            return self._handle_decoded_response(response, payload)

    def _handle_decoded_response(self, response, payload):
        if response.status_code >= 400:
            raise AlegraClientError(f'Alegra HTTP {response.status_code}: {payload}')
        if isinstance(payload, dict) and payload.get('error'):
            raise AlegraClientError(f'Alegra error: {payload["error"]}')
        return payload
