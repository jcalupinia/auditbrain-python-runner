"""Catálogo de Ingresos Exentos / No Objeto (CMIE) — descripción y normativa.

GENERADO automáticamente desde el archivo del cliente
`INGRESOS EXCCENTOS.xlsx`.
NO editar a mano: regenerar con scripts/generate_catalogo_ingresos_exentos.py.

Mapea cada casillero de ingreso exento / no objeto (rango 6001-6999) a una
tupla (descripción, normativa). Lo usa el A4 Cuadro 1 para autocompletar las
columnas E (descripción del tipo de ingreso exento) y F (normativa de
respaldo) cuando traslada un casillero exento declarado en el F-101.

Cobertura: 76 casilleros definidos por el cliente.
"""
from __future__ import annotations


# casillero -> (descripcion_tipo_ingreso, normativa_respaldo)
IE_CASILLERO_INFO: dict[str, tuple[str, str]] = {
    '6002': ('Ventas Netas Locales De Bienes Gravadas Con Tarifa Diferente De O% De Iva', 'Art. 9 LRTI / norma especial aplicable'),
    '6003': ('Ventas Netas Locales Gravadas Con Tarifa Cero O Exentas De Iva', 'Art. 9 LRTI / norma especial aplicable'),
    '6004': ('Ventas Netas Locales Gravadas Con Tarifa Cero O Exentas De Iva', 'Art. 9 LRTI / norma especial aplicable'),
    '6006': ('Prestaciones De Servicios Gravadas Con Tarifa Diferente De O% De Iva', 'Art. 9 LRTI / norma especial aplicable'),
    '6007': ('Prestaciones Locales De Servicios Gravadas Con Tarifa Cero O Exentas De Iva', 'Art. 9 LRTI / norma especial aplicable'),
    '6008': ('Prestaciones Locales De Servicios Gravadas Con Tarifa Cero O Exentas De Iva', 'Art. 9 LRTI / norma especial aplicable'),
    '6010': ('Exportaciones Netas De Bienes', 'Art. 9 LRTI / norma especial aplicable'),
    '6012': ('Exportaciones Netas De Servicios', 'Art. 9 LRTI / norma especial aplicable'),
    '6014': ('Ingresos Por Prestacion De Servicios De Construccion', 'Art. 9 LRTI / norma especial aplicable'),
    '6016': ('Ingresos Obtenidos Bajo La Modalidad De Comisiones O Similares', 'Art. 9 LRTI / norma especial aplicable'),
    '6018': ('Ingresos Obtenidos Por Arrendamientos Operativos', 'Art. 9 LRTI / norma especial aplicable'),
    '6020': ('Ingresos Por Regalias Y Otras Cesiones De Derechos A Residentes O Establecidas En Ecuador', 'Art. 9 LRTI / norma especial aplicable'),
    '6022': ('Ingresos Por Regalias Y Otras Cesiones De Derechos A No Residentes Ni Establecidas En Ecuador', 'Art. 9 LRTI / norma especial aplicable'),
    '6024': ('Dividendos de sociedades residentes', 'Art. 9 LRTI (1)'),
    '6026': ('Dividendos del exterior / sociedades no residentes', 'Art. 49 LRTI'),
    '6028': ('Ganancias Netas Por Mediciones De Activos Biologicos A Valor Razonable Menos Costos De Venta', 'Art. 9 LRTI'),
    '6030': ('Ganancias Netas Por Medicion De Propiedades De Inversion A Valor Razonable', 'Art. 9 LRTI'),
    '6032': ('Ganancias Netas Por Medicion De Instrumentos Financieros A Valor Razonable', 'Art. 9 LRTI'),
    '6034': ('Ganancias Netas Por Diferencias De Cambios', 'Art. 9 LRTI'),
    '6036': ('Utilidad En Venta De Propiedades Planta Y Equipo', 'Art. 9 LRTI'),
    '6038': ('Utilidad en enajenación de derechos representativos de capital', 'Art. innumerado posterior Art. 37 LRTI'),
    '6040': ('Subvenciones gubernamentales y ayudas estatales', 'Art. 9 LRTI (21)'),
    '6042': ('Reversiones De Deterioro En El Valor De Activos Financieros (Reversion De Provisiones Para Creditos Incobrables)', 'Art. 9 LRTI'),
    '6044': ('Valor Exento Ganacias Netas Por Reversiones De Deterioro En El Valor De Inventarios', 'Art. 9 LRTI'),
    '6046': ('Reversiones De Deterioro En El Valor De Activos No Corrientes Mantenidos Para La Venta', 'Art. 9 LRTI'),
    '6048': ('Reversiones De Deterioro En El Valor De Activos Biologicos', 'Art. 9 LRTI'),
    '6050': ('Reversiones De Deterioro En El Valor De Propiedades, Planta Y Equipo', 'Art. 9 LRTI'),
    '6052': ('Reversiones De Deterioro En El Valor De Activos Intangibles', 'Art. 9 LRTI'),
    '6054': ('Reversiones De Deterioro En El Valor De Propiedades De Inversion', 'Art. 9 LRTI'),
    '6056': ('Reversiones De Deterioro En El Valor De Activos De Exploracion, Evaluacion Y Explotacion De Recursos Minerales', 'Art. 9 LRTI'),
    '6058': ('Reversiones De Deterioro En El Valor De Inversiones No Corrientes', 'Art. 9 LRTI'),
    '6060': ('Reversiones De Deterioro En El Valor De Otras', 'Art. 9 LRTI'),
    '6062': ('Reversiones De Provisiones Por Garantias', 'Art. 9 LRTI'),
    '6064': ('Reversiones De Provisiones Por Desmantelamientos', 'Art. 9 LRTI'),
    '6066': ('Reversiones De Provisiones Por Contratos Onerosos', 'Art. 9 LRTI'),
    '6068': ('Reversiones De Provisiones Por Reestructuraciones De Negocios', 'Art. 9 LRTI'),
    '6070': ('Reversiones De Provisiones Por Reembolsos A Clientes', 'Art. 9 LRTI'),
    '6072': ('Reversiones De Provisiones Por Litigios', 'Art. 9 LRTI'),
    '6074': ('Reversiones De Provisiones Por Pasivos Contingentes Asumidos En Una Combinacion De Negocios', 'Art. 9 LRTI'),
    '6076': ('Reversiones De Provisiones Otras', 'Art. 9 LRTI'),
    '6078': ('Reversiones De Pasivos Por Beneficios A Los Empleados Jubilacion Patronal Y Desahucio', 'Art. 9 LRTI'),
    '6080': ('Reversiones De Pasivos Por Beneficios A Los Empleados Otros', 'Art. 9 LRTI'),
    '6081': ('Rentas Exentas De Donaciones Y Aportaciones De Recursos Publicos', 'Art. 9 LRTI (21)'),
    '6082': ('Rentas Exentas De Donaciones Y Aportaciones De Recursos Publicos', 'Art. 9 LRTI (21)'),
    '6083': ('Rentas Exentas De Donaciones Y Aportaciones De Otras Locales', 'Art. 9 LRTI (21)'),
    '6084': ('Rentas Exentas De Donaciones Y Aportaciones De Otras Locales', 'Art. 9 LRTI (21)'),
    '6085': ('Rentas Exentas De Donaciones Y Aportaciones Del Exterior', 'Art. 9 LRTI (21)'),
    '6086': ('Rentas Exentas De Donaciones Y Aportaciones Del Exterior', 'Art. 9 LRTI (21)'),
    '6088': ('Reembolso de seguros por lucro cesante (revisión: normalmente gravado)', 'Art. 9 LRTI / norma especial aplicable'),
    '6090': ('Indemnizaciones de seguros excepto lucro cesante', 'Art. 9 LRTI (16)'),
    '6092': ('Otros ingresos del exterior', 'Art. 49 LRTI'),
    '6094': ('Otras rentas exentas', 'Art. 9 LRTI / norma especial aplicable'),
    '6096': ('Ingresos Financieros Por Arrendamiento Mercantil Relacionada Local', 'Art. 9 LRTI / norma especial aplicable'),
    '6098': ('Ingresos Financieros Por Arrendamiento Mercantil Relacionada Exterior', 'Art. 9 LRTI / norma especial aplicable'),
    '6100': ('Ingresos Financieros Por Arrendamiento Mercantil No Relacionada Local', 'Art. 9 LRTI / norma especial aplicable'),
    '6102': ('Ingresos Financieros Por Arrendamiento Mercantil No Relacionada Exterior', 'Art. 9 LRTI / norma especial aplicable'),
    '6104': ('Ingresos Financieros Por Costos De Transaccion Relacionada Local', 'Art. 9 LRTI / norma especial aplicable'),
    '6106': ('Ingresos Financieros Por Costos De Transaccion Relacionada Exterior', 'Art. 9 LRTI / norma especial aplicable'),
    '6108': ('Ingresos Financieros Por Costos De Transaccion No Relacionada Local', 'Art. 9 LRTI / norma especial aplicable'),
    '6110': ('Ingresos Financieros Por Costos De Transaccion No Relacionada Exterior', 'Art. 9 LRTI / norma especial aplicable'),
    '6112': ('Ingresos Financieros Interes Con Instituciones Financieras Relacionadas Locales / renta fija ≥180 días', 'Art. 9 LRTI (15.1)'),
    '6114': ('Ingresos Financieros Interes Con Instituciones Financieras Relacionadas Exterior / renta fija ≥180 días', 'Art. 9 LRTI (15.1)'),
    '6116': ('Ingresos Financieros Interes Con Instituciones Financieras No Relacionadas Locales / renta fija ≥180 días', 'Art. 9 LRTI (15.1)'),
    '6118': ('Ingresos Financieros Interes Con Instituciones Financieras No Relacionadas Exterior / renta fija ≥180 días', 'Art. 9 LRTI (15.1)'),
    '6120': ('Ingresos Financieros Por Intereses Devengados Con Terceros Relacionados Locales / renta fija ≥180 días', 'Art. 9 LRTI (15.1)'),
    '6122': ('Ingresos Financieros Por Intereses Devengados Con Terceros Relacionados Exterior / renta fija ≥180 días', 'Art. 9 LRTI (15.1)'),
    '6124': ('Ingresos Financieros Por Intereses Devengados Con Terceros No Relacionados Locales / renta fija ≥180 días', 'Art. 9 LRTI (15.1)'),
    '6126': ('Ingresos Financieros Por Intereses Devengados Con Terceros No Relacionados Exterior / renta fija ≥180 días', 'Art. 9 LRTI (15.1)'),
    '6128': ('Ingresos Financieros Por Intereses Implicitos Devengados Por Acuerdos Que Constituyen Efectivamente Una Transaccion Financiera O Cobro Diferido / renta fija ≥180 días', 'Art. 9 LRTI (15.1)'),
    '6130': ('Otros Ingresos Financieros / renta fija ≥180 días', 'Art. 9 LRTI (15.1)'),
    '6132': ('Valor patrimonial proporcional en asociadas y negocios conjuntos', 'Art. innumerado posterior Art. 37 LRTI'),
    '6134': ('Otros Ingresos No Operacionales', 'Art. 9 LRTI / norma especial aplicable'),
    '6136': ('Ganancias Netas Procedentes De Actividades Discontinuadas', 'Art. 9 LRTI / norma especial aplicable'),
    '6242': ('Por Ingresos Financieros Prestacion De Servicios De Custodia De Activos Financieros', 'Art. 9 LRTI (15.1)'),
    '6252': ('Por Ingresos Financieros Prestacion De Servicios De Operaciones De Inversion En Nombre De Terceros', 'Art. 9 LRTI (15.1)'),
    '6262': ('De Ingresos Por Actividades De Inversion, Reinversion O De Negociacion De Activos Financieros (Si La Sociedad Es Administrada Por Una Institucion Financiera)', 'Art. 9 LRTI (15.1)'),
}


def ie_descripcion(casillero: str) -> str | None:
    """Descripción del tipo de ingreso exento / no objeto, o None."""
    info = IE_CASILLERO_INFO.get(str(casillero).strip())
    return info[0] if info else None


def ie_normativa(casillero: str) -> str | None:
    """Normativa de respaldo del ingreso exento, o None."""
    info = IE_CASILLERO_INFO.get(str(casillero).strip())
    return info[1] if info else None
