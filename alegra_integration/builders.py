from decimal import Decimal, ROUND_DOWN

from django.db.models import Sum

from accounting.models import Anticipos, Facturas, Pagos, cuentas_intercompanias, transferencias_companias
from alegra_integration.exceptions import AlegraBuildError, AlegraConfigurationError
from alegra_integration.mapping import MappingResolver
from alegra_integration.models import AlegraDocument, AlegraMapping
from andinasoft.models import Detalle_gtt, Gtt, asesores, clientes, cuentas_pagos, empresas
from andinasoft.shared_models import Recaudos, consecutivos, formas_pago


def _money(value):
    return float(Decimal(value or 0).quantize(Decimal('0.01')))


def _date(value):
    return value.isoformat() if value else None


def _journal_payload(*, numeration_id, date, reference, observations, entries):
    """
    POST /journals — mismo contrato que recibos de caja (numberTemplate + status open).
    Alegra aplica el tipo de comprobante contable vía numberTemplate, no idNumeration.
    """
    return {
        'numberTemplate': str(numeration_id),
        'date': date,
        'reference': reference,
        'observations': (observations or '')[:500],
        'status': 'open',
        'entries': entries,
    }


def _journal_entry(*, account_id, description, debit, credit, client_id=None):
    """Línea de asiento; `client` como string (mismo formato que recibos de caja)."""
    entry = {
        'id': account_id,
        'description': (description or '')[:255],
        'debit': debit,
        'credit': credit,
    }
    if client_id:
        entry['client'] = str(client_id)
    return entry


def _nonzero(value):
    return Decimal(value or 0) != 0


def _commission_payment_value(commission, mode):
    if mode == 'gross':
        return _money(commission.comision)
    return _money(commission.pagoneto)


def _empresa_pk(value):
    if value is None:
        return ''
    if hasattr(value, 'pk'):
        return str(value.pk).strip()
    return str(value).strip()


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

    def _cuenta_empresa_id(self, cuenta):
        if not cuenta:
            return ''
        return _empresa_pk(getattr(cuenta, 'nit_empresa_id', None))

    def _resolve_interco_cxc_for_bank(self, empresa_origen_id, empresa_banco_id):
        """
        Recibo en empresa origen con forma de pago en banco de otra empresa:
        débito a CxC intercompany (la contraparte tiene el efectivo).
        """
        rel_b_to_a = cuentas_intercompanias.objects.filter(
            empresa_desde_id=empresa_banco_id,
            empresa_hacia_id=empresa_origen_id,
        ).first()
        rel_a_to_b = cuentas_intercompanias.objects.filter(
            empresa_desde_id=empresa_origen_id,
            empresa_hacia_id=empresa_banco_id,
        ).first()
        if not rel_b_to_a or not rel_a_to_b:
            raise AlegraBuildError(
                f'No existe configuración intercompany para recibo entre {empresa_banco_id} (banco) '
                f'y {empresa_origen_id} (proyecto).'
            )

        interco_cxc = None
        cxc_code = ''
        for rel in (rel_a_to_b, rel_b_to_a):
            if rel is rel_a_to_b:
                cxc_code = str(getattr(rel, 'cuenta_por_cobrar', '') or '').strip() or cxc_code
                interco_cxc = self.resolver.get(
                    AlegraMapping.CATEGORY,
                    local_model='accounting.cuentas_intercompanias',
                    local_pk=str(rel.pk),
                    local_code=f'interco_cxc:{empresa_banco_id}',
                    required=False,
                ) or interco_cxc
            if interco_cxc:
                break
        if not interco_cxc:
            if not cxc_code:
                raise AlegraBuildError('La relación intercompany no tiene cuenta_por_cobrar configurada.')
            interco_cxc = self.resolver.category_for_code(cxc_code)
        return interco_cxc

    def _contact_id_empresa_intercompany(self, empresa_nit, *, label='contraparte'):
        """Contacto Alegra de la empresa del grupo (NIT = empresas.pk) donde ingresó el efectivo."""
        nit = str(empresa_nit or '').strip()
        if not nit:
            raise AlegraBuildError(f'Falta NIT de empresa {label} para el asiento intercompany del recibo.')
        try:
            return self.resolver.contact_for_empresa(nit)
        except AlegraConfigurationError as exc:
            raise AlegraBuildError(
                f'Falta mapeo de contacto Alegra para la empresa {nit} ({label}). '
                f'Sincroniza o enlaza el contacto en Referencias.'
            ) from exc

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

        numeration_id = self.resolver.numeration('receipt_cash')
        cost_center_id = self.resolver.cost_center_for_project(required=False)

        forma_pago = (receipt.formapago or '').strip()
        if not forma_pago:
            raise AlegraBuildError(f'El recibo {receipt.numrecibo} no tiene forma de pago.')

        # POST /journals: débito por forma de pago (mapeo en Referencias), créditos anticipo por titular.
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

        adj_ref = (getattr(receipt, 'idadjudicacion', None) or '').strip()
        if not adj_ref and adj is not None:
            adj_ref = str(getattr(adj, 'pk', '') or '').strip()

        desc_parts = [f'RECIBO {receipt.numrecibo}', str(self.proyecto.pk)]
        if adj_ref:
            desc_parts.append(f'ADJ {adj_ref}')
        if titular_name:
            desc_parts.append(titular_name)
        desc = ' '.join(desc_parts).strip()
        concepto = (receipt.concepto or '').strip()
        observations = desc if not concepto else f'{desc} - {concepto}'
        fecha_pago = _date(getattr(receipt, 'fecha_pago', None))
        if fecha_pago:
            observations = f'{observations} · F.pago {fecha_pago}'.strip()

        try:
            forma_cfg = self.resolver.receipt_forma_pago_config(forma_pago)
        except AlegraConfigurationError as exc:
            raise AlegraBuildError(
                f'{exc} Configure la forma de pago «{forma_pago}» en Referencias → Recibos.'
            ) from exc
        debit_account = forma_cfg['category_id']

        # Credit account: configured "anticipos de clientes"
        credit_account = self.resolver.get(AlegraMapping.CATEGORY, local_code='receipt_client_advance')

        n = max(1, len(titular_ids))
        base = (total / Decimal(n)).quantize(Decimal('0.01'), rounding=ROUND_DOWN)
        remainder = total - (base * n)
        amounts = [base] * n
        if remainder != 0:
            amounts[0] = (amounts[0] + remainder).quantize(Decimal('0.01'))

        if forma_cfg.get('intercompany'):
            counterparty_nit = (forma_cfg.get('counterparty_nit') or '').strip()
            if not counterparty_nit:
                raise AlegraBuildError(
                    f'La forma de pago «{forma_pago}» está marcada como intercompany pero no tiene NIT '
                    f'contraparte en Referencias → Recibos.'
                )
            try:
                debit_client_id = self.resolver.contact_for_empresa(counterparty_nit)
            except AlegraConfigurationError as exc:
                raise AlegraBuildError(
                    f'{exc} Enlaza el contacto de la empresa {counterparty_nit} en Referencias.'
                ) from exc
            observations = f'{observations} · INTERCO {counterparty_nit}'.strip()
        else:
            debit_client_id = self.resolver.contact_for_cliente(titular_ids[0])

        entries = [
            {
                'id': debit_account,
                'description': desc[:255],
                'debit': float(total),
                'credit': 0,
                'client': str(debit_client_id),
            }
        ]
        for t_id, amt in zip(titular_ids, amounts):
            client_id = self.resolver.contact_for_cliente(t_id)
            entries.append(
                {
                    'id': credit_account,
                    'description': desc[:255],
                    'debit': 0,
                    'credit': float(amt),
                    'client': str(client_id),
                }
            )
        if cost_center_id:
            for e in entries:
                e['costCenter'] = {'id': cost_center_id}
        payload = {
            'numberTemplate': str(numeration_id),
            'date': _date(receipt.fecha),
            'reference': f'RC-{self.proyecto.pk}-{receipt.numrecibo}',
            'observations': observations[:500],
            'status': 'open',
            'entries': entries,
        }
        payload['__local'] = {
            'forma_pago': forma_pago,
            'debit_category_id': debit_account,
            'credit_category_id': credit_account,
            'intercompany': bool(forma_cfg.get('intercompany')),
            'counterparty_nit': (forma_cfg.get('counterparty_nit') or '').strip() or None,
        }

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

        forma_pago = (getattr(receipt, 'formapago', None) or '').strip()
        puc_local = ''
        try:
            fp = formas_pago.objects.using(self.proyecto.pk).filter(descripcion=forma_pago).first()
            if fp:
                puc_local = (getattr(fp, 'cuenta_contable', None) or '').strip()
        except Exception:
            puc_local = ''

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
            'idadjudicacion': (getattr(receipt, 'idadjudicacion', None) or '').strip() or None,
            'numrecibo': getattr(receipt, 'numrecibo', None),
            'fecha': _date(getattr(receipt, 'fecha', None)),
            'fecha_pago': _date(getattr(receipt, 'fecha_pago', None)),
            'forma_pago': forma_pago or None,
            'puc_local': puc_local or None,
            'debit_mapping': 'receipt_debit',
            'credit_account_config': 'receipt_client_advance',
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

    def _debit_category_id(self, doc):
        mapped = self.resolver.get(AlegraMapping.CATEGORY, local_code='commission_debit', required=False)
        if mapped:
            return mapped
        return self.resolver.category_for_code(doc.cuenta_aux1)

    def _credit_category_id(self, doc):
        mapped = self.resolver.get(AlegraMapping.CATEGORY, local_code='commission_credit', required=False)
        if mapped:
            return mapped
        return self.resolver.category_for_code(doc.cuenta_inmora)

    def build(self, commission, asesor):
        doc = consecutivos.objects.using(self.proyecto.pk).get(documento='COMISIONES')
        amount_mode = self.resolver.commission_amount_source(for_tipo='internal', default='net')
        value = _commission_payment_value(commission, amount_mode)
        if value <= 0:
            field = 'comision' if amount_mode == 'gross' else 'pagoneto'
            raise AlegraBuildError(
                f'La comision interna no tiene valor positivo ({field}, modo={amount_mode}).'
            )
        contact_id = self.resolver.contact_for_asesor(asesor.pk)
        cost_center_id = self.resolver.cost_center_for_project(required=False)
        debit_account = self._debit_category_id(doc)
        credit_account = self._credit_category_id(doc)
        numeration_id = self.resolver.numeration('commission_journal')
        description = f'COMISION {asesor.nombre} {self.proyecto.pk} {commission.fecha}'
        entries = [
            _journal_entry(
                account_id=debit_account,
                description=description,
                debit=value,
                credit=0,
                client_id=contact_id,
            ),
            _journal_entry(
                account_id=credit_account,
                description=description,
                debit=0,
                credit=value,
                client_id=contact_id,
            ),
        ]
        if cost_center_id:
            for entry in entries:
                entry['costCenter'] = {'id': cost_center_id}

        payload = _journal_payload(
            numeration_id=numeration_id,
            date=_date(commission.fecha),
            reference=f'COM-{self.proyecto.pk}-{commission.id_pago}',
            observations=description,
            entries=entries,
        )
        payload['__local'] = {
            'amount_mode': amount_mode,
            'amount': value,
            'commission_debit_category_id': debit_account,
            'commission_credit_category_id': credit_account,
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
        amount_mode = self.resolver.commission_amount_source(for_tipo='internal', default='net')
        return {
            'tipo': 'comision_interna_journal',
            'proyecto': getattr(self.proyecto, 'pk', None),
            'fecha': _date(getattr(commission, 'fecha', None)),
            'asesor': {'id': getattr(asesor, 'pk', None), 'nombre': getattr(asesor, 'nombre', None)},
            'debit_account_code': getattr(doc, 'cuenta_aux1', None),
            'credit_account_code': getattr(doc, 'cuenta_inmora', None),
            'amount_mode': amount_mode,
            'valor': _commission_payment_value(commission, amount_mode),
        }


class ExternalCommissionSupportDocumentBuilder:
    """
    Documento soporte (Colombia) por comisión de asesor externo — POST /bills.
    """

    def __init__(self, empresa, proyecto, resolver=None):
        self.empresa = empresa
        self.proyecto = proyecto
        self.resolver = resolver or MappingResolver(empresa, proyecto)

    def _expense_category_id(self, doc):
        mapped = self.resolver.get(AlegraMapping.CATEGORY, local_code='commission_expense', required=False)
        if mapped:
            return mapped
        return self.resolver.category_for_code(doc.cuenta_capital)

    def build(self, commission, asesor):
        doc = consecutivos.objects.using(self.proyecto.pk).get(documento='COMISIONES')
        amount_mode = self.resolver.commission_amount_source(for_tipo='external', default='gross')
        amount = _commission_payment_value(commission, amount_mode)
        if amount <= 0:
            field = 'comision' if amount_mode == 'gross' else 'pagoneto'
            raise AlegraBuildError(
                f'La comision externa no tiene valor positivo ({field}, modo={amount_mode}).'
            )

        provider_id = self.resolver.contact_for_asesor(asesor.pk)
        cost_center_id = self.resolver.cost_center_for_project(required=False)
        numeration_id = self.resolver.numeration('commission_support_document')
        expense_category = self._expense_category_id(doc)

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
                        'price': amount,
                        'observations': f'COMISION {self.proyecto.pk} {getattr(commission, "idadjudicacion", "") or ""}'.strip(),
                    }
                ]
            },
        }
        if cost_center_id:
            payload['costCenter'] = {'id': cost_center_id}

        retefuente_amount = _money(commission.retefuente)
        if amount_mode == 'gross' and _nonzero(commission.retefuente):
            retention_id = self.resolver.retention('commission_retefuente', required=True)
            payload['retentions'] = [{'id': retention_id, 'amount': retefuente_amount}]

        payload['__local'] = {
            'commission_expense_category_id': expense_category,
            'amount_mode': amount_mode,
            'amount': amount,
            'retefuente': retefuente_amount if amount_mode == 'gross' else 0,
        }

        return BuiltDocument(
            document_type='commission_external_support',
            operation='POST /bills',
            transport=AlegraDocument.ALEGRA_REST,
            source_model='andinasoft.Pagocomision',
            source_pk=commission.id_pago,
            local_key=f'commission:external:{self.proyecto.pk}:{commission.id_pago}',
            payload=payload,
        )


class GttSupportDocumentBuilder:
    """
    Documento soporte (Colombia) por línea de GTT aprobado — POST /bills.
    Numeración: mapeo numeration / local_code gtt_support_document (tipo documento soporte en Alegra).
    """

    def __init__(self, empresa, proyecto, resolver=None):
        self.empresa = empresa
        self.proyecto = proyecto
        self.resolver = resolver or MappingResolver(empresa, proyecto)

    def _expense_category_id(self):
        """Cuenta de gasto (línea en purchases.categories del documento soporte)."""
        mapped = self.resolver.get(AlegraMapping.CATEGORY, local_code='gtt_expense', required=False)
        if mapped:
            return mapped
        doc = consecutivos.objects.using(self.proyecto.pk).get(documento='COMISIONES')
        return self.resolver.category_for_code(doc.cuenta_capital)

    def _cxp_category_id(self):
        """Cuenta por pagar (mapeo por proyecto; contrapartida en el asiento de Alegra)."""
        return self.resolver.get(AlegraMapping.CATEGORY, local_code='gtt_cxp', required=True)

    def build(self, detalle, gtt, asesor):
        value = _money(detalle.valor)
        if value <= 0:
            raise AlegraBuildError('La línea GTT no tiene valor positivo.')
        if getattr(asesor, 'tipo_asesor', None) != 'Externo':
            raise AlegraBuildError(f'El asesor {asesor.pk} no es externo (GTT solo aplica a externos).')

        provider_id = self.resolver.contact_for_asesor(asesor.pk)
        cost_center_id = self.resolver.cost_center_for_project(required=False)
        numeration_id = self.resolver.numeration('gtt_support_document')
        expense_category = self._expense_category_id()
        cxp_category = self._cxp_category_id()
        bill_date = _date(gtt.fecha_hasta)
        desc = (
            f'GTT {asesor.nombre} {self.proyecto.pk} '
            f'{gtt.fecha_desde}..{gtt.fecha_hasta}'
        )[:500]

        payload = {
            'date': bill_date,
            'dueDate': bill_date,
            'provider': {'id': provider_id},
            'numberTemplate': {'id': numeration_id},
            'observations': desc,
            'purchases': {
                'categories': [
                    {
                        'id': expense_category,
                        'quantity': 1,
                        'price': value,
                        'observations': f'GTT {self.proyecto.pk} GTT#{gtt.pk} linea {detalle.pk}'.strip(),
                    }
                ]
            },
        }
        if cost_center_id:
            payload['costCenter'] = {'id': cost_center_id}

        payload['__local'] = {
            'gtt_expense_category_id': expense_category,
            'gtt_cxp_category_id': cxp_category,
        }

        return BuiltDocument(
            document_type='gtt_support',
            operation='POST /bills',
            transport=AlegraDocument.ALEGRA_REST,
            source_model='andinasoft.Detalle_gtt',
            source_pk=detalle.pk,
            local_key=f'gtt:{self.proyecto.pk}:{gtt.pk}:{detalle.pk}',
            payload=payload,
        )

    def local_payload(self, detalle, gtt, asesor):
        return {
            'tipo': 'gtt_documento_soporte',
            'proyecto': getattr(self.proyecto, 'pk', None),
            'gtt_id': getattr(gtt, 'pk', None),
            'fecha_desde': _date(getattr(gtt, 'fecha_desde', None)),
            'fecha_hasta': _date(getattr(gtt, 'fecha_hasta', None)),
            'asesor': {'id': getattr(asesor, 'pk', None), 'nombre': getattr(asesor, 'nombre', None)},
            'valor': _money(getattr(detalle, 'valor', 0)),
            'gtt_expense_category_id': self._expense_category_id(),
            'gtt_cxp_category_id': self._cxp_category_id(),
        }


class GttBuilder:
    def __init__(self, empresa, proyecto):
        self.empresa = empresa
        self.proyecto = proyecto
        self.resolver = MappingResolver(empresa, proyecto)
        self._line_builder = GttSupportDocumentBuilder(empresa, proyecto, self.resolver)

    def build(self, detalle):
        gtt = detalle.gtt
        if (gtt.proyecto or '').strip() != str(self.proyecto.pk).strip():
            raise AlegraBuildError('El GTT no pertenece al proyecto seleccionado.')
        if (gtt.estado or '').strip().lower() != 'aprobado':
            raise AlegraBuildError(f'El GTT {gtt.pk} no está aprobado (estado={gtt.estado}).')
        try:
            asesor = detalle.asesor
        except Exception:
            raise AlegraBuildError(f'No existe asesor para la línea GTT {detalle.pk}.')
        return self._line_builder.build(detalle, gtt, asesor)

    def local_payload(self, detalle):
        gtt = detalle.gtt
        asesor = detalle.asesor
        return self._line_builder.local_payload(detalle, gtt, asesor)


class ExpensePaymentBuilder:
    def __init__(self, empresa):
        self.empresa = empresa
        self.resolver = MappingResolver(empresa)

    def _contact_id_for_tercero(self, resolver, tercero_pk, *, required=True):
        """Resuelve contacto Alegra para idtercero de Facturas/Pagos (cliente, empresa, asesor o índice)."""
        tercero_pk = str(tercero_pk or '').strip()
        if not tercero_pk:
            if required:
                raise AlegraBuildError('Falta idtercero para mapear contacto en el asiento.')
            return None
        if clientes.objects.filter(pk=tercero_pk).exists():
            return resolver.contact_for_cliente(tercero_pk)
        if empresas.objects.filter(pk=tercero_pk).exists():
            return resolver.contact_for_empresa(tercero_pk)
        if asesores.objects.filter(pk=tercero_pk).exists():
            return resolver.contact_for_asesor(tercero_pk)
        return resolver.contact_by_identification(
            tercero_pk,
            prefer_types=['provider', 'client'],
            required=required,
        )

    def _contact_id_for_empresa_nit(self, resolver, empresa_id, *, required=False):
        nit = str(empresa_id or '').strip()
        if not nit or not empresas.objects.filter(pk=nit).exists():
            if required:
                raise AlegraBuildError(f'Falta empresa local {empresa_id} para mapear contacto intercompany.')
            return None
        return resolver.get(
            AlegraMapping.CONTACT,
            local_model='andinasoft.empresas',
            local_pk=nit,
            required=required,
        )

    def _contact_id_empresa_intercompany(self, resolver, counterparty_nit, *, label='contraparte'):
        """
        Contacto Alegra de la empresa del grupo contraparte (NIT = empresas.pk).
        Fuente: empresa_origen/empresa_pago en pagos; empresa_sale/empresa_entra en transferencias;
        alineado con local_code interco_cxc:<nit> / interco_cxp:<nit> en cuentas_intercompanias.
        """
        nit = str(counterparty_nit or '').strip()
        if not nit:
            raise AlegraBuildError(f'Falta NIT de empresa {label} para el asiento intercompany.')
        contact_id = self._contact_id_for_empresa_nit(resolver, nit, required=False)
        if not contact_id:
            raise AlegraBuildError(
                f'Falta mapeo de contacto Alegra para la empresa intercompany {nit} ({label}). '
                f'Configure en Referencias → contacto con local_model=andinasoft.empresas.'
            )
        return contact_id

    def build(self, source):
        if isinstance(source, Pagos):
            built = self._from_pago(source)
            return built
        if isinstance(source, Anticipos):
            return self._from_anticipo(source)
        if isinstance(source, transferencias_companias):
            return self._from_transferencia(source)
        raise AlegraBuildError(f'Tipo de egreso no soportado: {source.__class__.__name__}')

    def _pagos_detalle(self, pago):
        from accounting.models import pago_detallado_relacionado

        return list(pago_detallado_relacionado.objects.filter(pago=pago.pk).order_by('pk'))

    def _local_key_pago(self, pago_pk, id_tercero=None):
        if id_tercero:
            from accounting.journal_cxp import _ident_norm

            return f'expense:pago:{pago_pk}:t:{_ident_norm(id_tercero)}'
        return f'expense:pago:{pago_pk}'

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

        pagos_det = self._pagos_detalle(pago)
        if pagos_det:
            return [self._from_pago_detalle_line(pago, factura, pd) for pd in pagos_det]
        return self._from_pago_unico(pago, factura)

    def _from_pago_detalle_line(self, pago, factura, pd):
        """Un POST /payments por tercero del pago detallado (tesorería)."""
        id_tercero = (pd.id_tercero or '').strip()
        if not id_tercero:
            raise AlegraBuildError(f'El pago {pago.pk} tiene una línea de detalle sin id_tercero.')
        valor_linea = getattr(pd, 'valor', None)
        if valor_linea is None or _money(valor_linea) <= 0:
            raise AlegraBuildError(
                f'El pago {pago.pk} tiene una línea de detalle sin valor para el tercero {id_tercero}.'
            )
        contact_id = self._contact_id_for_tercero(self.resolver, id_tercero, required=True)
        nombre = (getattr(pd, 'nombre_tercero', None) or '').strip()
        desc_base = f'PAGO FACT {factura.nrofactura} {factura.descripcion or ""}'.strip()
        if nombre:
            desc_base = f'{desc_base} · {nombre}'.strip()
        built = self._base_payment(
            date=pago.fecha_pago,
            cuenta=pago.cuenta,
            value=valor_linea,
            description=desc_base,
            local_key=self._local_key_pago(pago.pk, id_tercero),
            source_model='accounting.Pagos',
            source_pk=pago.pk,
            contact_id=contact_id,
            numeration_id=self.resolver.numeration('expense_payment', required=False),
        )
        bill_id = self.resolver.bill_for_factura(factura.pk, required=False, factura=factura)
        if bill_id:
            built.payload['bills'] = [{'id': bill_id, 'amount': _money(valor_linea)}]
            return built
        cat_id = self._categoria_para_pago_linea(factura, id_tercero)
        if not cat_id:
            from accounting.journal_cxp import detalle_pago_desde_factura, fila_journal_para_tercero

            journal_detalle = detalle_pago_desde_factura(factura)
            row = fila_journal_para_tercero(journal_detalle, id_tercero) if journal_detalle else {}
            puc = (row.get('account_code') or '').strip()
            raise AlegraBuildError(
                f'El pago {pago.pk} (tercero {id_tercero}) no tiene categoría CxP mapeada '
                f'(cuenta PUC {puc or "?"}). Revise Alegra → Referencias → Egresos.'
            )
        built.payload['categories'] = [{
            'id': cat_id,
            'quantity': 1,
            'price': _money(valor_linea),
            'observations': desc_base[:255],
        }]
        return built

    def _categoria_para_pago_linea(self, factura, id_tercero):
        from accounting.journal_cxp import (
            categoria_alegra_desde_fila_journal,
            detalle_pago_desde_factura,
            fila_journal_para_tercero,
        )
        from alegra_integration.bill_mapping import ALEGRA_DOC_JOURNAL

        journal_detalle = detalle_pago_desde_factura(factura)
        doc_type = (getattr(factura, 'alegra_document_type', '') or '').strip()
        if not doc_type and ':journal:' in (getattr(factura, 'alegra_bill_id', None) or ''):
            doc_type = ALEGRA_DOC_JOURNAL
        if doc_type == ALEGRA_DOC_JOURNAL or journal_detalle:
            row = fila_journal_para_tercero(journal_detalle, id_tercero) if journal_detalle else None
            return categoria_alegra_desde_fila_journal(self.resolver, row)

        category_code = factura.cuenta_por_pagar.cuenta_credito_1 if factura.cuenta_por_pagar else None
        if not category_code:
            return None
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
        if not cat_id:
            cat_id = self.resolver.category_for_puc_code(category_code, required=False)
        if not cat_id:
            cat_id = self.resolver.get(AlegraMapping.CATEGORY, local_code='default_cxp', required=False)
        return cat_id

    def _from_pago_unico(self, pago, factura):
        if not factura or getattr(factura, 'idtercero', None) is None:
            raise AlegraBuildError(f'El pago {pago.pk} no tiene idtercero en su factura/radicado.')
        contact_id = self._contact_id_for_tercero(self.resolver, factura.idtercero, required=True)
        built = self._base_payment(
            date=pago.fecha_pago,
            cuenta=pago.cuenta,
            value=pago.valor,
            description=f'PAGO FACT {factura.nrofactura} {factura.descripcion or ""}',
            local_key=self._local_key_pago(pago.pk),
            source_model='accounting.Pagos',
            source_pk=pago.pk,
            contact_id=contact_id,
            numeration_id=self.resolver.numeration('expense_payment', required=False),
        )
        bill_id = self.resolver.bill_for_factura(factura.pk, required=False, factura=factura)
        if bill_id:
            built.payload['bills'] = [{'id': bill_id, 'amount': _money(pago.valor)}]
            return built

        from accounting.journal_cxp import categoria_alegra_para_pago_journal, detalle_pago_desde_factura
        from alegra_integration.bill_mapping import ALEGRA_DOC_JOURNAL

        doc_type = (getattr(factura, 'alegra_document_type', '') or '').strip()
        if not doc_type and ':journal:' in (getattr(factura, 'alegra_bill_id', None) or ''):
            doc_type = ALEGRA_DOC_JOURNAL
        journal_detalle = detalle_pago_desde_factura(factura)
        if doc_type == ALEGRA_DOC_JOURNAL or journal_detalle:
            cat_id = categoria_alegra_para_pago_journal(self.resolver, factura, pago)
            if cat_id:
                built.payload['categories'] = [{
                    'id': cat_id,
                    'quantity': 1,
                    'price': _money(pago.valor),
                    'observations': f'PAGO FACT {factura.nrofactura}',
                }]
                return built
            if journal_detalle:
                from accounting.journal_cxp import _fila_detalle_para_pago
                row = _fila_detalle_para_pago(journal_detalle, factura, pago) or {}
                puc = (row.get('account_code') or '').strip()
                raise AlegraBuildError(
                    f'La factura {factura.pk} tiene detalle journal (cuenta PUC {puc or "?"}) '
                    f'pero falta mapeo en Alegra → Referencias → Egresos. '
                    f'Registre el pago en tesorería con detalle por tercero.'
                )

        category_code = factura.cuenta_por_pagar.cuenta_credito_1 if factura.cuenta_por_pagar else None
        if not category_code:
            raise AlegraBuildError(
                f'La factura {factura.pk} no tiene cuenta por pagar ni detalle journal CxP para mapear categoría.'
            )
        cat_id = self._categoria_para_pago_linea(factura, factura.idtercero)
        if not cat_id:
            raise AlegraBuildError(
                f'La factura {factura.pk} tiene cuenta {category_code} sin mapeo en Alegra → Referencias → Egresos.'
            )
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
            # Contraparte = empresa del gasto (dueña del radicado); las líneas interco/banco no usan proveedor.
            interco_client = self._contact_id_empresa_intercompany(
                resolver, empresa_origen_id, label='empresa origen (gasto)',
            )
            desc = observations[:255]

            numeration_id = resolver.numeration('interco_journal')
            payload = _journal_payload(
                numeration_id=numeration_id,
                date=date,
                reference=interco_ref,
                observations=observations,
                entries=[
                    _journal_entry(
                        account_id=interco_cxc, description=desc, debit=value, credit=0,
                        client_id=interco_client,
                    ),
                    _journal_entry(
                        account_id=bank_cat, description=desc, debit=0, credit=value,
                    ),
                ],
            )
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

        provider_id = self._contact_id_for_tercero(resolver, getattr(factura, 'idtercero', None), required=True)
        interco_client = self._contact_id_empresa_intercompany(
            resolver, empresa_pago_id, label='empresa que pagó (banco)',
        )
        desc = observations[:255]
        numeration_id = resolver.numeration('interco_journal')
        payload = _journal_payload(
            numeration_id=numeration_id,
            date=date,
            reference=interco_ref,
            observations=observations,
            entries=[
                _journal_entry(
                    account_id=concept_cat, description=desc, debit=value, credit=0,
                    client_id=provider_id,
                ),
                _journal_entry(
                    account_id=interco_cxp, description=desc, debit=0, credit=value,
                    client_id=interco_client,
                ),
            ],
        )
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
            # Dinero sale de empresa_sale → entra aquí: contraparte = empresa_sale (NIT).
            interco_client = self._contact_id_empresa_intercompany(
                resolver, empresa_sale_id, label='empresa sale (origen fondos)',
            )
            desc = observations[:255]

            numeration_id = resolver.numeration('interco_journal')
            payload = _journal_payload(
                numeration_id=numeration_id,
                date=date,
                reference=interco_ref,
                observations=observations,
                entries=[
                    _journal_entry(
                        account_id=bank_cat, description=desc, debit=value, credit=0,
                        client_id=interco_client,
                    ),
                    _journal_entry(
                        account_id=interco_cxp, description=desc, debit=0, credit=value,
                        client_id=interco_client,
                    ),
                ],
            )
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
        interco_client = self._contact_id_empresa_intercompany(
            resolver, empresa_entra_id, label='empresa entra (destino fondos)',
        )
        desc = observations[:255]

        numeration_id = resolver.numeration('interco_journal')
        payload = _journal_payload(
            numeration_id=numeration_id,
            date=date,
            reference=interco_ref,
            observations=observations,
            entries=[
                _journal_entry(
                    account_id=interco_cxc, description=desc, debit=value, credit=0,
                    client_id=interco_client,
                ),
                _journal_entry(
                    account_id=bank_cat, description=desc, debit=0, credit=value,
                    client_id=interco_client,
                ),
            ],
        )
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
