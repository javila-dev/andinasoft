from decimal import Decimal, ROUND_DOWN

from django.db.models import Sum

from accounting.models import Anticipos, Facturas, Pagos, cuentas_intercompanias, transferencias_companias
from alegra_integration.exceptions import AlegraBuildError
from alegra_integration.mapping import MappingResolver
from alegra_integration.models import AlegraDocument, AlegraMapping
from andinasoft.models import asesores, clientes, cuentas_pagos, empresas
from andinasoft.shared_models import Recaudos, consecutivos, formas_pago


def _money(value):
    return float(Decimal(value or 0).quantize(Decimal('0.01')))


def _date(value):
    return value.isoformat() if value else None


def _nonzero(value):
    return Decimal(value or 0) != 0


class BuiltDocument:
    def __init__(
        self,
        *,
        document_type,
        operation,
        transport,
        source_model,
        source_pk,
        local_key,
        payload,
        attachment=None,
        empresa_id=None,
        proyecto_id=None,
    ):
        self.document_type = document_type
        self.operation = operation
        self.transport = transport
        self.source_model = source_model
        self.source_pk = str(source_pk)
        self.local_key = local_key
        self.payload = payload
        self.attachment = attachment
        self.empresa_id = str(empresa_id) if empresa_id is not None else None
        self.proyecto_id = str(proyecto_id) if proyecto_id is not None else None

    def as_dict(self):
        return {
            'document_type': self.document_type,
            'operation': self.operation,
            'transport': self.transport,
            'source_model': self.source_model,
            'source_pk': self.source_pk,
            'local_key': self.local_key,
            'payload': self.payload,
            'empresa_id': self.empresa_id,
            'proyecto_id': self.proyecto_id,
        }


class ReceiptPaymentBuilder:
    def __init__(self, empresa, proyecto):
        self.empresa = empresa
        self.proyecto = proyecto
        self.resolver = MappingResolver(empresa, proyecto)

    def build(self, receipt):
        if receipt.valor <= 0:
            raise AlegraBuildError('El recibo no tiene valor positivo.')

        titular_id = receipt.idtercero
        try:
            adj = receipt.info_adj()
            if not titular_id:
                titular_id = adj.idtercero1
        except Exception:
            adj = None

        if not titular_id:
            raise AlegraBuildError(f'El recibo {receipt.numrecibo} no tiene tercero/titular identificable.')

        # Some resolver stubs/tests expose numeration(document_code) without kwargs.
        # Real MappingResolver supports `required`, but we keep this call positional and treat missing mapping as optional.
        try:
            numeration_id = self.resolver.numeration('receipt_cash')
        except Exception:
            numeration_id = None
        cost_center_id = self.resolver.cost_center_for_project(required=False)

        fp = formas_pago.objects.using(self.proyecto.pk).filter(descripcion=receipt.formapago).first()
        # Payment method (Alegra enum) should not block preview; fallback by account type.
        payment_method = self.resolver.payment_method(receipt.formapago or 'default', required=False)
        if fp and getattr(fp, 'cuenta_asociada_id', None):
            # IMPORTANT: `formas_pago` lives in the project DB, but `cuentas_pagos` lives in the main DB.
            # Avoid dereferencing fp.cuenta_asociada (would query the wrong DB).
            cuenta = cuentas_pagos.objects.filter(pk=fp.cuenta_asociada_id).first()
            if cuenta:
                if not payment_method:
                    payment_method = 'cash' if getattr(cuenta, 'es_caja', False) else 'transfer'
                bank_account_id = self.resolver.bank_account_for_account(cuenta)
            else:
                if not payment_method:
                    payment_method = 'transfer'
                bank_account_id = self.resolver.get(
                    AlegraMapping.BANK_ACCOUNT,
                    local_code=f'{self.proyecto.pk}:{receipt.formapago or "default"}',
                )
        else:
            if not payment_method:
                payment_method = 'transfer'
            bank_account_id = self.resolver.get(
                AlegraMapping.BANK_ACCOUNT,
                local_code=f'{self.proyecto.pk}:{receipt.formapago or "default"}',
            )

        # Build a journal (POST /journals) so we can split credit per titular and attach a client per line,
        # and so we can use "Numeraciones contables" (idNumeration) from Alegra.
        total = Decimal(receipt.valor or 0).quantize(Decimal('0.01'))
        if total <= 0:
            raise AlegraBuildError('El recibo no tiene valor positivo.')

        titular_ids = []
        if adj is not None:
            for x in (getattr(adj, 'idtercero1', None), getattr(adj, 'idtercero2', None), getattr(adj, 'idtercero3', None), getattr(adj, 'idtercero4', None)):
                x = (x or '').strip() if isinstance(x, str) else (str(x).strip() if x is not None else '')
                if x and x not in titular_ids:
                    titular_ids.append(x)
        if titular_id and str(titular_id).strip() and str(titular_id).strip() not in titular_ids:
            titular_ids.insert(0, str(titular_id).strip())
        if not titular_ids:
            titular_ids = [str(titular_id).strip()]

        titular_name = ''
        try:
            titular = clientes.objects.filter(pk=titular_ids[0]).first()
            titular_name = (getattr(titular, 'nombrecompleto', '') or '').strip()
        except Exception:
            titular_name = ''
        titular_name = (titular_name or '').upper().strip()

        desc = f'RECIBO {receipt.numrecibo} {self.proyecto.pk} {titular_name}'.strip()
        concepto = (receipt.concepto or '').strip()
        observations = desc if not concepto else f'{desc} - {concepto}'

        # Debit account: bank/cash category from payment form's associated local account, when available.
        debit_account = None
        if fp and getattr(fp, 'cuenta_asociada_id', None):
            cuenta = cuentas_pagos.objects.filter(pk=fp.cuenta_asociada_id).first()
            if cuenta and getattr(cuenta, 'nro_cuentacontable', None):
                debit_account = self.resolver.category_for_code(cuenta.nro_cuentacontable)
        if not debit_account:
            debit_account = self.resolver.get(
                AlegraMapping.CATEGORY,
                local_code=f'bank_category:{self.proyecto.pk}:{receipt.formapago or "default"}',
            )

        # Credit account: configured "anticipos de clientes"
        credit_account = self.resolver.get(AlegraMapping.CATEGORY, local_code='receipt_client_advance')

        n = max(1, len(titular_ids))
        base = (total / Decimal(n)).quantize(Decimal('0.01'), rounding=ROUND_DOWN)
        remainder = total - (base * n)
        amounts = [base] * n
        if remainder != 0:
            amounts[0] = (amounts[0] + remainder).quantize(Decimal('0.01'))

        entries = [
            {
                'id': debit_account,
                'description': desc[:255],
                'debit': float(total),
            }
        ]
        for t_id, amt in zip(titular_ids, amounts):
            client_id = self.resolver.contact_for_cliente(t_id)
            entries.append(
                {
                    'id': credit_account,
                    'description': desc[:255],
                    'credit': float(amt),
                    'client': {'id': client_id},
                }
            )
        if cost_center_id:
            for e in entries:
                e['costCenter'] = {'id': cost_center_id}

        payload = {
            'date': _date(receipt.fecha_pago or receipt.fecha),
            'reference': f'RC-{self.proyecto.pk}-{receipt.numrecibo}',
            'observations': observations[:500],
            'entries': entries,
        }
        if numeration_id:
            payload['idNumeration'] = numeration_id

        return BuiltDocument(
            document_type='receipt',
            operation='accounting__createJournal',
            transport=AlegraDocument.ALEGRA_REST,
            source_model='andinasoft.Recaudos_general',
            source_pk=receipt.pk,
            local_key=f'receipt:{self.proyecto.pk}:{receipt.numrecibo}',
            payload=payload,
        )

    def local_payload(self, receipt):
        """
        Local (Andinasoft) representation of the asiento for debugging in UI.
        Does not require any Alegra mappings.
        """
        titular_id = getattr(receipt, 'idtercero', '') or ''
        adj = None
        try:
            adj = receipt.info_adj()
        except Exception:
            adj = None

        titular_ids = []
        if adj is not None:
            for x in (getattr(adj, 'idtercero1', None), getattr(adj, 'idtercero2', None), getattr(adj, 'idtercero3', None), getattr(adj, 'idtercero4', None)):
                x = (x or '').strip() if isinstance(x, str) else (str(x).strip() if x is not None else '')
                if x and x not in titular_ids:
                    titular_ids.append(x)
        if titular_id and str(titular_id).strip() and str(titular_id).strip() not in titular_ids:
            titular_ids.insert(0, str(titular_id).strip())
        titular_ids = titular_ids or ([str(titular_id).strip()] if titular_id else [])

        total = Decimal(getattr(receipt, 'valor', 0) or 0).quantize(Decimal('0.01'))
        n = max(1, len(titular_ids) or 1)
        base = (total / Decimal(n)).quantize(Decimal('0.01'), rounding=ROUND_DOWN)
        remainder = total - (base * n)
        amounts = [base] * n
        if remainder != 0:
            amounts[0] = (amounts[0] + remainder).quantize(Decimal('0.01'))

        # Try to get local bank accounting code (nro_cuentacontable) via formas_pago -> cuentas_pagos.
        debit_code = None
        try:
            fp = formas_pago.objects.using(self.proyecto.pk).filter(descripcion=getattr(receipt, 'formapago', None)).first()
            if fp and getattr(fp, 'cuenta_asociada_id', None):
                cuenta = cuentas_pagos.objects.filter(pk=fp.cuenta_asociada_id).first()
                if cuenta and getattr(cuenta, 'nro_cuentacontable', None):
                    debit_code = str(cuenta.nro_cuentacontable)
        except Exception:
            debit_code = None

        desc_t1 = ''
        try:
            if titular_ids:
                t = clientes.objects.filter(pk=titular_ids[0]).first()
                desc_t1 = (getattr(t, 'nombrecompleto', '') or '').strip().upper()
        except Exception:
            desc_t1 = ''

        return {
            'tipo': 'recibo_caja',
            'proyecto': getattr(self.proyecto, 'pk', None),
            'numrecibo': getattr(receipt, 'numrecibo', None),
            'fecha': _date(getattr(receipt, 'fecha', None)),
            'fecha_pago': _date(getattr(receipt, 'fecha_pago', None)),
            'forma_pago': getattr(receipt, 'formapago', None),
            'debit_account_code': debit_code,  # contable local si existe
            'credit_account_config': 'receipt_client_advance',  # se configura en UI (Anticipo clientes)
            'concepto': getattr(receipt, 'concepto', None),
            'titulares': [
                {'id': tid, 'valor': float(amt)}
                for tid, amt in zip(titular_ids, amounts)
            ],
            'total': float(total),
            'descripcion': f'RECIBO {getattr(receipt, "numrecibo", "")} {getattr(self.proyecto, "pk", "")} {desc_t1}'.strip(),
        }

class CommissionBuilder:
    def __init__(self, empresa, proyecto):
        self.empresa = empresa
        self.proyecto = proyecto
        self.resolver = MappingResolver(empresa, proyecto)

    def build(self, commission):
        try:
            asesor = asesores.objects.get(pk=commission.idgestor)
        except asesores.DoesNotExist:
            raise AlegraBuildError(f'No existe asesor {commission.idgestor}.')
        if asesor.tipo_asesor == 'Interno':
            return InternalCommissionAdvanceBuilder(self.empresa, self.proyecto, self.resolver).build(commission, asesor)
        if asesor.tipo_asesor == 'Externo':
            return ExternalCommissionSupportDocumentBuilder(self.empresa, self.proyecto, self.resolver).build(commission, asesor)
        raise AlegraBuildError(f'El asesor {asesor.pk} no tiene tipo_asesor valido.')


class InternalCommissionAdvanceBuilder:
    def __init__(self, empresa, proyecto, resolver=None):
        self.empresa = empresa
        self.proyecto = proyecto
        self.resolver = resolver or MappingResolver(empresa, proyecto)

    def build(self, commission, asesor):
        doc = consecutivos.objects.using(self.proyecto.pk).get(documento='COMISIONES')
        value = _money(commission.pagoneto)
        if value <= 0:
            raise AlegraBuildError('La comision interna no tiene pago neto positivo.')
        contact_id = self.resolver.contact_for_asesor(asesor.pk)
        cost_center_id = self.resolver.cost_center_for_project(required=False)
        debit_account = self.resolver.category_for_code(doc.cuenta_aux1)
        credit_account = self.resolver.category_for_code(doc.cuenta_inmora)
        numeration_id = self.resolver.numeration('commission_journal')
        description = f'ANTICIPO COMISION {asesor.nombre} {self.proyecto.pk} {commission.fecha}'
        entries = [
            {
                'id': debit_account,
                'description': description,
                'debit': value,
                'client': {'id': contact_id},
            },
            {
                'id': credit_account,
                'description': description,
                'credit': value,
                'client': {'id': contact_id},
            },
        ]
        if cost_center_id:
            for entry in entries:
                entry['costCenter'] = {'id': cost_center_id}

        payload = {
            'date': _date(commission.fecha),
            'reference': f'COM-{self.proyecto.pk}-{commission.id_pago}',
            'observations': description[:500],
            'idNumeration': numeration_id,
            'entries': entries,
        }
        return BuiltDocument(
            document_type='commission_internal_advance',
            operation='accounting__createJournal',
            transport=AlegraDocument.ALEGRA_TOOL,
            source_model='andinasoft.Pagocomision',
            source_pk=commission.id_pago,
            local_key=f'commission:internal:{self.proyecto.pk}:{commission.id_pago}',
            payload=payload,
        )

    def local_payload(self, commission, asesor):
        doc = consecutivos.objects.using(self.proyecto.pk).get(documento='COMISIONES')
        return {
            'tipo': 'comision_interna_anticipo',
            'proyecto': getattr(self.proyecto, 'pk', None),
            'fecha': _date(getattr(commission, 'fecha', None)),
            'asesor': {'id': getattr(asesor, 'pk', None), 'nombre': getattr(asesor, 'nombre', None)},
            'debit_account_code': getattr(doc, 'cuenta_aux1', None),
            'credit_account_code': getattr(doc, 'cuenta_inmora', None),
            'valor': _money(getattr(commission, 'pagoneto', 0)),
        }


class ExternalCommissionSupportDocumentBuilder:
    def __init__(self, empresa, proyecto, resolver=None):
        self.empresa = empresa
        self.proyecto = proyecto
        self.resolver = resolver or MappingResolver(empresa, proyecto)

    def build(self, commission, asesor):
        doc = consecutivos.objects.using(self.proyecto.pk).get(documento='COMISIONES')
        gross = _money(commission.comision)
        if gross <= 0:
            raise AlegraBuildError('La comision externa no tiene valor bruto positivo.')

        provider_id = self.resolver.contact_for_asesor(asesor.pk)
        cost_center_id = self.resolver.cost_center_for_project(required=False)
        numeration_id = self.resolver.numeration('support_document')
        expense_category = self.resolver.category_for_code(doc.cuenta_capital)
        retention_id = self.resolver.retention('commission_retefuente', required=bool(commission.retefuente))

        payload = {
            'date': _date(commission.fecha),
            'dueDate': _date(commission.fecha),
            'provider': {'id': provider_id},
            'numberTemplate': {'id': numeration_id},
            'observations': f'DOCUMENTO SOPORTE COMISION {asesor.nombre} {self.proyecto.pk} {commission.fecha}'[:500],
            'purchases': {
                'categories': [
                    {
                        'id': expense_category,
                        'quantity': 1,
                        'price': gross,
                        'observations': f'COMISION {self.proyecto.pk} {commission.idadjudicacion or ""}'.strip(),
                    }
                ]
            },
        }
        if cost_center_id:
            payload['costCenter'] = {'id': cost_center_id}
        if _nonzero(commission.retefuente):
            payload['retentions'] = [{'id': retention_id, 'amount': _money(commission.retefuente)}]

        return BuiltDocument(
            document_type='commission_external_support',
            operation='POST /bills',
            transport=AlegraDocument.ALEGRA_REST,
            source_model='andinasoft.Pagocomision',
            source_pk=commission.id_pago,
            local_key=f'commission:external:{self.proyecto.pk}:{commission.id_pago}',
            payload=payload,
        )


class ExpensePaymentBuilder:
    def __init__(self, empresa):
        self.empresa = empresa
        self.resolver = MappingResolver(empresa)

    def build(self, source):
        if isinstance(source, Pagos):
            return self._from_pago(source)
        if isinstance(source, Anticipos):
            return self._from_anticipo(source)
        if isinstance(source, transferencias_companias):
            return self._from_transferencia(source)
        raise AlegraBuildError(f'Tipo de egreso no soportado: {source.__class__.__name__}')

    def _base_payment(self, *, date, cuenta, value, description, local_key, source_model, source_pk, contact_id=None, numeration_id=None):
        bank_account_id = self.resolver.bank_account_for_account(cuenta)
        payment_method = self.resolver.payment_method(cuenta.cuentabanco, required=False) or 'transfer'
        # Optional company-level cost center for expense payments (when configured).
        cost_center_id = self.resolver.get(AlegraMapping.COST_CENTER, local_code='company_default', required=False)
        payload = {
            'type': 'out',
            'date': _date(date),
            'bankAccount': {'id': bank_account_id},
            'paymentMethod': payment_method,
            'observations': description[:500],
        }
        if numeration_id:
            payload['numberTemplate'] = {'id': str(numeration_id)}
        if cost_center_id:
            payload['costCenter'] = {'id': cost_center_id}
        if contact_id:
            payload['client'] = {'id': contact_id}
        return BuiltDocument(
            document_type='expense_payment',
            operation='POST /payments',
            transport=AlegraDocument.ALEGRA_REST,
            source_model=source_model,
            source_pk=source_pk,
            local_key=local_key,
            payload=payload,
        )

    def _from_pago(self, pago):
        factura = pago.nroradicado
        empresa_origen_id = getattr(getattr(factura, 'empresa', None), 'pk', None)
        empresa_pago_id = getattr(getattr(getattr(pago, 'cuenta', None), 'nit_empresa_id', None), '__str__', lambda: None)()
        empresa_pago_id = empresa_pago_id or getattr(getattr(getattr(pago, 'cuenta', None), 'nit_empresa_id', None), 'pk', None) or getattr(getattr(pago, 'cuenta', None), 'nit_empresa_id', None)
        empresa_pago_id = str(empresa_pago_id).strip() if empresa_pago_id is not None else ''
        empresa_origen_id = str(empresa_origen_id).strip() if empresa_origen_id is not None else ''

        # Intercompany: gasto/origen (factura.empresa) != empresa dueña del banco que paga (cuenta.nit_empresa_id).
        if empresa_origen_id and empresa_pago_id and empresa_origen_id != empresa_pago_id:
            return self._from_pago_intercompany(pago, factura, empresa_origen_id, empresa_pago_id)

        tercero_pk = str(factura.idtercero).strip() if factura and getattr(factura, 'idtercero', None) is not None else ''
        if not tercero_pk:
            raise AlegraBuildError(f'El pago {pago.pk} no tiene idtercero en su factura/radicado.')

        # `idtercero` in Facturas/Pagos can refer to different local tables depending on the business case.
        # Prefer a concrete local model to avoid creating the mapping under the wrong local_model.
        if clientes.objects.filter(pk=tercero_pk).exists():
            contact_id = self.resolver.contact_for_cliente(tercero_pk)
        elif empresas.objects.filter(pk=tercero_pk).exists():
            contact_id = self.resolver.contact_for_empresa(tercero_pk)
        elif asesores.objects.filter(pk=tercero_pk).exists():
            contact_id = self.resolver.contact_for_asesor(tercero_pk)
        else:
            # No local third-party table; resolve using Alegra contact index by identification.
            contact_id = self.resolver.contact_by_identification(
                tercero_pk,
                prefer_types=['provider', 'client'],
                required=True,
            )
        built = self._base_payment(
            date=pago.fecha_pago,
            cuenta=pago.cuenta,
            value=pago.valor,
            description=f'PAGO FACT {factura.nrofactura} {factura.descripcion or ""}',
            local_key=f'expense:pago:{pago.pk}',
            source_model='accounting.Pagos',
            source_pk=pago.pk,
            contact_id=contact_id,
            numeration_id=self.resolver.numeration('expense_payment', required=False),
        )
        bill_id = self.resolver.bill_for_factura(factura.pk, required=False)
        if bill_id:
            built.payload['bills'] = [{'id': bill_id, 'amount': _money(pago.valor)}]
        else:
            category_code = factura.cuenta_por_pagar.cuenta_credito_1 if factura.cuenta_por_pagar else None
            if not category_code:
                raise AlegraBuildError(f'La factura {factura.pk} no tiene cuenta por pagar para mapear categoria.')
            # 1) Try mapping per interface (concept)
            interface_id = getattr(factura, 'cuenta_por_pagar_id', None)
            cat_id = None
            if interface_id:
                cat_id = self.resolver.get(
                    AlegraMapping.CATEGORY,
                    local_model='accounting.info_interfaces',
                    local_pk=str(interface_id),
                    local_code='cxp_credito_1',
                    required=False,
                )
            # 2) Try mapping by account code
            if not cat_id:
                cat_id = self.resolver.category_for_code(category_code, required=False)
            if not cat_id:
                # Company-level fallback (configure in UI): default account for CXP payments.
                cat_id = self.resolver.get(AlegraMapping.CATEGORY, local_code='default_cxp')
            built.payload['categories'] = [{
                'id': cat_id,
                'quantity': 1,
                'price': _money(pago.valor),
                'observations': f'PAGO FACT {factura.nrofactura}',
            }]
        return built

    def _from_pago_intercompany(self, pago, factura, empresa_origen_id, empresa_pago_id):
        """
        Build ONE intercompany journal for the current batch company (`self.empresa`):
        - If current company is empresa_pago (bank owner): bank out vs intercompany CxC
        - If current company is empresa_origen (expense owner): CXP concept vs intercompany CxP
        """
        try:
            empresa_origen = empresas.objects.get(pk=empresa_origen_id)
            empresa_pago = empresas.objects.get(pk=empresa_pago_id)
        except Exception:
            raise AlegraBuildError(f'No se pudo resolver empresas intercompany: origen={empresa_origen_id}, pagó={empresa_pago_id}.')

        current_empresa_id = str(getattr(self.empresa, 'pk', '') or '').strip()
        if current_empresa_id not in (empresa_origen_id, empresa_pago_id):
            raise AlegraBuildError(
                f'El pago {pago.pk} es intercompany entre {empresa_origen_id} y {empresa_pago_id}, '
                f'pero el lote actual es de empresa {current_empresa_id}.'
            )

        value = _money(getattr(pago, 'valor', 0))
        if value <= 0:
            raise AlegraBuildError('El pago no tiene valor positivo.')

        # Provider name for audit trail
        prov = (getattr(factura, 'nombretercero', '') or '').strip()
        if not prov:
            prov = (getattr(factura, 'descripcion', '') or '').strip()
        if not prov:
            prov = str(getattr(factura, 'idtercero', '') or '').strip()
        prov = (prov or '').strip()

        interco_ref = f'INTERCO-PAGO-{pago.pk}'
        observations = f'{interco_ref} {prov} · Origen {empresa_origen_id}'.strip()

        # Lookup intercompany configuration (local codes) between companies
        rel_b_to_a = cuentas_intercompanias.objects.filter(empresa_desde_id=empresa_pago_id, empresa_hacia_id=empresa_origen_id).first()
        rel_a_to_b = cuentas_intercompanias.objects.filter(empresa_desde_id=empresa_origen_id, empresa_hacia_id=empresa_pago_id).first()
        if not rel_b_to_a or not rel_a_to_b:
            raise AlegraBuildError(f'No existe configuración intercompany para {empresa_pago_id}→{empresa_origen_id} (cuentas_intercompanias).')

        # Resolve intercompany accounts in Alegra (prefer per-rel mapping; fallback to mapping by local account code).
        cxc_code = str(getattr(rel_b_to_a, 'cuenta_por_cobrar', '') or '').strip()
        cxp_code = str(getattr(rel_a_to_b, 'cuenta_por_pagar', '') or '').strip()
        if not cxc_code or not cxp_code:
            raise AlegraBuildError('La relación intercompany no tiene cuenta_por_cobrar/cuenta_por_pagar configuradas.')

        date = _date(getattr(pago, 'fecha_pago', None))

        # Branch: build the side that belongs to the current batch company only
        if current_empresa_id == empresa_pago_id:
            resolver = MappingResolver(empresa_pago)
            interco_cxc = resolver.get(
                AlegraMapping.CATEGORY,
                local_model='accounting.cuentas_intercompanias',
                local_pk=str(rel_b_to_a.pk),
                local_code=f'interco_cxc:{empresa_origen_id}',
                required=False,
            ) or resolver.category_for_code(cxc_code)

            bank_code = getattr(getattr(pago, 'cuenta', None), 'nro_cuentacontable', None)
            if not bank_code:
                raise AlegraBuildError('La cuenta bancaria del pago no tiene nro_cuentacontable.')
            bank_cat = resolver.category_for_code(str(bank_code))

            num = resolver.get(AlegraMapping.NUMERATION, local_code='interco_journal', required=False)
            payload = {
                'date': date,
                'reference': interco_ref,
                'observations': observations[:500],
                'entries': [
                    {'id': interco_cxc, 'description': observations[:255], 'debit': value},
                    {'id': bank_cat, 'description': observations[:255], 'credit': value},
                ],
            }
            if num:
                payload['idNumeration'] = num
            return BuiltDocument(
                document_type='expense_intercompany',
                operation='accounting__createJournal',
                transport=AlegraDocument.ALEGRA_REST,
                source_model='accounting.Pagos',
                source_pk=pago.pk,
                local_key=f'interco:{pago.pk}:{empresa_pago_id}',
                payload=payload,
                empresa_id=empresa_pago_id,
                proyecto_id=None,
            )

        # current_empresa_id == empresa_origen_id
        resolver = MappingResolver(empresa_origen)
        interco_cxp = resolver.get(
            AlegraMapping.CATEGORY,
            local_model='accounting.cuentas_intercompanias',
            local_pk=str(rel_a_to_b.pk),
            local_code=f'interco_cxp:{empresa_pago_id}',
            required=False,
        ) or resolver.category_for_code(cxp_code)

        concept_cat = None
        interface_id = getattr(factura, 'cuenta_por_pagar_id', None)
        if interface_id:
            concept_cat = resolver.get(
                AlegraMapping.CATEGORY,
                local_model='accounting.info_interfaces',
                local_pk=str(interface_id),
                local_code='cxp_credito_1',
                required=False,
            )
        if not concept_cat:
            category_code = factura.cuenta_por_pagar.cuenta_credito_1 if factura.cuenta_por_pagar else None
            if not category_code:
                raise AlegraBuildError(f'La factura {factura.pk} no tiene cuenta por pagar para mapear categoria.')
            concept_cat = resolver.category_for_code(str(category_code))

        num = resolver.get(AlegraMapping.NUMERATION, local_code='interco_journal', required=False)
        payload = {
            'date': date,
            'reference': interco_ref,
            'observations': observations[:500],
            'entries': [
                {'id': concept_cat, 'description': observations[:255], 'debit': value},
                {'id': interco_cxp, 'description': observations[:255], 'credit': value},
            ],
        }
        if num:
            payload['idNumeration'] = num
        return BuiltDocument(
            document_type='expense_intercompany',
            operation='accounting__createJournal',
            transport=AlegraDocument.ALEGRA_REST,
            source_model='accounting.Pagos',
            source_pk=pago.pk,
            local_key=f'interco:{pago.pk}:{empresa_origen_id}',
            payload=payload,
            empresa_id=empresa_origen_id,
            proyecto_id=None,
        )

    def _from_anticipo(self, anticipo):
        contact_id = self.resolver.get(AlegraMapping.CONTACT, local_model='andinasoft.clientes', local_pk=anticipo.id_tercero, required=False)
        built = self._base_payment(
            date=anticipo.fecha_pago,
            cuenta=anticipo.cuenta,
            value=anticipo.valor,
            description=f'ANTICIPO {anticipo.nombre_tercero or anticipo.id_tercero} {anticipo.descripcion}',
            local_key=f'expense:anticipo:{anticipo.pk}',
            source_model='accounting.Anticipos',
            source_pk=anticipo.pk,
            contact_id=contact_id,
            numeration_id=self.resolver.numeration('expense_anticipo', required=False),
        )
        debit_code = getattr(getattr(anticipo, 'tipo_anticipo', None), 'cuenta_debito_1', None)
        # 1) Try mapping per interface (concept)
        interface_id = getattr(anticipo, 'tipo_anticipo_id', None)
        cat_id = None
        if interface_id:
            cat_id = self.resolver.get(
                AlegraMapping.CATEGORY,
                local_model='accounting.info_interfaces',
                local_pk=str(interface_id),
                local_code='anticipo_debito_1',
                required=False,
            )
        # 2) Try mapping by account code
        if not cat_id:
            cat_id = self.resolver.category_for_code(debit_code, required=False) if debit_code else None
        if not cat_id:
            # Company-level fallback (configure in UI): default account for anticipos.
            cat_id = self.resolver.get(AlegraMapping.CATEGORY, local_code='default_anticipo')
        built.payload['categories'] = [{
            'id': cat_id,
            'quantity': 1,
            'price': _money(anticipo.valor),
            'observations': anticipo.descripcion,
        }]
        return built

    def _from_transferencia(self, transferencia):
        # Intercompany transfer between companies. When running a batch for one company,
        # only generate the journal side that belongs to that company.
        empresa_entra_id = str(getattr(transferencia, 'empresa_entra_id', '') or '').strip()
        empresa_sale_id = str(getattr(transferencia, 'empresa_sale_id', '') or '').strip()
        current_empresa_id = str(getattr(self.empresa, 'pk', '') or '').strip()
        if not empresa_entra_id or not empresa_sale_id:
            raise AlegraBuildError(f'Transferencia {transferencia.pk} sin empresa_entra/empresa_sale.')
        if current_empresa_id not in (empresa_entra_id, empresa_sale_id):
            raise AlegraBuildError(
                f'La transferencia {transferencia.pk} es entre {empresa_sale_id}→{empresa_entra_id}, '
                f'pero el lote actual es de empresa {current_empresa_id}.'
            )

        value = _money(getattr(transferencia, 'valor', 0))
        if value <= 0:
            raise AlegraBuildError('La transferencia no tiene valor positivo.')

        # If it's within the same company in Andinasoft, use Alegra dedicated bank transfer endpoint.
        if empresa_entra_id == empresa_sale_id == current_empresa_id:
            origin_bank = self.resolver.bank_account_for_account(transferencia.cuenta_sale)
            dest_bank = self.resolver.bank_account_for_account(transferencia.cuenta_entra)
            obs = f'TRANSFERENCIA {transferencia.cuenta_sale.cuentabanco} → {transferencia.cuenta_entra.cuentabanco}'.strip()
            payload = {
                'idDestination': str(dest_bank),
                'amount': float(value),
                'date': _date(getattr(transferencia, 'fecha', None)),
                'observations': obs[:500],
            }
            return BuiltDocument(
                document_type='expense_bank_transfer',
                operation=f'POST /bank-accounts/{origin_bank}/transfer',
                transport=AlegraDocument.ALEGRA_REST,
                source_model='accounting.transferencias_companias',
                source_pk=transferencia.pk,
                local_key=f'banktransfer:{transferencia.pk}:{current_empresa_id}',
                payload=payload,
                empresa_id=current_empresa_id,
                proyecto_id=None,
            )

        interco_ref = f'INTERCO-TRANSF-{transferencia.pk}'
        origen_name = getattr(getattr(transferencia, 'empresa_sale', None), 'nombre', '') or ''
        origen_name = (origen_name or '').strip()
        observations = f'{interco_ref} {origen_name} · Origen {empresa_sale_id}'.strip()

        date = _date(getattr(transferencia, 'fecha', None))

        if current_empresa_id == empresa_entra_id:
            # In empresa_entra: debit bank in, credit intercompany CxP towards empresa_sale
            # Relation must follow transfer direction: empresa_sale -> empresa_entra
            rels_a_to_b = list(cuentas_intercompanias.objects.filter(
                empresa_desde_id=empresa_sale_id,
                empresa_hacia_id=empresa_entra_id,
            ).order_by('pk')[:50])
            if not rels_a_to_b:
                raise AlegraBuildError(f'No existe configuración intercompany para {empresa_sale_id}→{empresa_entra_id}.')

            resolver = MappingResolver(self.empresa)
            interco_cxp = None
            cxp_code = ''
            for rel in rels_a_to_b:
                cxp_code = str(getattr(rel, 'cuenta_por_pagar', '') or '').strip() or cxp_code
                interco_cxp = resolver.get(
                    AlegraMapping.CATEGORY,
                    local_model='accounting.cuentas_intercompanias',
                    local_pk=str(rel.pk),
                    local_code=f'interco_cxp:{empresa_sale_id}',
                    required=False,
                )
                if interco_cxp:
                    break
            if not interco_cxp:
                if not cxp_code:
                    raise AlegraBuildError('La relación intercompany no tiene cuenta_por_pagar configurada.')
                interco_cxp = resolver.category_for_code(cxp_code)

            bank_code = getattr(getattr(transferencia, 'cuenta_entra', None), 'nro_cuentacontable', None)
            if not bank_code:
                raise AlegraBuildError('La cuenta que entra no tiene nro_cuentacontable.')
            bank_cat = resolver.category_for_code(str(bank_code))

            num = resolver.get(AlegraMapping.NUMERATION, local_code='interco_journal', required=False)
            payload = {
                'date': date,
                'reference': interco_ref,
                'observations': observations[:500],
                'entries': [
                    {'id': bank_cat, 'description': observations[:255], 'debit': value},
                    {'id': interco_cxp, 'description': observations[:255], 'credit': value},
                ],
            }
            if num:
                payload['idNumeration'] = num
            return BuiltDocument(
                document_type='expense_intercompany_transfer_in',
                operation='accounting__createJournal',
                transport=AlegraDocument.ALEGRA_REST,
                source_model='accounting.transferencias_companias',
                source_pk=transferencia.pk,
                local_key=f'interco:transfer:{transferencia.pk}:{empresa_entra_id}:in',
                payload=payload,
                empresa_id=empresa_entra_id,
                proyecto_id=None,
            )

        # current_empresa_id == empresa_sale_id
        # In empresa_sale: debit intercompany CxC towards empresa_entra, credit bank out
        rels_b_to_a = list(cuentas_intercompanias.objects.filter(
            empresa_desde_id=empresa_sale_id,
            empresa_hacia_id=empresa_entra_id,
        ).order_by('pk')[:50])
        if not rels_b_to_a:
            raise AlegraBuildError(f'No existe configuración intercompany para {empresa_sale_id}→{empresa_entra_id}.')

        resolver = MappingResolver(self.empresa)
        interco_cxc = None
        cxc_code = ''
        for rel in rels_b_to_a:
            cxc_code = str(getattr(rel, 'cuenta_por_cobrar', '') or '').strip() or cxc_code
            interco_cxc = resolver.get(
                AlegraMapping.CATEGORY,
                local_model='accounting.cuentas_intercompanias',
                local_pk=str(rel.pk),
                local_code=f'interco_cxc:{empresa_entra_id}',
                required=False,
            )
            if interco_cxc:
                break
        if not interco_cxc:
            if not cxc_code:
                raise AlegraBuildError('La relación intercompany no tiene cuenta_por_cobrar configurada.')
            interco_cxc = resolver.category_for_code(cxc_code)

        bank_code = getattr(getattr(transferencia, 'cuenta_sale', None), 'nro_cuentacontable', None)
        if not bank_code:
            raise AlegraBuildError('La cuenta que sale no tiene nro_cuentacontable.')
        bank_cat = resolver.category_for_code(str(bank_code))

        num = resolver.get(AlegraMapping.NUMERATION, local_code='interco_journal', required=False)
        payload = {
            'date': date,
            'reference': interco_ref,
            'observations': observations[:500],
            'entries': [
                {'id': interco_cxc, 'description': observations[:255], 'debit': value},
                {'id': bank_cat, 'description': observations[:255], 'credit': value},
            ],
        }
        if num:
            payload['idNumeration'] = num
        return BuiltDocument(
            document_type='expense_intercompany_transfer_out',
            operation='accounting__createJournal',
            transport=AlegraDocument.ALEGRA_REST,
            source_model='accounting.transferencias_companias',
            source_pk=transferencia.pk,
            local_key=f'interco:transfer:{transferencia.pk}:{empresa_sale_id}:out',
            payload=payload,
            empresa_id=empresa_sale_id,
            proyecto_id=None,
        )

    def local_payload(self, source):
        if isinstance(source, Pagos):
            factura = source.nroradicado
            return {
                'tipo': 'egreso_pago_factura',
                'empresa': getattr(self.empresa, 'pk', None),
                'fecha_pago': _date(getattr(source, 'fecha_pago', None)),
                'valor': _money(getattr(source, 'valor', 0)),
                'factura': {
                    'nroradicado': getattr(factura, 'pk', None),
                    'nrofactura': getattr(factura, 'nrofactura', None),
                    'idtercero': getattr(factura, 'idtercero', None),
                    'descripcion': getattr(factura, 'descripcion', None),
                    'cuenta_por_pagar': getattr(getattr(factura, 'cuenta_por_pagar', None), 'cuenta_credito_1', None),
                },
                'cuenta_banco': {
                    'id': getattr(getattr(source, 'cuenta', None), 'pk', None),
                    'nombre': getattr(getattr(source, 'cuenta', None), 'cuentabanco', None),
                    'nro_cuentacontable': getattr(getattr(source, 'cuenta', None), 'nro_cuentacontable', None),
                },
            }
        if isinstance(source, Anticipos):
            return {
                'tipo': 'egreso_anticipo',
                'empresa': getattr(self.empresa, 'pk', None),
                'fecha_pago': _date(getattr(source, 'fecha_pago', None)),
                'valor': _money(getattr(source, 'valor', 0)),
                'tercero': getattr(source, 'id_tercero', None),
                'descripcion': getattr(source, 'descripcion', None),
                'cuenta_debito_1': getattr(getattr(getattr(source, 'tipo_anticipo', None), 'cuenta_debito_1', None), 'cuenta_debito_1', None)
                if hasattr(getattr(source, 'tipo_anticipo', None), 'cuenta_debito_1') else getattr(getattr(source, 'tipo_anticipo', None), 'cuenta_debito_1', None),
            }
        if isinstance(source, transferencias_companias):
            return {
                'tipo': 'egreso_transferencia_companias',
                'empresa': getattr(self.empresa, 'pk', None),
                'fecha': _date(getattr(source, 'fecha', None)),
                'valor': _money(getattr(source, 'valor', 0)),
                'empresa_entra': getattr(getattr(source, 'empresa_entra', None), 'nombre', None),
                'cuenta_sale': getattr(getattr(source, 'cuenta_sale', None), 'nro_cuentacontable', None),
                'cuenta_entra': getattr(getattr(source, 'cuenta_entra', None), 'nro_cuentacontable', None),
            }
        return {'tipo': 'egreso', 'note': 'no local payload'}
