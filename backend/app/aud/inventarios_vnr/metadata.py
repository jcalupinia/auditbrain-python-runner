"""Referencias para revisión expresa; no certifican adopción local automática."""
SHEETS=['00 Portada','01 Criterio','02 Fuentes','03 Inventario','04 Precios','05 Gastos','06 VNR','07 Conciliacion','08 Ajustes','09 Diferido','10 Conclusion','11 Revision']
TITLES=['Portada del encargo','Normativa y política','Evidencia y trazabilidad','Inventario valorado','Precios de venta','Costos necesarios','Cálculo VNR','Conciliación contable','Ajustes y reversiones','Impuesto diferido','Conclusión del auditor','Control de revisión']
REFERENCES=[
 {'framework':'full','title':'NIC 2: 6, 9, 28–34 · medición y reversión','url':'https://www.ifrs.org/content/dam/ifrs/publications/html-standards/english/2024/issued/ias2.html'},
 {'framework':'full','title':'NIC 12 · diferencias temporarias y reconocimiento','url':'https://www.ifrs.org/issued-standards/list-of-standards/ias-12-income-taxes/'},
 {'framework':'sme','title':'NIIF para las PYMES · secciones 13, 27 y 29; verificar edición y adopción','url':'https://www.ifrs.org/issued-standards/ifrs-for-smes/'},
 {'framework':'sme','title':'Edición 2025: vigencia IASB desde 2027; aplicación anticipada permitida, sujeta a adopción local','url':'https://www.ifrs.org/content/dam/ifrs/shop/more-details/ifrs-smes-2025-more-details.pdf'},
 {'framework':'all','title':'NIA 540 (Revisada), 500, 230, 315 y 330: estimaciones, evidencia, documentación y riesgos; aplicar procedimientos pertinentes','url':'https://www.iaasb.org/iaasb/focus-areas/auditing-accounting-estimates'},
 {'framework':'Ecuador','title':'SRI: consultar normativa vigente al período para base fiscal y diferidos, sin tasa por defecto','url':'https://www.sri.gob.ec/normativa-tributaria-legislacion-nacional'}]
NOTES=[
 'Ficha declarada por el auditor; todos los importes se expresan en la moneda del encargo.',
 'Seleccionar marco y edición, verificar vigencia local, alcance y política antes de concluir. No se ejecuta una consulta normativa automática.',
 'Identificar documentos, huellas SHA256 y referencias de hoja/fila; la carga no equivale a evidencia suficiente.',
 'Costo total = cantidad × costo unitario. El deterioro registrado corresponde a los ítems que permanecen al corte.',
 'Precio estimado por ítem al corte; evaluar descuentos, contratos y ventas posteriores que confirmen condiciones existentes.',
 'Método unitario o precio × (gastos necesarios / ventas de población comparable). No incluir indiscriminadamente todos los gastos del estado de resultados.',
 'VNR unitario = MAX(0, precio − terminación − venta). Deterioro = MAX(0, costo total − VNR total). Piso cero para el inventario; costos que lo exceden requieren evaluación separada.',
 'Comparar costo bruto y deterioro de la población contra sus saldos del mayor. Mostrar diferencias sin forzar cuadre.',
 'Ajuste = deterioro requerido − registrado. Positivo: gasto adicional. Negativo: reversión limitada al deterioro registrado, con sustento de recuperación.',
 'Comparar base fiscal con valor contable ajustado. Activo solo con recuperabilidad sustentada; pasivo sobre diferencia imponible. Mostrar ajuste frente al diferido ya registrado, sin compensarlos automáticamente.',
 'Conclusión pendiente de juicio profesional, evidencia suficiente y revisión. Los cálculos no son un dictamen.',
 'Preparado por y revisado por identifican responsables declarados; no equivalen a firma electrónica ni aprobación automática.']
