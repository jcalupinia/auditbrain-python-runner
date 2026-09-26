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
  pce_simplificada_niif9: {
    "RQ-001": "RQ-001_actual.xlsx",
    "RQ-002": "RQ-002_anterior.xlsx",
    "RQ-003": "RQ-003_castigos.xlsx",
    "RQ-004": "RQ-004_informacion_prospectiva_usada_para_el_ajuste_pro.pdf",
    "RQ-005": "RQ-005_politica_de_credito_y_cobranza_y_gestion_de_clie.pdf",
    "RQ-006": "RQ-006_cobros_posteriores_al_cierre.xlsx",
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
  // --- Lote 2 --- (mismos dos generadores; datos + evidencia de soporte)
  arrendamientos: {
    "RQ-001": "RQ-001_contratos.xlsx",
    "RQ-002": "RQ-002_contratos_de_arrendamiento_firmados_y_adendas.pdf",
    "RQ-003": "RQ-003_sustento_de_la_tasa_implicita_o_incremental.pdf",
    "RQ-004": "RQ-004_mayor_y_auxiliares_del_pasivo_derecho_de_uso_dep.xlsx",
    "RQ-005": "RQ-005_evaluacion_de_deterioro_y_tasaciones_del_activo.pdf",
    "RQ-006": "RQ-006_contrato_de_compraventa_de_la_venta_con_arrendam.pdf",
    "RQ-007": "RQ-007_facturas_o_liquidaciones_de_renta_del_ejercicio_.pdf",
    "RQ-008": "RQ-008_mayor_y_asientos_posteriores_a_la_venta_con_arre.xlsx",
  },
  intangibles_goodwill: {
    "RQ-001": "RQ-001_intangibles.xlsx",
    "RQ-002": "RQ-002_memorias_de_proyectos_de_desarrollo_y_evidencia_.pdf",
    "RQ-003": "RQ-003_pruebas_de_deterioro_valor_en_uso_vr_menos_costo.xlsx",
    "RQ-004": "RQ-004_asignacion_del_precio_de_compra_de_las_combinaci.pdf",
    "RQ-005": "RQ-005_contratos_de_licencias_registros_de_marcas_y_pat.pdf",
    "RQ-006": "RQ-006_analisis_de_la_vida_util_y_del_valor_residual_re.pdf",
    "RQ-007": "RQ-007_papel_de_calculo_de_la_amortizacion_y_si_el_meto.pdf",
  },
  activos_biologicos: {
    "RQ-001": "RQ-001_activos.xlsx",
    "RQ-002": "RQ-002_cosecha.xlsx",
    "RQ-003": "RQ-003_precios_de_mercado_o_informe_del_perito_valuador.pdf",
    "RQ-004": "RQ-004_detalle_de_costos_de_venta_fletes_comisiones_tas.xlsx",
    "RQ-005": "RQ-005_actas_de_conteo_y_registros_de_campo_nacimientos.pdf",
    "RQ-006": "RQ-006_analisis_de_plantas_productoras_y_de_la_fiabilid.pdf",
    "RQ-007": "RQ-007_mayor_de_activos_biologicos_y_de_resultados_por_.xlsx",
  },
  seguros_cobertura: {
    "RQ-001": "RQ-001_activos.xlsx",
    "RQ-002": "RQ-002_polizas.xlsx",
    "RQ-003": "RQ-003_polizas_y_endosos_condiciones_particulares_deduc.pdf",
    "RQ-004": "RQ-004_tasaciones_o_valores_de_reposicion.pdf",
    "RQ-005": "RQ-005_reclamos_de_siniestros_y_comunicaciones_de_la_as.pdf",
    "RQ-006": "RQ-006_mayor_de_seguros_pagados_por_anticipado_y_factur.xlsx",
  },
  proveedores_cxp: {
    "RQ-001": "RQ-001_proveedores.xlsx",
    "RQ-002": "RQ-002_pagos_posteriores.xlsx",
    "RQ-003": "RQ-003_mayor_balance_de_comprobacion_de_proveedores_e_i.xlsx",
    "RQ-004": "RQ-004_respuestas_de_confirmacion_de_proveedores.pdf",
    "RQ-005": "RQ-005_comprobantes_de_egreso_y_estados_de_cuenta_poste.pdf",
    "RQ-006": "RQ-006_ingresos_a_bodega_o_actas_de_recepcion_alrededor.pdf",
    "RQ-007": "RQ-007_contratos_terminos_de_pago_y_sustento_de_la_tasa.pdf",
  },
  prestamos_obligaciones: {
    "RQ-001": "RQ-001_prestamos.xlsx",
    "RQ-002": "RQ-002_flujos.xlsx",
    "RQ-003": "RQ-003_contratos_de_prestamo_tablas_de_amortizacion_del.pdf",
    "RQ-004": "RQ-004_confirmaciones_bancarias.pdf",
    "RQ-005": "RQ-005_liquidaciones_de_desembolso_con_comisiones_y_cos.pdf",
    "RQ-006": "RQ-006_clausula_del_contrato_que_define_el_dscr_y_demas.pdf",
    "RQ-007": "RQ-007_estados_financieros_al_corte_activos_patrimonio_.pdf",
    "RQ-008": "RQ-008_mayor_y_auxiliares_de_prestamos_intereses_por_pa.xlsx",
    "RQ-009": "RQ-009_garantias_y_refinanciaciones_del_ejercicio.pdf",
  },
  // --- Lote 3 --- (mismos dos generadores; datos + evidencia de soporte)
  nomina_beneficios: {
    "RQ-001": "RQ-001_empleados.xlsx",
    "RQ-002": "RQ-002_actuarial.xlsx",
    "RQ-003": "RQ-003_roles_de_pago_mensuales_y_contratos_de_trabajo.xlsx",
    "RQ-004": "RQ-004_planillas_y_comprobantes_de_pago_del_iess_aporte.pdf",
    "RQ-005": "RQ-005_informe_actuarial_completo_y_censo_enviado_al_ac.pdf",
    "RQ-006": "RQ-006_mayores_de_gasto_de_nomina_y_de_pasivos_laborale.xlsx",
    "RQ-007": "RQ-007_registro_de_vacaciones_y_comprobantes_de_pago_de.xlsx",
  },
  ingresos_contratos: {
    "RQ-001": "RQ-001_contratos.xlsx",
    "RQ-002": "RQ-002_mayor_de_ingresos_activo_y_pasivo_del_contrato.xlsx",
    "RQ-003": "RQ-003_contratos_ordenes_de_compra_y_adendas.pdf",
    "RQ-004": "RQ-004_guias_de_remision_y_actas_de_entrega_alrededor_d.pdf",
    "RQ-005": "RQ-005_presupuestos_y_costos_incurridos_de_contratos_a_.xlsx",
    "RQ-006": "RQ-006_notas_de_credito_emitidas_despues_del_cierre_y_e.xlsx",
    "RQ-007": "RQ-007_listas_de_precios_o_cotizaciones_precio_de_venta.pdf",
    "RQ-008": "RQ-008_sustento_de_la_tasa_de_descuento_de_ventas_a_pla.pdf",
  },
  gastos_analisis: {
    "RQ-001": "RQ-001_cuentas.xlsx",
    "RQ-002": "RQ-002_transacciones.xlsx",
    "RQ-003": "RQ-003_mayor_de_gastos_y_balance_de_comprobacion_al_cor.xlsx",
    "RQ-004": "RQ-004_facturas_contratos_aprobaciones_y_comprobantes_d.pdf",
    "RQ-005": "RQ-005_facturas_y_pagos_posteriores_al_cierre.pdf",
    "RQ-006": "RQ-006_maestro_completo_de_partes_relacionadas_al_corte.xlsx",
    "RQ-007": "RQ-007_presupuesto_aprobado_del_ejercicio.xlsx",
    "RQ-008": "RQ-008_manifestacion_escrita_de_la_administracion_sobre.pdf",
  },
  provisiones_contingencias: {
    "RQ-001": "RQ-001_provisiones.xlsx",
    "RQ-002": "RQ-002_garantias.xlsx",
    "RQ-003": "RQ-003_respuestas_de_los_abogados_a_la_carta_de_confirm.pdf",
    "RQ-004": "RQ-004_contratos_onerosos_y_estudio_tecnico_de_desmante.pdf",
    "RQ-005": "RQ-005_sentencias_o_acuerdos_posteriores_al_corte.pdf",
    "RQ-006": "RQ-006_mayor_de_provisiones_y_de_gastos_financieros.xlsx",
    "RQ-007": "RQ-007_carta_de_manifestaciones_de_la_gerencia_litigios.pdf",
  },
  impuesto_corriente_diferido: {
    "RQ-001": "RQ-001_conciliacion.xlsx",
    "RQ-002": "RQ-002_partidas.xlsx",
    "RQ-003": "RQ-003_perdidas.xlsx",
    "RQ-004": "RQ-004_formulario_101_presentado_y_declaraciones_de_ano.pdf",
    "RQ-005": "RQ-005_comprobantes_de_retencion_anticipos_y_credito_tr.pdf",
    "RQ-006": "RQ-006_proyecciones_de_ganancias_fiscales_y_analisis_de.xlsx",
    "RQ-007": "RQ-007_mayor_de_cuentas_de_impuesto_corriente_diferido_.xlsx",
    "RQ-008": "RQ-008_detalle_del_ingreso_exento_bruto_del_ejercicio_a.xlsx",
  },
  patrimonio: {
    "RQ-001": "RQ-001_movimientos.xlsx",
    "RQ-002": "RQ-002_transacciones.xlsx",
    "RQ-003": "RQ-003_libro_de_actas_de_junta_general_del_periodo_y_po.pdf",
    "RQ-004": "RQ-004_escrituras_de_constitucion_y_aumentos_de_capital.pdf",
    "RQ-005": "RQ-005_contratos_o_estatutos_de_acciones_preferentes_ap.pdf",
    "RQ-006": "RQ-006_estado_de_cambios_en_el_patrimonio_y_nota_de_pat.xlsx",
    "RQ-007": "RQ-007_conciliacion_de_la_adopcion_por_primera_vez_de_l.xlsx",
  },
  // --- Planificación de la auditoría (NIA 300, 315, 320) ---
  planificacion_nia: {
    "RQ-001": "RQ-001_balance_anterior.xlsx",
    "RQ-002": "RQ-002_balance_actual.xlsx",
    "RQ-003": "RQ-003_resultados_mismo_corte.xlsx",
    "RQ-004": "RQ-004_carta_control_interno.xlsx",
    "RQ-005": "RQ-005_informe_anterior.xlsx",
    "RQ-006": "RQ-006_notas_estados_financieros.xlsx",
    "RQ-009": "RQ-009_notas_detalle.xlsx",
    "RQ-010": "RQ-010_cuestionario_planificacion.xlsx",
    "RQ-011": "RQ-011_equipo_encargo.xlsx",
    "RQ-012": "RQ-012_diferencias_auditoria.xlsx",
    "RQ-013": "RQ-013_componentes_grupo.xlsx",
    "RQ-007": "RQ-007_informe_de_auditoria_notas_y_carta_de_control_in.pdf",
    "RQ-008": "RQ-008_ruc_actualizado_de_la_entidad.pdf",
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
