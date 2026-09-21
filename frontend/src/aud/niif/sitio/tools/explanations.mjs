export function calculationNotes(tool){
 const d=tool.definition,ops={add:'sumar',subtract:'restar',multiply:'multiplicar',divide:'dividir',min:'tomar el menor',max:'tomar el mayor',gt:'1 si A es mayor que B, si no 0',gte:'1 si A es mayor o igual que B, si no 0',lt:'1 si A es menor que B, si no 0',lte:'1 si A es menor o igual que B, si no 0',eq:'1 si A es igual a B, si no 0',if:'si A no es cero toma B, si no C',days:'días desde A hasta B',band:'valor del tramo en que cae A'};
 const formulas=d.rules.map(r=>`${r.label}: ${ops[r.op]} (${[r.a,r.b,r.c].filter(x=>x!==undefined).join(', ')}${r.op==='band'?'; tramos '+r.table.map(b=>`desde ${b.from} = ${b.value}`).join(', '):''}); ${r.precision} decimales.`).join(' ');
 return [
 'La ficha identifica cliente, marco, edición, país, visita, corte, firma y responsables. Los resultados requieren revisión profesional.',
 'Cada procedimiento se vincula con su objetivo, riesgo, evidencia, criterio y fuente verificada. Los textos del programa no son resultados de cálculo.',
 `Los parámetros documentan entradas, constantes, unidades y metodología. ${tool.parameters?.basis||'Sustento pendiente.'}`,
 'La selección normativa requiere verificar documento, edición, vigencia local y párrafo o artículo para el marco elegido. Una URL consultada no equivale a una fuente aprobada.',
 'Se conserva la población mapeada con archivo, hoja y fila de origen. Los datos faltantes no deben sustituirse por cero. Los originales completos se consultan en el sitio hasta encerar.',
 'Las celdas de datos procesados referencian la población original. Los importes no se modifican para forzar una conciliación.',
 formulas+(d.id==='vnr'?' El ajuste resta el deterioro registrado al requerido. Un importe negativo señala un posible reverso que exige verificar su procedencia y límite; no genera automáticamente impuesto diferido.':''),
 'La diferencia es población menos saldo contable. La tolerancia debe estar sustentada; una aceptación documentada no elimina la diferencia.',
 'Las excepciones identifican partidas que requieren evaluación. La ausencia de alertas automáticas no constituye una conclusión de auditoría.',
 'La sumaria suma los resultados por partida desde la cédula de cálculos; no vuelve a aplicar una tasa global a la población.',
 'El auditor documenta su análisis, la evaluación de excepciones y la conclusión. Los textos no se regeneran automáticamente al editar el Excel descargado.',
 'Los puntos de revisión exigen respuesta y resolución antes de aprobar. La descarga conserva una copia; las modificaciones posteriores requieren otra revisión.',
 'El cuadro expande cada contrato en sus períodos: una fila por período y una columna por concepto, en el orden en que la serie los calcula. Los contratos se separan con una fila en blanco y el identificador se repite en cada fila. Los agregados por contrato (primer período, último y suma) se leen en la cédula de cálculos; aquí no se totaliza el detalle.'
 ];
}
