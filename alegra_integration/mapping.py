from alegra_integration.exceptions import AlegraConfigurationError
import re

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
        elif mapping_type == AlegraMapping.NUMERATION and local_code.startswith('receipt_'):
            # Receipt numbering can vary per project, with optional fallback to company default.
            if self.proyecto:
                qs = qs.filter(Q(proyecto=self.proyecto) | Q(proyecto__isnull=True))
            else:
                qs = qs.filter(proyecto__isnull=True)
        elif mapping_type == AlegraMapping.NUMERATION:
            qs = qs.filter(proyecto__isnull=True)
        elif mapping_type == AlegraMapping.CATEGORY and local_code == 'receipt_client_advance':
            # This one is project-specific (each project can credit a different account),
            # but we allow fallback to company-level default when present.
            if self.proyecto:
                qs = qs.filter(Q(proyecto=self.proyecto) | Q(proyecto__isnull=True))
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

    def numeration(self, document_code, required=True):
        return self.get(AlegraMapping.NUMERATION, local_code=document_code, required=required)

    def retention(self, retention_code, required=True):
        return self.get(AlegraMapping.RETENTION, local_code=retention_code, required=required)

    def payment_method(self, local_method, required=True):
        return self.get(AlegraMapping.PAYMENT_METHOD, local_code=local_method, required=required)

    def bill_for_factura(self, factura_id, required=False):
        return self.get(
            AlegraMapping.BILL,
            local_model='accounting.Facturas',
            local_pk=factura_id,
            required=required,
        )
