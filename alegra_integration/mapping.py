from alegra_integration.exceptions import AlegraConfigurationError
import re

from alegra_integration.bill_mapping import ALEGRA_DOC_BILL, parse_alegra_bill_id_for_api
from alegra_integration.models import AlegraContactIndex, AlegraMapping
from django.db.models import Q


class MappingResolver:
    def __init__(self, empresa, proyecto=None):
        self.empresa = empresa
        self.proyecto = proyecto

    def get(self, mapping_type, *, local_model='', local_pk='', local_code='', required=True):
        local_model = (local_model or '').strip()
        local_pk = '' if local_pk is None else str(local_pk).strip()
        local_code = '' if local_code is None else str(local_code).strip()
        qs = AlegraMapping.objects.filter(
            empresa_id=self.empresa.pk,
            mapping_type=mapping_type,
            active=True,
        )
        # These mappings are global per company account in Alegra; do not scope them by project.
        if mapping_type in (AlegraMapping.CONTACT, AlegraMapping.PAYMENT_METHOD):
            qs = qs.filter(proyecto__isnull=True)
        elif mapping_type == AlegraMapping.NUMERATION and (
            local_code.startswith('receipt_')
            or local_code in (
                'gtt_support_document',
                'commission_support_document',
                'commission_journal',
                'caja_cuenta_cobro',
                'caja_legalization_journal',
            )
        ):
            # Receipt / GTT / comisiones numbering can vary per project, with optional fallback to company default.
            if self.proyecto:
                qs = qs.filter(Q(proyecto=self.proyecto) | Q(proyecto__isnull=True))
            else:
                qs = qs.filter(proyecto__isnull=True)
        elif mapping_type == AlegraMapping.NUMERATION:
            qs = qs.filter(proyecto__isnull=True)
        elif mapping_type == AlegraMapping.CATEGORY and local_model == 'andinasoft.formas_pago':
            # Débito por forma de pago (recibos): una fila por descripcion en formas_pago del proyecto.
            if self.proyecto:
                qs = qs.filter(proyecto=self.proyecto)
            else:
                qs = qs.filter(proyecto__isnull=True)
        elif mapping_type == AlegraMapping.CATEGORY and local_code in (
            'receipt_client_advance',
            'gtt_cxp',
            'gtt_expense',
            'commission_expense',
            'commission_debit',
            'commission_credit',
            'commission_amount_source',
            'commission_amount_source_internal',
            'commission_amount_source_external',
            'caja_cxp',
            'caja_ajuste_aproximacion',
        ):
            # Project-specific category with optional company-level fallback.
            if self.proyecto:
                qs = qs.filter(Q(proyecto=self.proyecto) | Q(proyecto__isnull=True))
            else:
                qs = qs.filter(proyecto__isnull=True)
        elif mapping_type == AlegraMapping.COST_CENTER and local_model == 'andinasoft.proyectos':
            if self.proyecto:
                qs = qs.filter(proyecto=self.proyecto)
            else:
                qs = qs.filter(proyecto__isnull=True)
        else:
            # Default: company-level mapping
            qs = qs.filter(proyecto__isnull=True)

        if local_model:
            qs = qs.filter(local_model=local_model)
        if local_pk != '':
            qs = qs.filter(local_pk=local_pk)
        if local_code != '':
            qs = qs.filter(local_code=local_code)

        mapping = qs.order_by('-proyecto_id', '-updated_at').first()
        if mapping:
            return mapping.alegra_id
        if not required:
            return None

        project = self.proyecto.pk if self.proyecto else 'empresa'
        key_parts = []
        if local_model:
            key_parts.append(f'model={local_model}')
        if local_pk not in (None, ''):
            key_parts.append(f'pk={local_pk}')
        if local_code not in (None, ''):
            key_parts.append(f'code={local_code}')
        key = ', '.join(key_parts) or 'sin llave local'
        raise AlegraConfigurationError(
            f'Falta mapeo Alegra tipo "{mapping_type}" para empresa {self.empresa.pk}, '
            f'proyecto {project} ({key}).'
        )

    def bank_account_for_account(self, cuenta):
        return self.get(
            AlegraMapping.BANK_ACCOUNT,
            local_model='andinasoft.cuentas_pagos',
            local_pk=cuenta.pk,
        )

    def category_for_code(self, account_code, *, required=True):
        return self.get(AlegraMapping.CATEGORY, local_code=str(account_code), required=required)

    def category_for_puc_code(self, account_code, *, required=False):
        """
        Categoría Alegra para un código PUC (egreso / journal).
        Orden: local_code exacto → interfaz cxp_credito_1 (descripción «{código} · …») → interfaz por cuenta_credito_1 → default_cxp.
        """
        code = str(account_code or '').strip()
        if not code:
            if required:
                raise AlegraConfigurationError(
                    f'Código PUC vacío para categoría Alegra (empresa {self.empresa.pk}).'
                )
            return None

        cat_id = self.get(AlegraMapping.CATEGORY, local_code=code, required=False)
        if cat_id:
            return cat_id

        row = (
            AlegraMapping.objects.filter(
                empresa_id=self.empresa.pk,
                proyecto__isnull=True,
                mapping_type=AlegraMapping.CATEGORY,
                local_code='cxp_credito_1',
                active=True,
                description__startswith=code,
            )
            .order_by('-updated_at')
            .first()
        )
        if row:
            return row.alegra_id

        from accounting.models import info_interfaces

        iface = info_interfaces.objects.filter(
            empresa_id=self.empresa.pk,
            cuenta_credito_1=code,
        ).first()
        if iface:
            cat_id = self.get(
                AlegraMapping.CATEGORY,
                local_model='accounting.info_interfaces',
                local_pk=str(iface.pk),
                local_code='cxp_credito_1',
                required=False,
            )
            if cat_id:
                return cat_id

        cat_id = self.get(AlegraMapping.CATEGORY, local_code='default_cxp', required=False)
        if cat_id or not required:
            return cat_id
        raise AlegraConfigurationError(
            f'Falta mapeo Alegra categoría para cuenta PUC {code} en empresa {self.empresa.pk}. '
            f'Configure en Referencias → Egresos (interfaces o código {code}).'
        )

    def sync_puc_category_mapping(self, account_code, alegra_category_id=None, *, description=''):
        """
        Persiste PUC → categoría Alegra (como bill en webhook).
        Si no se pasa alegra_category_id, lo resuelve vía interfaces Referencias / default_cxp.
        """
        code = str(account_code or '').strip()
        if not code:
            return None
        cat_id = str(alegra_category_id or '').strip() or None
        if not cat_id:
            cat_id = self.category_for_puc_code(code, required=False)
        if not cat_id:
            return None
        desc = (description or '').strip()[:255] or code
        AlegraMapping.objects.update_or_create(
            empresa_id=self.empresa.pk,
            proyecto=None,
            mapping_type=AlegraMapping.CATEGORY,
            local_model='',
            local_pk='',
            local_code=code,
            defaults={
                'alegra_id': cat_id,
                'description': desc,
                'active': True,
            },
        )
        return cat_id

    def contact_for_cliente(self, cliente_id):
        return self.get(AlegraMapping.CONTACT, local_model='andinasoft.clientes', local_pk=cliente_id)

    def contact_for_asesor(self, asesor_id):
        return self.get(AlegraMapping.CONTACT, local_model='andinasoft.asesores', local_pk=asesor_id)

    def contact_for_empresa(self, empresa_id):
        return self.get(AlegraMapping.CONTACT, local_model='andinasoft.empresas', local_pk=empresa_id)

    def contact_by_identification(self, identification, *, prefer_types=None, required=True):
        """
        Resolve Alegra contact id by identification (NIT/CC) using `AlegraContactIndex`.
        `prefer_types` can be ['provider','client'] etc.
        """
        ident = re.sub(r'[^0-9A-Za-z]', '', str(identification or '')).strip().upper()
        if not ident:
            if required:
                raise AlegraConfigurationError(f'Identificación inválida para resolver contacto en empresa {self.empresa.pk}.')
            return None
        variants = {ident}
        if ident.isdigit() and len(ident) >= 6:
            variants.add(ident[:-1])  # allow match without DV

        prefer_types = prefer_types or [AlegraContactIndex.TYPE_PROVIDER, AlegraContactIndex.TYPE_CLIENT]
        for t in prefer_types:
            row = AlegraContactIndex.objects.filter(
                empresa_id=self.empresa.pk,
                contact_type=t,
                identification__in=list(variants),
            ).order_by('-updated_at').first()
            if row:
                return str(row.alegra_id)

        # Last attempt: any type
        row = AlegraContactIndex.objects.filter(
            empresa_id=self.empresa.pk,
            identification__in=list(variants),
        ).order_by('-updated_at').first()
        if row:
            return str(row.alegra_id)

        if not required:
            return None
        raise AlegraConfigurationError(
            f'Falta contacto en índice Alegra para empresa {self.empresa.pk} (identification={ident}). '
            f'Sincroniza contactos o enlázalo manualmente.'
        )

    def cost_center_for_project(self, required=True):
        if not self.proyecto:
            return None if not required else self.get(AlegraMapping.COST_CENTER, local_code='company_default')
        return self.get(
            AlegraMapping.COST_CENTER,
            local_model='andinasoft.proyectos',
            local_pk=self.proyecto.pk,
            required=required,
        )

    def cost_center_for_commission(self, required=False):
        """Centro de costo por proyecto para comisiones (Referencias → Comisiones)."""
        if not self.proyecto:
            return None
        return self.get(
            AlegraMapping.COST_CENTER,
            local_model='andinasoft.proyectos',
            local_pk=self.proyecto.pk,
            local_code='commission',
            required=required,
        )

    def receipt_forma_pago_config(self, forma_pago_descripcion, *, required=True):
        """
        Configuración de débito por forma de pago (categoría + intercompany opcional).
        Referencias → Recibos: local_model=andinasoft.formas_pago, local_code=receipt_debit.
        alegra_payload: { intercompany: bool, counterparty_nit: str }
        """
        desc = str(forma_pago_descripcion or '').strip()
        if not desc:
            if required:
                project = self.proyecto.pk if self.proyecto else 'empresa'
                raise AlegraConfigurationError(
                    f'El recibo no tiene forma de pago para resolver débito (proyecto {project}).'
                )
            return None
        if not self.proyecto:
            if required:
                raise AlegraConfigurationError(
                    f'Falta proyecto para mapeo de forma de pago «{desc}» (empresa {self.empresa.pk}).'
                )
            return None
        mapping = AlegraMapping.objects.filter(
            empresa_id=self.empresa.pk,
            proyecto=self.proyecto,
            mapping_type=AlegraMapping.CATEGORY,
            local_model='andinasoft.formas_pago',
            local_pk=desc,
            local_code='receipt_debit',
            active=True,
        ).order_by('-updated_at').first()
        if not mapping:
            if not required:
                return None
            raise AlegraConfigurationError(
                f'Falta mapeo Alegra de débito para forma de pago «{desc}» '
                f'(proyecto {self.proyecto.pk}).'
            )
        payload = mapping.alegra_payload if isinstance(mapping.alegra_payload, dict) else {}
        nit = str(payload.get('counterparty_nit') or '').strip()
        return {
            'category_id': mapping.alegra_id,
            'intercompany': bool(payload.get('intercompany')),
            'counterparty_nit': nit,
        }

    def receipt_debit_for_forma_pago(self, forma_pago_descripcion, *, required=True):
        cfg = self.receipt_forma_pago_config(forma_pago_descripcion, required=required)
        if cfg is None:
            return None
        return cfg['category_id']

    def numeration(self, document_code, required=True):
        return self.get(AlegraMapping.NUMERATION, local_code=document_code, required=required)

    def retention(self, retention_code, required=True):
        return self.get(AlegraMapping.RETENTION, local_code=retention_code, required=required)

    def tax_for_impuesto(self, impuesto_pk, *, required=True):
        """Impuesto Alegra (IVA) mapeado desde accounting.impuestos_legalizacion."""
        pk = str(impuesto_pk or '').strip()
        if not pk:
            if required:
                raise AlegraConfigurationError('Falta tipo de IVA en el gasto de caja.')
            return None
        return self.get(
            AlegraMapping.TAX,
            local_model='accounting.impuestos_legalizacion',
            local_pk=pk,
            local_code='impuesto_tax',
            required=required,
        )

    def retention_for_impuesto(self, impuesto_pk, *, required=True):
        """Retencion Alegra mapeada desde accounting.impuestos_legalizacion (tipo retefuente)."""
        pk = str(impuesto_pk or '').strip()
        if not pk:
            if required:
                raise AlegraConfigurationError('Falta tipo de retencion en el gasto de caja.')
            return None
        mapped = self.get(
            AlegraMapping.RETENTION,
            local_model='accounting.impuestos_legalizacion',
            local_pk=pk,
            local_code='impuesto_retention',
            required=False,
        )
        if mapped:
            return mapped
        if required:
            raise AlegraConfigurationError(
                f'Falta mapeo Alegra de retencion para impuestos_legalizacion pk={pk}. '
                f'Configure en Referencias → Caja efectivo → Impuestos.'
            )
        return None

    def commission_amount_source(self, *, for_tipo, default='net', required=False):
        """
        Base del valor de comisión por proyecto y tipo de asesor.
        for_tipo: 'internal' | 'external'
        Mapeos: commission_amount_source_internal / commission_amount_source_external.
        """
        tipo = (for_tipo or '').strip().lower()
        if tipo not in ('internal', 'external'):
            raise ValueError(f'for_tipo debe ser internal o external, recibido: {for_tipo!r}')
        local_code = (
            'commission_amount_source_internal'
            if tipo == 'internal'
            else 'commission_amount_source_external'
        )
        mode = self.get(AlegraMapping.CATEGORY, local_code=local_code, required=False)
        if mode not in ('net', 'gross'):
            # Compatibilidad con mapeo único anterior
            legacy = self.get(
                AlegraMapping.CATEGORY,
                local_code='commission_amount_source',
                required=False,
            )
            if legacy in ('net', 'gross'):
                mode = legacy
        if mode in ('net', 'gross'):
            return mode
        if required:
            project = self.proyecto.pk if self.proyecto else 'empresa'
            label = 'internos' if tipo == 'internal' else 'externos'
            raise AlegraConfigurationError(
                f'Falta configurar valor del pago (neto/bruto) para asesores {label}, '
                f'proyecto {project}, en Referencias → Comisiones.'
            )
        return default if default in ('net', 'gross') else 'net'

    def payment_method(self, local_method, required=True):
        return self.get(AlegraMapping.PAYMENT_METHOD, local_code=local_method, required=required)

    def bill_for_factura(self, factura_id, required=False, *, factura=None):
        """
        Id numérico del bill en Alegra para POST /payments (bills[]).
        Orden: AlegraMapping → factura tipo bill con alegra_bill_id.
        """
        mapped = self.get(
            AlegraMapping.BILL,
            local_model='accounting.Facturas',
            local_pk=str(factura_id),
            required=False,
        )
        if mapped:
            return mapped
        fac = factura
        if fac is None:
            from accounting.models import Facturas
            fac = Facturas.objects.filter(pk=factura_id).first()
        if not fac:
            if required:
                raise AlegraConfigurationError(
                    f'No hay radicado {factura_id} para resolver bill en empresa {self.empresa.pk}.'
                )
            return None
        doc_type = (getattr(fac, 'alegra_document_type', None) or '').strip()
        if doc_type and doc_type != ALEGRA_DOC_BILL:
            return None
        _, bill_id = parse_alegra_bill_id_for_api(fac.alegra_bill_id)
        if bill_id:
            return bill_id
        if required:
            raise AlegraConfigurationError(
                f'El radicado {factura_id} no tiene bill de Alegra enlazado (tipo={doc_type or "sin tipo"}).'
            )
        return None
