from django.contrib.auth.models import User
from django.test import TestCase

from accounting.alcance import (
    filter_facturas_qs,
    get_alcance,
    oficinas_choices_for,
    resolve_oficina_filter,
    user_can_access,
)
from accounting.models import Facturas, GastoNotificacionOficina, UsuarioAccountingAlcance
from andinasoft.models import empresas


class AlcanceUnitTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        GastoNotificacionOficina.objects.get_or_create(
            codigo='MEDELLIN', defaults={'etiqueta': 'MEDELLIN'}
        )
        GastoNotificacionOficina.objects.get_or_create(
            codigo='MONTERIA', defaults={'etiqueta': 'MONTERIA'}
        )
        cls.user = User.objects.create_user('alcance_user', password='x')
        cls.superuser = User.objects.create_superuser('alcance_admin', 'a@a.com', 'x')
        cls.emp_a, _ = empresas.objects.get_or_create(
            Nit='900111222',
            defaults={'nombre': 'Empresa A alcance'},
        )
        cls.emp_b, _ = empresas.objects.get_or_create(
            Nit='900333444',
            defaults={'nombre': 'Empresa B alcance'},
        )

    def test_sin_fila_deniega(self):
        self.assertIsNone(get_alcance(self.user))
        self.assertFalse(user_can_access(self.user, empresa_id=self.emp_a.pk, oficina='MEDELLIN'))
        self.assertEqual(oficinas_choices_for(self.user), [])

    def test_superuser_bypass(self):
        alcance = get_alcance(self.superuser)
        self.assertIsNotNone(alcance)
        self.assertIsNone(alcance['empresa_ids'])
        self.assertIsNone(alcance['oficinas'])
        self.assertTrue(user_can_access(self.superuser, empresa_id=self.emp_a.pk, oficina='MONTERIA'))

    def test_fila_m2m_vacios_acceso_total(self):
        UsuarioAccountingAlcance.objects.create(user=self.user, activo=True)
        alcance = get_alcance(self.user)
        self.assertIsNotNone(alcance)
        self.assertIsNone(alcance['empresa_ids'])
        self.assertIsNone(alcance['oficinas'])
        self.assertTrue(user_can_access(self.user, empresa_id=self.emp_b.pk, oficina='MEDELLIN'))
        choices = oficinas_choices_for(self.user, include_todas=True)
        self.assertEqual(choices[0][0], 'TODAS')
        self.assertIn(('MEDELLIN', 'MEDELLIN'), choices)

    def test_solo_oficina(self):
        entry = UsuarioAccountingAlcance.objects.create(user=self.user, activo=True)
        entry.oficinas.add(GastoNotificacionOficina.objects.get(codigo='MEDELLIN'))
        self.assertTrue(user_can_access(self.user, empresa_id=self.emp_a.pk, oficina='MEDELLIN'))
        self.assertFalse(user_can_access(self.user, empresa_id=self.emp_a.pk, oficina='MONTERIA'))
        ok, codigo = resolve_oficina_filter(self.user, 'MONTERIA')
        self.assertFalse(ok)
        ok, codigo = resolve_oficina_filter(self.user, 'TODAS')
        self.assertTrue(ok)
        self.assertEqual(codigo, 'TODAS')

    def test_solo_empresa(self):
        entry = UsuarioAccountingAlcance.objects.create(user=self.user, activo=True)
        entry.empresas.add(self.emp_a)
        self.assertTrue(user_can_access(self.user, empresa_id=self.emp_a.pk, oficina='MONTERIA'))
        self.assertFalse(user_can_access(self.user, empresa_id=self.emp_b.pk, oficina='MONTERIA'))

    def test_empresa_y_oficina(self):
        entry = UsuarioAccountingAlcance.objects.create(user=self.user, activo=True)
        entry.empresas.add(self.emp_a)
        entry.oficinas.add(GastoNotificacionOficina.objects.get(codigo='MEDELLIN'))
        self.assertTrue(user_can_access(self.user, empresa_id=self.emp_a.pk, oficina='MEDELLIN'))
        self.assertFalse(user_can_access(self.user, empresa_id=self.emp_a.pk, oficina='MONTERIA'))
        self.assertFalse(user_can_access(self.user, empresa_id=self.emp_b.pk, oficina='MEDELLIN'))

    def test_inactivo_deniega(self):
        UsuarioAccountingAlcance.objects.create(user=self.user, activo=False)
        self.assertIsNone(get_alcance(self.user))

    def test_filter_facturas_qs(self):
        entry = UsuarioAccountingAlcance.objects.create(user=self.user, activo=True)
        entry.empresas.add(self.emp_a)
        entry.oficinas.add(GastoNotificacionOficina.objects.get(codigo='MEDELLIN'))

        Facturas.objects.create(
            empresa=self.emp_a,
            oficina='MEDELLIN',
            valor=1000,
            nrofactura='T-ALC-1',
            **Facturas.kwargs_gasto_no_aplica(),
        )
        Facturas.objects.create(
            empresa=self.emp_a,
            oficina='MONTERIA',
            valor=2000,
            nrofactura='T-ALC-2',
            **Facturas.kwargs_gasto_no_aplica(),
        )
        Facturas.objects.create(
            empresa=self.emp_b,
            oficina='MEDELLIN',
            valor=3000,
            nrofactura='T-ALC-3',
            **Facturas.kwargs_gasto_no_aplica(),
        )
        qs = filter_facturas_qs(Facturas.objects.filter(nrofactura__startswith='T-ALC-'), self.user)
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().nrofactura, 'T-ALC-1')
