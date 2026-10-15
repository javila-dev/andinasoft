"""
Cliente JSON-RPC para las herramientas de reportes del servidor MCP de Alegra.

Usa el Bearer OAuth de `alegra_integration.oauth` (no el Basic de la API REST).
Las respuestas pueden llegar como JSON plano o como SSE (`text/event-stream`).
"""
import json
import logging
import time

import requests

from alegra_integration import oauth
from alegra_integration.exceptions import AlegraClientError

logger = logging.getLogger('alegra_integration')


class AlegraReportsClient:
    MCP_URL = 'https://mcp.alegra.com/'
    GROUPS = 'reports'
    PROTOCOL_VERSION = '2025-03-26'
    MAX_RATE_LIMIT_RETRIES = 4

    def __init__(self, empresa, timeout=180):
        self.empresa = empresa
        self.timeout = timeout
        self._session_id = None
        self._initialized = False
        self._rpc_id = 0

    def _headers(self, access_token):
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json, text/event-stream',
            'mcp-groups': self.GROUPS,
        }
        if self._session_id:
            headers['mcp-session-id'] = self._session_id
        return headers

    @staticmethod
    def _decode(response):
        ctype = (response.headers.get('content-type') or '').lower()
        text = response.text or ''
        if 'text/event-stream' in ctype:
            # Tomar el último mensaje JSON-RPC del stream.
            last = None
            for line in text.splitlines():
                if line.startswith('data:'):
                    chunk = line[5:].strip()
                    if chunk:
                        try:
                            last = json.loads(chunk)
                        except ValueError:
                            continue
            return last
        if not text.strip():
            return None
        try:
            return response.json()
        except ValueError:
            return {'raw': text[:1000]}

    def _post(self, payload, notification=False):
        token = oauth.get_access_token(self.empresa)
        refreshed = False
        rate_retries = 0
        while True:
            try:
                resp = requests.post(self.MCP_URL, headers=self._headers(token), json=payload, timeout=self.timeout)
            except requests.RequestException as exc:
                raise AlegraClientError(f'Error de red llamando el MCP de Alegra: {exc}') from exc
            if resp.status_code == 401 and not refreshed:
                token = oauth.get_access_token(self.empresa, force_refresh=True)
                refreshed = True
                continue
            if resp.status_code == 429 and rate_retries < self.MAX_RATE_LIMIT_RETRIES:
                wait = int(resp.headers.get('X-Rate-Limit-Reset') or resp.headers.get('Retry-After') or 10)
                time.sleep(min(max(wait, 1), 65))
                rate_retries += 1
                continue
            break
        sid = resp.headers.get('mcp-session-id')
        if sid:
            self._session_id = sid
        if notification:
            return None
        decoded = self._decode(resp)
        if resp.status_code >= 400:
            raise AlegraClientError(f'MCP Alegra respondió {resp.status_code}: {decoded}')
        if isinstance(decoded, dict) and decoded.get('error'):
            raise AlegraClientError(f'MCP Alegra error: {decoded["error"]}')
        return decoded

    def _initialize(self):
        self._post({
            'jsonrpc': '2.0',
            'id': self._next_id(),
            'method': 'initialize',
            'params': {
                'protocolVersion': self.PROTOCOL_VERSION,
                'capabilities': {},
                'clientInfo': {'name': 'andinasoft', 'version': '1.0'},
            },
        })
        self._post({'jsonrpc': '2.0', 'method': 'notifications/initialized'}, notification=True)
        self._initialized = True

    def _next_id(self):
        self._rpc_id += 1
        return self._rpc_id

    def list_tools(self):
        if not self._initialized:
            self._initialize()
        decoded = self._post({'jsonrpc': '2.0', 'id': self._next_id(), 'method': 'tools/list'})
        return ((decoded or {}).get('result') or {}).get('tools') or []

    def call_tool(self, name, arguments):
        """Devuelve el resultado de la herramienta ya decodificado (dict/list) cuando es posible."""
        if not self._initialized:
            self._initialize()
        decoded = self._post({
            'jsonrpc': '2.0',
            'id': self._next_id(),
            'method': 'tools/call',
            'params': {'name': name, 'arguments': arguments},
        })
        result = (decoded or {}).get('result') or {}
        if result.get('isError'):
            raise AlegraClientError(f'La herramienta {name} devolvió error: {result.get("content")}')
        if result.get('structuredContent') is not None:
            return result['structuredContent']
        texts = [c.get('text') for c in (result.get('content') or []) if isinstance(c, dict) and c.get('type') == 'text']
        if len(texts) == 1:
            try:
                return json.loads(texts[0])
            except (TypeError, ValueError):
                return texts[0]
        return result

    def third_party_trial_balance(self, from_date, to_date, category_id=None, client_id=None, include_zero=False):
        args = {
            'fromDate': str(from_date),
            'toDate': str(to_date),
            'includeZeroBalanceAccounts': bool(include_zero),
        }
        if category_id:
            args['idCategory'] = int(category_id)
        if client_id:
            args['idClient'] = int(client_id)
        return self.call_tool('reports__getThirdPartyTrialBalance', args)
