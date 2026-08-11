"""
Tests del generador dinamico de bonos de cartera (sin BD).
"""
from decimal import Decimal
from types import SimpleNamespace

from django.test import SimpleTestCase

from andinasoft.bonos_cartera_excel import (
    TASA_OV_DEFAULT,
    agregar_fila_override,
    bono_por_escala,
    construir_override,
    es_cashout,
    generar_libro_bonos,
    normalizar_gestor,
)
from collections import defaultdict


def _fila(**kwargs):
    defaults = dict(
        pk='ADJ1',
        cliente='Cliente',
        estado='Aprobado',
        origen='Normal',
        venta_mes='No',
        tipocartera='Comercial',
        edad='0-30',
        ppto_mes=0,
        recaudo_mes=0,
        ppto_vencido=0,
        recaudo_vencido=0,
        presupuesto=1_000_000,
        recaudo_pptado=800_000,
        recaudo_nopptado=50_000,
        recaudo_total=850_000,
        asesor='ANA PEREZ',
        cashout=None,
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


class BonosHelpersTests(SimpleTestCase):
    def test_normalizar_gestor(self):
        self.assertEqual(normalizar_gestor('Ana Perez'), 'ANA PEREZ')
        self.assertEqual(normalizar_gestor(''), 'SIN GESTOR')

    def test_es_cashout(self):
        self.assertFalse(es_cashout(None))
        self.assertFalse(es_cashout(''))
        self.assertFalse(es_cashout('No'))
        self.assertTrue(es_cashout('Si'))
        self.assertTrue(es_cashout('cashout'))

    def test_bono_por_escala(self):
        self.assertEqual(bono_por_escala(Decimal('0.39')), Decimal('0'))
        self.assertEqual(bono_por_escala(Decimal('0.40')), Decimal('0.0010'))
        self.assertEqual(bono_por_escala(Decimal('0.95')), Decimal('0.0014'))
        self.assertEqual(bono_por_escala(Decimal('1.2')), Decimal('0.0016'))


class BonosAgregacionTests(SimpleTestCase):
    def test_override_dos_proyectos_mismo_gestor(self):
        acc = defaultdict(lambda: {
            'presupuesto': Decimal('0'),
            'rcdo_pptado': Decimal('0'),
            'rcdo_nopptado_sin_cashout': Decimal('0'),
            'filas': 0,
        })
        agregar_fila_override(acc, 'Oasis', _fila(presupuesto=1_000_000, recaudo_pptado=1_000_000, recaudo_nopptado=100_000))
        agregar_fila_override(acc, 'Perla del Mar', _fila(presupuesto=500_000, recaudo_pptado=400_000, recaudo_nopptado=0))
        # juridico ignorado
        agregar_fila_override(acc, 'Oasis', _fila(asesor='JURIDICO', presupuesto=9_999_999, recaudo_pptado=9_999_999))

        filas, totales = construir_override(acc)
        self.assertEqual(len(filas), 2)
        self.assertEqual(len(totales), 1)
        self.assertEqual(totales[0].gestor, 'ANA PEREZ')

        # Oasis: (1_000_000 + 100_000) * 0.002 = 2200
        oasis = next(f for f in filas if f.proyecto == 'Oasis')
        self.assertEqual(oasis.bono_override, Decimal('2200.00'))
        self.assertEqual(oasis.cumplimiento, Decimal('1.0000'))

        # Perla: (400_000 + 0) * 0.002 = 800
        perla = next(f for f in filas if f.proyecto == 'Perla del Mar')
        self.assertEqual(perla.bono_override, Decimal('800.00'))
        self.assertEqual(totales[0].bono_override, Decimal('3000.00'))

    def test_cashout_excluye_nopptado(self):
        acc = defaultdict(lambda: {
            'presupuesto': Decimal('0'),
            'rcdo_pptado': Decimal('0'),
            'rcdo_nopptado_sin_cashout': Decimal('0'),
            'filas': 0,
        })
        agregar_fila_override(
            acc,
            'Oasis',
            _fila(recaudo_pptado=0, presupuesto=100, recaudo_nopptado=50_000, cashout='Si'),
        )
        filas, _ = construir_override(acc)
        self.assertEqual(filas[0].rcdo_nopptado_sin_cashout, Decimal('0.00'))
        self.assertEqual(filas[0].bono_override, Decimal('0.00'))

    def test_generar_libro_sheets_dinamicas(self):
        datos = {
            'Oasis': [_fila()],
            'Proyecto Nuevo X': [_fila(asesor='NUEVO GESTOR', presupuesto=2000, recaudo_pptado=2000, recaudo_nopptado=0)],
        }
        wb = generar_libro_bonos(datos)
        self.assertIn('Override', wb.sheetnames)
        self.assertIn('Escalas', wb.sheetnames)
        self.assertIn('Oasis', wb.sheetnames)
        self.assertIn('Proyecto Nuevo X', wb.sheetnames)
        # Override debe listar ambos gestores
        ov = wb['Override']
        gestores = {ov.cell(r, 1).value for r in range(2, 20) if ov.cell(r, 1).value}
        self.assertIn('ANA PEREZ', gestores)
        self.assertIn('NUEVO GESTOR', gestores)
        self.assertEqual(TASA_OV_DEFAULT, Decimal('0.002'))
