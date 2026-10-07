# Formato de la ficha de una prueba NIIF (bloques A–E)

Plantilla que siguen las fichas CXC-PI-01 (pérdidas incurridas, PYMES) y CXC-PCE-01 (pérdida esperada simplificada,
NIIF 9). Encabezado: código · cuenta · **marco** (uno solo cuando el modelo difiere entre marcos) · origen · estado.

## A · Base técnica
- A.1 Tabla **Párrafo | Qué establece | Cómo lo aplica la herramienta**, leída del texto oficial (M03), y la lista de lo
  que la norma **no permite** y la herramienta respeta.
- A.2 Normas vinculadas (p. ej. NIC 12 / Secc. 29 para diferidos; hechos posteriores).
- A.3 Tabla **NIA | Párrafos | Qué exige en esta prueba** (NIA 540 para estimaciones; 500, 505, 560, 330 según el caso).
- A.4 Tributario Ecuador: norma, qué exige, cómo se aplica; «VERIFICAR» hasta leerla vigente al corte. Porcentajes
  como parámetros editables.

## B · Programa
Tabla `code | objective | risk | assertion | procedure | evidence | criterion | source`, un procedimiento por
aseveración relevante; cada uno con su fuente normativa.

## C · Requerimientos al cliente (M06, M17)
Tabla `id | document | use (calculo/soporte) | formats | components | required`. Para cada anexo de cálculo, sus
columnas: **Columna | clave | tipo | obligatoria | ejemplo | también puede llamarse**. Un anexo = un requerimiento = un
modelo Excel. Lo que se ingresa como parámetro (p. ej. provisión registrada) no se pide como anexo.

## D · Carga de documentos
Criterios de aceptación y de rechazo (agrupado sin detalle, sin fechas, filas de total, corte distinto) y lo que debe
coincidir entre anexos (p. ej. el mismo N° de factura en todos los años).

## E · Procesamiento
- E.1 Parámetros con valor por defecto y sustento.
- E.2 Qué se calcula, en orden y en lenguaje contable.
- E.3 Resultado principal (neto de lo contabilizado, M09) y **problemas** que debe mostrar, derivados de cada «debe»
  de la norma (M22).
- E.4 Cédulas.
- E.5 Dónde vive el cálculo (M18).
- E.6 **Ejemplo numérico de control** resuelto a mano (M19).
- Verificación: fecha, pruebas, fórmulas comparadas en Excel real y cifras recalculadas a mano.
