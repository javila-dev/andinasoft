"""
Utilidades compartidas para los tools MCP.
"""


def resolve_proyecto(proyecto: str):
    """
    Resuelve el nombre exacto del proyecto por coincidencia exacta (iexact)
    o parcial (icontains).

    Returns:
        (nombre_exacto, None)  si se encontró un único proyecto
        (None, dict_error)     si no se encontró o hay ambigüedad
    """
    from andinasoft.models import proyectos as ProyectosModel

    proyecto = (proyecto or '').strip()
    if not proyecto:
        return None, {'error': 'Debes enviar el parámetro "proyecto".'}

    # Intento 1: coincidencia exacta (case-insensitive)
    qs = ProyectosModel.objects.filter(proyecto__iexact=proyecto)
    if qs.exists():
        return qs.first().proyecto, None

    # Intento 2: búsqueda parcial
    qs = ProyectosModel.objects.filter(proyecto__icontains=proyecto)
    count = qs.count()
    if count == 1:
        return qs.first().proyecto, None
    elif count > 1:
        nombres = ', '.join(p.proyecto for p in qs)
        return None, {
            'error': f'El nombre "{proyecto}" coincide con varios proyectos: {nombres}. Sé más específico.'
        }
    else:
        return None, {
            'error': f'No encontramos el proyecto "{proyecto}". Pregunta al usuario cuál proyecto quiere consultar.'
        }
