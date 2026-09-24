/*
 * Ejemplos «formato válido con datos ficticios» por procesador y requerimiento.
 *
 * Los archivos son estáticos y viven en
 *   frontend/public/ejemplos/<processor>/<archivo>
 * (se generan con scripts/ejemplos_<procesador>.py). El manifiesto solo mapea
 * processor → { requerimiento: nombre de archivo }.
 *
 * Cuando una herramienta no tenga ejemplos propios aquí, la flecha de la vista
 * usa el modelo en blanco del propio requerimiento (bajarModelo) si alimenta el
 * cálculo (req.dataset); si no, no se muestra flecha y solo quedan los formatos.
 */
export const EJEMPLOS_REQUERIMIENTOS = {
  perdidas_incurridas_s11: {
    "RQ-001": "RQ-001_cartera_2025.xlsx",
    "RQ-002": "RQ-002_cartera_2024.xlsx",
    "RQ-003": "RQ-003_cartera_2023.xlsx",
    "RQ-004": "RQ-004_provision_inicial_2025.xlsx",
    "RQ-005": "RQ-005_movimiento_provision_3_ejercicios.xlsx",
    "RQ-006": "RQ-006_cobros_posteriores_al_cierre.xlsx",
    "RQ-007": "RQ-007_politica_credito_cobranza.docx",
    "RQ-008": "RQ-008_ventas_por_factura_3_ejercicios.xlsx",
  },
  // --- Lote 1 ---
  // Datos que alimentan el cálculo: un libro derivado del EJEMPLO canónico del
  // procesador (scripts/ejemplos_lote.py). Requerimientos de soporte: documento
  // de evidencia de muestra en el primer formato aceptado, PDF narrativo o XLSX
  // tabular (scripts/ejemplos_soporte.py). Todos con datos ficticios.
  efectivo_equivalentes: {
    "RQ-001": "RQ-001_cuentas.xlsx",
    "RQ-002": "RQ-002_partidas.xlsx",
    "RQ-003": "RQ-003_conciliaciones_y_estados_bancarios_del_mes_de_co.pdf",
    "RQ-004": "RQ-004_estados_bancarios_posteriores_al_corte_ventana_d.pdf",
    "RQ-005": "RQ-005_respuestas_de_confirmacion_bancaria_recibidas_po.pdf",
    "RQ-006": "RQ-006_contratos_de_garantia_pignoracion_embargos_o_fid.pdf",
    "RQ-007": "RQ-007_certificados_y_contratos_de_inversiones_presenta.pdf",
    "RQ-008": "RQ-008_politica_contable_de_efectivo_y_equivalentes_y_a.pdf",
  },
  cxc_cartera: {
    "RQ-001": "RQ-001_cartera.xlsx",
    "RQ-002": "RQ-002_mayor_de_cuentas_por_cobrar_deterioro_y_descuent.xlsx",
    "RQ-003": "RQ-003_respuestas_de_confirmacion_de_clientes.pdf",
    "RQ-004": "RQ-004_estados_de_cuenta_y_recibos_de_cobros_posteriore.pdf",
    "RQ-005": "RQ-005_guias_de_remision_de_las_ventas_alrededor_del_ci.pdf",
    "RQ-006": "RQ-006_contratos_o_pagares_de_ventas_a_plazo_y_sustento.pdf",
    "RQ-007": "RQ-007_politica_de_credito_y_sustento_de_las_tasas_de_d.pdf",
  },
  inversiones_instrumentos: {
    "RQ-001": "RQ-001_inversiones.xlsx",
    "RQ-002": "RQ-002_estados_de_cuenta_y_confirmaciones_de_custodios_.pdf",
    "RQ-003": "RQ-003_politica_de_inversiones_y_documentacion_del_mode.pdf",
    "RQ-004": "RQ-004_prospectos_o_contratos_de_los_titulos_flujos_con.pdf",
    "RQ-005": "RQ-005_precios_de_cierre_vector_de_precios_o_valuacione.pdf",
    "RQ-006": "RQ-006_actas_o_avisos_de_dividendos_decretados.pdf",
    "RQ-007": "RQ-007_calificaciones_de_riesgo_e_informacion_de_los_em.pdf",
  },
  inventarios_costos: {
    "RQ-001": "RQ-001_inventario.xlsx",
    "RQ-002": "RQ-002_produccion.xlsx",
    "RQ-003": "RQ-003_movimiento.xlsx",
    "RQ-004": "RQ-004_corte.xlsx",
    "RQ-005": "RQ-005_actas_e_instrucciones_del_recuento_fisico.pdf",
    "RQ-006": "RQ-006_ventas_y_precios_posteriores_al_cierre_costos_de.xlsx",
    "RQ-007": "RQ-007_sustento_de_la_capacidad_normal_de_planta.pdf",
    "RQ-008": "RQ-008_politica_de_obsolescencia_y_lenta_rotacion.pdf",
    "RQ-009": "RQ-009_inventario_de_terceros_o_en_consignacion.xlsx",
    "RQ-010": "RQ-010_costeo_estandar_y_lista_de_precios_de_los_produc.xlsx",
  },
  ppe_propiedad_planta: {
    "RQ-001": "RQ-001_activos.xlsx",
    "RQ-002": "RQ-002_adiciones.xlsx",
    "RQ-003": "RQ-003_prestamos.xlsx",
    "RQ-004": "RQ-004_politica_contable_de_vidas_utiles_residuales_y_m.pdf",
    "RQ-005": "RQ-005_informe_del_perito_de_la_revaluacion.pdf",
    "RQ-006": "RQ-006_calculo_del_importe_recuperable_valor_en_uso_o_v.xlsx",
    "RQ-007": "RQ-007_contratos_de_prestamo_tablas_de_amortizacion_y_m.pdf",
    "RQ-008": "RQ-008_estimacion_tecnica_de_desmantelamiento_o_restaur.pdf",
    "RQ-009": "RQ-009_facturas_de_venta_y_actas_de_baja_del_ano.pdf",
  },
  propiedades_inversion: {
    "RQ-001": "RQ-001_inmuebles.xlsx",
    "RQ-002": "RQ-002_bajas.xlsx",
    "RQ-003": "RQ-003_informes_de_tasacion_al_corte.pdf",
    "RQ-004": "RQ-004_contratos_de_arrendamiento_vigentes.pdf",
    "RQ-005": "RQ-005_escrituras_y_certificados_del_registro_de_la_pro.pdf",
    "RQ-006": "RQ-006_evidencia_de_cambios_de_uso_actas_contratos_ocup.pdf",
    "RQ-007": "RQ-007_gastos_directos_de_operacion_por_inmueble.xlsx",
    "RQ-008": "RQ-008_base_fiscal_de_los_inmuebles.xlsx",
    "RQ-009": "RQ-009_auxiliar_del_superavit_de_revaluacion_por_inmueb.xlsx",
  },
};

/**
 * Qué ofrece la flecha «↓ Ejemplo» para un requerimiento:
 *   { tipo: "ejemplo", archivo, url } → hay un ejemplo lleno en el manifiesto (descarga estática)
 *   { tipo: "modelo" }                → no hay ejemplo, pero el requerimiento alimenta el cálculo
 *                                        (req.dataset) → se baja el modelo en blanco con bajarModelo
 *   null                              → no hay ninguno; la vista solo muestra los formatos aceptados
 *
 * `base` es el prefijo público (import.meta.env.BASE_URL) para armar la URL estática.
 */
export function ejemploDe(processor, req, manifest = EJEMPLOS_REQUERIMIENTOS, base = "") {
  if (!req) return null;
  const archivo = processor && manifest[processor] && manifest[processor][req.id];
  if (archivo) return { tipo: "ejemplo", archivo, url: `${base}ejemplos/${processor}/${archivo}` };
  if (req.dataset) return { tipo: "modelo" };
  return null;
}

/** Formatos aceptados en mayúsculas para la vista, p. ej. «XLSX · CSV». */
export function formatosTexto(req) {
  return (req?.formats || []).map((f) => String(f).toUpperCase()).join(" · ");
}
