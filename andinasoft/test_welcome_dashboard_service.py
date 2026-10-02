"""
Tests unitarios del dashboard de inicio (/welcome).

Solo helpers puros y mocks — no requieren BD de proyecto.
"""
import datetime
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from andinasoft import welcome_dashboard_service as svc


class SeccionesTests(SimpleTestCase):
    def test_todas_las_metricas_tienen_fuente(self):
        for section in svc.SECTIONS:
            for kpi in section['kpis']:
                self.assertIn(kpi['metric'], svc.METRIC_SOURCE, kpi['metric'])

    def test_superusuario_ve_todas(self):
        keys = [s['key'] for s in svc.visible_sections([], True)]
        self.assertNotIn('pendientes', keys)
        self.assertEqual(len(keys), len(svc.SECTIONS) - 1)

    def test_secciones_segun_grupos(self):
        keys = [s['key'] for s in svc.visible_sections(['Gestor Cartera', 'Otro'], False)]
        self.assertEqual(keys, ['cartera'])

    def test_sin_grupos_no_hay_secciones_ni_fuentes(self):
        sections = svc.visible_sections([], False)
        self.assertEqual(sections, [])
        self.assertEqual(svc.required_sources(sections), set())

    def test_solo_se_piden_las_fuentes_necesarias(self):
        sections = svc.visible_sections(['Servicio Cliente'], False)
        self.assertEqual(svc.required_sources(sections), {'compromisos', 'promesas', 'pqrs'})
        self.assertEqual(svc.required_sources(svc.visible_sections(['Recepcion'], False)), set())

    def test_graficas_agregan_sus_fuentes(self):
        sections = svc.visible_sections(['Jefe Ventas'], False)
        self.assertTrue({'asesor_trend', 'inmuebles', 'ventas_asesor'} <= svc.required_sources(sections))

    def test_pendientes_solo_si_tiene_algo_propio(self):
        self.assertEqual(svc.visible_sections([], False, has_pendientes=False), [])
        keys = [s['key'] for s in svc.visible_sections([], False, has_pendientes=True)]
        self.assertEqual(keys, ['pendientes'])
        keys = [s['key'] for s in svc.visible_sections([], True, has_pendientes=True)]
        self.assertIn('pendientes', keys)

    def test_tesoreria_ve_recaudos_y_pagos(self):
        keys = [s['key'] for s in svc.visible_sections(['Tesoreria'], False)]
        self.assertEqual(keys, ['recaudos', 'pagos'])

    def test_sin_alcance_contable_oculta_accounting(self):
        keys = [s['key'] for s in svc.visible_sections(['Tesoreria', 'Contabilidad'], False, has_accounting=False)]
        self.assertEqual(keys, ['recaudos'])
        keys = [s['key'] for s in svc.visible_sections([], True, has_accounting=False)]
        self.assertFalse({'pagos', 'contabilidad', 'recepcion'} & set(keys))

    def test_no_hay_secciones_de_proyectos_de_obra(self):
        self.assertNotIn('gerencia_proyectos', [s['key'] for s in svc.SECTIONS])


class AccesosRapidosTests(SimpleTestCase):
    def test_sin_repetidos_y_por_rondas(self):
        sections = svc.visible_sections(['Operaciones', 'Asistente Operaciones', 'Servicio Cliente'], False)
        hrefs = [s['href'] for s in svc.build_shortcuts(sections)]
        self.assertEqual(len(hrefs), len(set(hrefs)))
        # Primero el principal de cada sección.
        self.assertEqual(hrefs[:2], ['/projectselector/nueva_adjudicacion', '/servicio_cliente/dashboard'])

    def test_limite(self):
        self.assertEqual(len(svc.build_shortcuts(svc.visible_sections([], True))), svc.MAX_SHORTCUTS)


class GraficasTests(SimpleTestCase):
    def test_meses_de_tendencia_cruzan_anio(self):
        months = svc.trend_months(datetime.date(2026, 2, 15))
        self.assertEqual(months[0], datetime.date(2025, 9, 1))
        self.assertEqual(months[-1], datetime.date(2026, 2, 1))

    def test_columnas_suman_proyectos_y_marcan_mes_en_curso(self):
        today = datetime.date(2026, 10, 2)
        series = {
            'A': {'asesor_trend': {datetime.date(2026, 10, 1): {'total': 2}}},
            'B': {'asesor_trend': {datetime.date(2026, 10, 1): {'total': 3},
                                   datetime.date(2026, 5, 1): {'total': 1}}},
        }
        chart = svc._columns_chart(svc.CHARTS['asesor_6m'], series, today)
        self.assertEqual([p['value'] for p in chart['points']], [1, 0, 0, 0, 0, 5])
        self.assertEqual([p['partial'] for p in chart['points']], [False] * 5 + [True])

    def test_grafica_global_usa_series_globales(self):
        today = datetime.date(2026, 10, 2)
        global_series = {'pagos_trend': {datetime.date(2026, 9, 1): {'valor': 100}}}
        chart = svc._columns_chart(svc.CHARTS['pagos_6m'], {'A': {}}, today, global_series)
        self.assertEqual(chart['points'][-2]['value'], 100)

    def test_radicados_por_oficina_apilados(self):
        today = datetime.date(2026, 10, 2)
        g = {'radicados_trend': {datetime.date(2026, 9, 1): {'MEDELLIN': 200, 'MONTERIA': 51}}}
        chart = svc._stacked_columns_chart(svc.CHARTS['radicados_6m'], g, today)
        sep = chart['points'][-2]
        self.assertEqual((sep['values'], sep['total']), ({'MEDELLIN': 200, 'MONTERIA': 51}, 251))
        self.assertEqual([c['key'] for c in chart['categories']], ['MEDELLIN', 'MONTERIA'])
        self.assertTrue(chart['points'][-1]['partial'])

    def test_categorias_inventario(self):
        self.assertEqual(svc.inventario_categoria('Libre'), 'libre')
        self.assertEqual(svc.inventario_categoria(' sin Liberar '), 'no_disponible')
        self.assertEqual(svc.inventario_categoria('Bloqueado'), 'no_disponible')
        self.assertIsNone(svc.inventario_categoria('Eliminado'))

    def test_grafica_compartida_se_muestra_una_vez(self):
        sections = svc.visible_sections(['Gerencia Comercial', 'Jefe Ventas'], False)
        charts = {k: {} for k in ('asesor_6m', 'inventario')}
        built = svc._build_sections(sections, {}, charts)
        self.assertEqual([s['charts'] for s in built], [['inventario'], ['asesor_6m']])

    def test_gerencia_comercial_ve_ventas_por_asesor(self):
        keys = [s['key'] for s in svc.visible_sections(['Gerencia Comercial'], False)]
        self.assertEqual(keys, ['comercial', 'ventas_asesor'])


class AsesorTests(SimpleTestCase):
    def _q(self, claves):
        with patch.object(svc.AsignacionComisiones, 'objects') as manager:
            manager.using.return_value.filter.return_value.values_list.return_value = claves
            return svc.ventas_de_asesor_q('P', '123')

    def test_escala_por_venta_y_por_adjudicacion(self):
        q = self._q(['368', 'ADJ781', None])
        self.assertIn(('id_venta__in', [368]), q.children)
        self.assertIn(('adj_id__in', ['ADJ781']), q.children)

    def test_asesor_sin_escala_no_tiene_ventas(self):
        self.assertIsNone(self._q([]))


class MosaicoTests(SimpleTestCase):
    def _block(self, size):
        pref, minimum = svc.SPANS[size]
        return {'size': size, 'pref': pref, 'min': minimum, 'span': pref}

    def _rows(self, layout):
        rows, acc = [], 0
        for item in layout:
            acc += item['span']
            if acc == 12:
                rows.append(acc)
                acc = 0
        return rows, acc

    def test_filas_completas_sin_huecos(self):
        sizes = ['full', 'compact', 'wide', 'compact', 'compact', 'wide', 'wide', 'half', 'compact', 'wide', 'half', 'full']
        layout = svc.pack_layout([self._block(z) for z in sizes])
        rows, resto = self._rows(layout)
        self.assertEqual(resto, 0)
        self.assertEqual(sum(i['span'] for i in layout), 12 * len(rows))
        self.assertTrue(all(i['span'] >= i['min'] for i in layout))

    def test_dos_anchas_se_emparejan(self):
        layout = svc.pack_layout([self._block('wide'), self._block('wide')])
        self.assertEqual([i['span'] for i in layout], [6, 6])

    def test_ancha_con_compacta(self):
        layout = svc.pack_layout([self._block('wide'), self._block('compact')])
        self.assertEqual([i['span'] for i in layout], [8, 4])

    def test_tamano_de_seccion(self):
        self.assertEqual(svc.section_size(['a', 'b'], [1]), 'full')
        self.assertEqual(svc.section_size(['a'], [1]), 'wide')
        self.assertEqual(svc.section_size([], [1, 2, 3, 4]), 'half')
        self.assertEqual(svc.section_size([], [1, 2]), 'compact')

    def test_flacas_se_apilan_de_a_dos(self):
        secciones = [
            {'key': 'a', 'size': 'wide'},
            {'key': 'op', 'size': 'half', 'slim': True},
            {'key': 'alta', 'size': 'large'},
            {'key': 'car', 'size': 'half', 'slim': True},
        ]
        layout = svc.build_layout(secciones)
        resumen = [(i['kind'], [s['key'] for s in i['sections']], i['span']) for i in layout]
        self.assertIn(('stack', ['op', 'car'], 6), resumen)
        self.assertEqual(sum(i['span'] for i in layout) % 12, 0)

    def test_flaca_sola_no_se_apila(self):
        layout = svc.build_layout([{'key': 'op', 'size': 'half', 'slim': True}, {'key': 'x', 'size': 'half'}])
        self.assertEqual([i['kind'] for i in layout], ['section', 'section'])

    def test_layout_solo_secciones_y_tabla(self):
        layout = svc.build_layout([{'size': 'wide'}, {'size': 'compact'}, {'size': 'full'}])
        self.assertEqual([(i['kind'], i['span']) for i in layout], [('section', 8), ('section', 4), ('section', 12)])


class FormatoTests(SimpleTestCase):
    def test_montos_grandes_en_millones(self):
        self.assertEqual(svc.format_kpi(1653320325, 'money'), ('$1.653 M', '$1.653.320.325'))
        self.assertEqual(svc.format_kpi(850000, 'money'), ('$850.000', '$850.000'))
        self.assertEqual(svc.format_kpi(1234), ('1.234', '1.234'))


class EmpresasTests(SimpleTestCase):
    def test_nombre_corto_sin_sufijo_societario(self):
        self.assertEqual(svc.nombre_corto_empresa('ANDINA CONCEPTOS INMOBILIARIOS SAS'), 'Andina Conceptos Inmobiliarios')
        self.assertEqual(svc.nombre_corto_empresa('Promotora Westville S.A.S.'), 'Promotora Westville')
        self.assertEqual(svc.nombre_corto_empresa('CONSTRUCTORA ROJOZ'), 'Constructora Rojoz')

    def test_sin_alcance_no_hay_empresas(self):
        self.assertEqual(svc.user_empresas(None), [])


class PendientesTests(SimpleTestCase):
    def test_pendientes_en_cero_no_se_muestran(self):
        sections = svc.visible_sections([], False, has_pendientes=True)
        self.assertEqual(svc._build_sections(sections, {}, {}), [])
        built = svc._build_sections(sections, {'mis_anticipos_por_aprobar': 1}, {})
        self.assertEqual([s['key'] for s in built], ['pendientes'])


class KpisTests(SimpleTestCase):
    def test_alerta_solo_si_warn_y_mayor_a_cero(self):
        sections = svc.visible_sections(['Contabilidad'], False)
        built = svc._build_sections(sections, {'facturas_radicadas_mes': 4, 'facturas_por_causar': 2}, {})
        alerts = {k['metric']: k['alert'] for k in built[0]['kpis'] if k['value']}
        self.assertEqual(alerts, {'facturas_radicadas_mes': False, 'facturas_por_causar': True})

    def test_recepcion_ya_no_existe(self):
        self.assertNotIn('recepcion', [s['key'] for s in svc.SECTIONS])

    def test_nuevos_kpis(self):
        kpis = {s['key']: [k['metric'] for k in s['kpis']] for s in svc.SECTIONS}
        self.assertIn('desistidos_mes', kpis['operaciones'])
        self.assertTrue({'solicitudes_pendientes', 'solicitudes_manuales'} <= set(kpis['recaudos']))


def _profile(fecha, nombre='Ana'):
    return SimpleNamespace(
        fecha_nacimiento=fecha,
        user=SimpleNamespace(first_name=nombre, last_name='Pérez'),
        avatar_id=None,
        avatar=None,
    )


class CumpleanosTests(SimpleTestCase):
    def _run(self, today, profiles):
        with patch.object(svc.Profiles, 'objects') as manager:
            manager.filter.return_value.select_related.return_value = profiles
            return svc.upcoming_birthdays(today)

    def test_ventana_cruza_fin_de_anio(self):
        rows = self._run(datetime.date(2026, 12, 25), [
            _profile(datetime.date(1990, 1, 3), 'Enero'),
            _profile(datetime.date(1990, 12, 24), 'Ayer'),
            _profile(datetime.date(1990, 12, 25), 'Hoy'),
        ])
        self.assertEqual([(r['nombre'].split()[0], r['dias']) for r in rows], [('Hoy', 0), ('Enero', 9)])
        self.assertEqual(rows[1]['fecha'], datetime.date(2027, 1, 3))

    def test_29_febrero_en_anio_no_bisiesto(self):
        rows = self._run(datetime.date(2027, 2, 20), [_profile(datetime.date(2000, 2, 29))])
        self.assertEqual(rows[0]['fecha'], datetime.date(2027, 2, 28))
