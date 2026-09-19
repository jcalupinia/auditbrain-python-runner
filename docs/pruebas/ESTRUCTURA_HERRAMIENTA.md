# Estructura común de una herramienta de auditoría

Versión 0.2 · 2026-09-19

Formulario de referencia para fabricar cualquier prueba de auditoría externa.
Lo **fijo** es esta estructura; lo **variable** por rubro es solo qué se le pide
al cliente y qué salidas produce.

Construido comparando las tres herramientas que ya existen:

| Fuente | Dónde vive |
|---|---|
| **Inventarios / VNR** | `auditbrain-site`, recorrido `app/herramientas/recorrido/` |
| **Obligaciones Fiscales** | `auditbrain-python-runner`, `frontend/src/aud/of/` |
| **ICT** | `auditbrain-python-runner`, `frontend-client/src/ict/` |

Leyenda: ✅ existe hoy · ❌ no existe · ⚠️ existe con limitación · **R** requisito de la estructura

---

## Bloque 0 · Dónde se diseña y dónde vive

| Etapa | Dónde | Qué hace |
|---|---|---|
| **Diseño** | AuditBrain Sites / Command Center | Se define la prueba: qué se pide al cliente, qué salidas, qué cálculos. Se prueba con muestras. **No es producción.** |
| **Código** | GitHub | Motor determinista, esquemas, lectores, exportadores y pruebas |
| **Ejecución** | **Catálogo del rubro** en AUDIT-IA | La herramienta terminada vive en su ciclo: Caja y bancos, CxC, Inventarios, Activos fijos, Nómina… Ahí la corre el auditor con datos del cliente |

Consecuencia práctica: **los límites de volumen del sitio son de diseño**, no de
producción. El volumen real lo absorbe el motor del portal. Un techo bajo en el
sitio solo limita la muestra con la que se prueba el diseño.

---

## Bloque 1 · Ficha del encargo

Se pide **una vez** y la heredan todas las pruebas del mismo encargo y visita.

| Campo | Inventarios | Oblig. Fiscales | ICT | Estructura |
|---|:---:|:---:|:---:|:---:|
| Cliente / razón social | ✅ | ✅ | ✅ | **R** |
| RUC / identificación fiscal | ✅ | ❌ | ✅ | **R** |
| Actividad económica | ✅ | ❌ | ❌ | **R** |
| Ejercicio económico | ✅ | ✅ | ✅ | **R** |
| Fecha de corte | ✅ | ✅ | ❌ | **R** |
| Visita: preliminar o final | ✅ | ❌ | ❌ | **R** |
| Preparado por | ✅ | ⚠️ opcional | ❌ | **R** |
| Revisado por | ✅ | ⚠️ opcional | ❌ | **R** |
| Firma auditora: Auditconsulting / Partner Auditing | ✅ | ✅ | ❌ | **R** |
| Marco contable: NIIF completas / NIIF PYMES | ✅ | ❌ | ❌ | **R** |
| Edición y vigencia del marco | ✅ | ❌ | ❌ | **R** |
| Adopción local por verificar | ✅ | ❌ | ❌ | **R** |
| País | ✅ | ❌ | ❌ | **R** |
| Moneda | ✅ | ❌ | ❌ | **R** |
| Alcance de reutilización: una / varias / todas | ✅ | ❌ | ❌ | **R** |
| **Aplica impuestos diferidos** (casilla) | ❌ | ❌ | ❌ | **R** |

**Brechas confirmadas.** Obligaciones Fiscales no pide RUC, visita ni marco
contable — este último es la primera pregunta obligatoria de la memoria (M02).
El ICT no pide fecha de corte, responsables ni firma.

**Impuestos diferidos.** Casilla presente en **todas** las pruebas. Si se marca,
la prueba habilita sus cédulas de diferido; si no, quedan ocultas. Para Ecuador
el caso del deterioro a valor neto de realización de inventarios está en la lista
cerrada del Reglamento (ver `FICHA_VNR_INVENTARIOS.md`, §2.4).

---

## Bloque 2 · Requerimiento al cliente

Documentos definidos **por contenido**, no por extensión. Cada uno declara
obligatoriedad, formatos aceptados y plantilla descargable.

### 2.1 Formatos que debe aceptar

| Formato | Inventarios | Oblig. Fiscales | ICT | Estructura |
|---|:---:|:---:|:---:|:---:|
| Excel (.xlsx / .xls) | ✅ | ✅ | ✅ | **R** |
| CSV | ✅ | ✅ | — | **R** |
| XML | ⚠️ lector en Consola, no en la prueba | ⚠️ aceptado **sin lector** | — | **R** |
| Word (.docx), lectura de tablas | ✅ | ❌ | — | **R** |
| PDF | ✅ | ✅ | ✅ | **R** |
| Imágenes de soporte (png / jpg) | ✅ | ❌ | — | **R** |
| ZIP | ⚠️ lector en Consola, no en la prueba | ❌ | ❌ | **R** |
| TXT | ✅ | ❌ | — | **R** |

⚠️ **Defecto abierto.** `obligaciones_fiscales/router.py:48` acepta
`application/xml` para el ATS, pero `libro/ats.py` no tiene lector XML — solo
procesa texto. El ATS del SRI es XML nativo: el archivo entra y no se extrae nada.

**Los lectores ya existen en el sitio, pero no en la prueba.** `auditbrain-site/lib/console/extract.mjs`
(la Consola de archivos) procesa **csv, docx con tablas, pdf, png, webp, txt, xlsx, xml y zip**
con descompresión recursiva. Límite: 10 MB por archivo, 240.000 caracteres de texto.
El lector de fuentes de la prueba (`lib/tools/files.mjs`) solo hace **csv y xlsx**.
La tarea no es construir lectores: es **conectar el extractor de la Consola al
requerimiento de la prueba**.

### 2.2 Capacidad

| Límite | Antes | Ahora | Dónde |
|---|---|---|---|
| **Filas que procesa el motor** | 10.000 | **100.000** | `auditbrain-site/lib/tools/domain.mjs` y `portable-engine.mjs` |
| Tamaño por archivo | 5 MB | 5 MB | `auditbrain-site` |
| Archivos por encargo | 20 | 20 | `auditbrain-site` |
| Total por encargo | 20 MB | 20 MB | `auditbrain-site` |
| Tamaño por archivo (portal) | 20 MB | 20 MB | `AUD_OF_MAX_FILE_MB` |
| Columnas por hoja | 150 | 150 | `files.mjs` |

Medición del motor tras el cambio, con la definición VNR real:

| Filas | Tiempo | Resultado |
|---|---|---|
| 10.000 | 0,57 s | correcto |
| 50.000 | 2,39 s | correcto |
| 100.000 | 4,08 s | correcto |
| 100.001 | rechazado con mensaje claro | correcto |

El tiempo escala de forma lineal. **R** — los límites de archivo (5 MB / 20 MB)
siguen siendo bajos para una empresa grande y deben subirse; falta definir el
volumen objetivo en MB.

### 2.3 Por cada documento solicitado

| Atributo | Inventarios | Oblig. Fiscales | ICT | Estructura |
|---|:---:|:---:|:---:|:---:|
| Nombre por contenido | ✅ | ✅ | ✅ | **R** |
| Obligatorio / opcional | ❌ | ✅ | — | **R** |
| Fuentes alternativas | ❌ | ❌ | ❌ | **R** |
| Plantilla descargable con instrucciones | ❌ | ❌ | ✅ | **R** |
| Estado: recibido / extraído / validado / rechazado | ⚠️ parcial | ⚠️ parcial | ⚠️ parcial | **R** |
| Quitar archivo | ❌ | ✅ | — | **R** |
| Categoría o mapeo de columnas | ❌ | ✅ | ❌ | condicional |

---

## Bloque 3 · Acciones

| Acción | Inventarios | Oblig. Fiscales | ICT | Estructura |
|---|:---:|:---:|:---:|:---:|
| Editar datos | ✅ | ✅ | ✅ | **R** |
| Subir documentos | ✅ | ✅ | ✅ | **R** |
| Procesar | ✅ | ✅ | ✅ | **R** |
| Descargar Excel | ✅ | ✅ | ✅ | **R** |
| **Descargar HTML** | ✅ | ❌ | ❌ | **R** |
| Encerar / Nuevo proyecto | ✅ | ✅ | ✅ | **R** |
| Descargar plantilla del cliente | ❌ | ❌ | ✅ | **R** |
| Guardar correcciones | ❌ | ✅ | ❌ | condicional |
| Aprobar y generar | ❌ | ✅ | ❌ | condicional |
| Confirmar ficha | ⚠️ demo | ❌ | ❌ | ✖ se elimina |

**HTML en todas las pruebas.** Varios clientes lo prefieren al Excel. Requisito
duro: **debe abrirse y funcionar sin conexión a internet**, sin depender de
recursos remotos ni de servicios privados (Manual §12). Hoy solo el sitio genera
HTML; se verificó que `lib/tools/html-presentation.mjs` **no contiene ninguna URL
externa**, así que la salida ya es autónoma. Falta llevar el HTML al portal.

**Condicionales.** «Guardar correcciones» y «Aprobar y generar» aparecen solo si
la prueba tiene un paso de clasificación o mapeo: Obligaciones Fiscales sí,
inventarios no, activos fijos probablemente sí.

---

## Bloque 4 · Salidas

**Las cédulas son todas variables.** La estructura no impone ninguna — ni las 12
del sitio, ni las 6 de Obligaciones Fiscales, ni los 10 anexos del ICT. Cada
prueba declara las suyas (Manual §11).

| Regla | Estructura |
|---|:---:|
| Cada salida es una tarjeta con estado propio | **R** |
| Cada tarjeta declara entradas, salidas y dependencias | **R** |
| Toda hoja entregada en el Excel tiene su tarjeta | **R** |
| Número fijo de cédulas | ✖ |

Lo que produce cada herramienta hoy, como referencia:

- Inventarios: 12 cédulas
- Obligaciones Fiscales: 6 tarjetas DM3–DM7 más Clasificación — **DM8 ATS se genera sin tarjeta**
- ICT: 10 anexos (ÍNDICE + A1 a A9)

---

## Bloque 5 · Lo que se elimina

| Se quita | Motivo |
|---|---|
| Población sintética y parámetros de cálculo en pantalla | Ya queda definido en la ficha de cada prueba |
| Confirmar ficha del ejemplo | Pertenece al recorrido de demostración |
| Número fijo de cédulas | Manual §11 |

---

## Bloque 6 · Lo único que se define al crear una prueba nueva

1. **Qué documentos se piden**: contenido, obligatoriedad, formatos, plantilla
2. **Qué salidas produce**: cédulas, cálculos y dependencias
3. **Si aplica impuestos diferidos**

Todo lo demás lo aporta la estructura. Al terminar, la herramienta se registra en
el **catálogo de su rubro** (`frontend/src/aud/catalog.js`), que es donde vive y
se ejecuta.

---

## Bloque 7 · Estado de implementación

Todo lo siguiente es **requisito de la estructura** y hoy no está resuelto:

| Requisito | Estado |
|---|---|
| Lector XML en el portal: el ATS se acepta pero no se procesa | defecto abierto |
| Conectar el extractor de la Consola (zip, docx, pdf, xml, imágenes) al lector de fuentes de la prueba | el extractor ya existe; falta el cableado |
| Lectura de tablas de Word | ya resuelta en `console/extract.mjs` |
| Imágenes de soporte (png, jpg, webp) | ya resuelta en `console/extract.mjs` |
| Plantilla descargable por documento | solo en el ICT |
| Casilla de impuestos diferidos | en ninguna |
| HTML autónomo sin internet | **verificado**: `html-presentation.mjs` no tiene ninguna URL externa |
| Límite de archivo para empresa grande | 5 MB en el sitio, 20 MB en el portal |
| Ficha completa en el portal | OF no pide RUC, visita ni marco contable |
| Estados de documento completos | parciales en las tres |
| Fuentes alternativas por requerimiento | en ninguna |

**Resuelto en esta versión:** capacidad del motor subida de 10.000 a 100.000
filas, verificada con la definición VNR real.

---

## Pendiente de decidir

- ☐ Volumen objetivo en MB por archivo y por encargo
- ☐ Si «Encerar» entra en la primera versión o solo queda declarado
