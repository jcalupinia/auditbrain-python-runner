# VNR: fábrica AuditBrain → artefactos → Command Center

Implementación autorizada en conversación: rama por herramienta y ubicación AUD → Análisis → Inventarios → Valor neto de realización. Mantener temas, autenticación y herramientas existentes.

## Contrato
Motor determinista Python, importable sin servidor. Inventario ordinario medido al menor entre costo y VNR; selección expresa NIIF completas o PYMES, edición, adopción local, país, moneda, corte, visita, cliente, preparado/revisado y firma. Cada ítem tiene cantidad, costo, precio, costos de terminación/venta, deterioro previo y referencia. Se rechazan duplicados, datos faltantes, negativos no admitidos y falta de precios. El deterioro nunca supera el costo; la reversión no supera el deterioro previo.

Gastos de venta: valor por unidad o porcentaje sustentado (gastos necesarios/ventas de población comparable), nunca todos los gastos indiscriminadamente. El auditor valida política, norma, evidencia y asignación. Impuesto diferido opcional: base fiscal por ítem, tasa documentada, recuperabilidad explícita y saldos registrados, sin tasas tributarias implícitas. Diferenciar activo/pasivo y ajustes de saldos existentes.

## Evidencia y autorización
API sin persistencia de documentos ni resultados. Cada petición exige JWT y autorización al proyecto activo; roles cliente no usan esta herramienta interna. Archivos se leen acotados en memoria: XLSX/CSV/XML para tablas; PDF/DOCX/TXT e imágenes como soporte, con revisión/manual cuando no hay extracción tabular segura; ZIP con límites, sin extracción al disco. Nunca afirmar OCR o revisión normativa automática. Datos y resultados permanecen solo en la pestaña. Encerar los elimina conservando opcionalmente ficha. Ficha reutilizable solo durante la sesión, con selección una/varias/todas; debe mostrar su alcance, sin alterar otros módulos.

## Entrega
Excel con doce hojas enlazadas, fórmulas visibles y resultados cacheados; HTML autónomo de consulta con doce cédulas y fórmulas documentadas. Firmas AuditConsulting/Partner, estilos acordes al workspace. Resultados son propuestas sujetas a revisión; nunca emitir dictamen automático. Descargar antes de encerar.

## Integración y distribución
Código canónico y manifiesto de versiones en audit-ia-artefactos, rama herramientas/inventarios-vnr. Copia verificable por SHA256 en runner, sin dependencia de red en ejecución. Añadir router /aud/inventarios-vnr y componente VnrTool al catálogo. No cambiar infraestructura, secretos, roles ni base de datos. Publicar solo después de pruebas y revisión; comprobar el estado de Render si accesible, informar límites de verificación.

## Validación
Cálculos independientes, reversión, diferidos, precisión decimal, entradas inválidas, archivos grandes/ZIP peligrosos, fórmulas y escape de texto, aislamiento por proyecto, exportación con el mismo resultado. Prueba sintética identificada; no afirmar validación con datos reales del cliente.
