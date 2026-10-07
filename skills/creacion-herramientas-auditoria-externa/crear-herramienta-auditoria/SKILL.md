---
name: crear-herramienta-auditoria
description: >
  Esta skill se usa cuando el socio pide crear o construir una herramienta o prueba nueva de auditoría externa de punta a
  punta: "crea una herramienta de…", "construye la prueba de…", "quiero una herramienta para cuentas por cobrar /
  inventarios / activos fijos…", "convierte este HTML/Excel en herramienta del Command Center", "pasa esta prueba al
  catálogo". Encadena los agentes del plugin en el orden de la receta, con compuertas y aprobación humana.
metadata:
  version: "1.5.0-draft"
---

# Crear una herramienta de auditoría externa de punta a punta

Aplicar la skill `metodologia-auditbrain` en todo momento (incluida la Puerta de conocimiento M31: reutilizar dominios y plugins ya instalados antes de construir). Comunicar al socio en español, sin tecnicismos, y avisar en
cada paso qué se hizo y qué sigue.

## Dónde corre

- **Claude Code y Cowork (plugin instalado):** lanzar cada paso con su agente.
- **Proyecto de claude.ai o entorno sin agentes:** aplicar en el mismo hilo el procedimiento equivalente de
  `references/agentes/<nombre>.md`, en el mismo orden y con las mismas compuertas.

## Antes de empezar

Confirmar, preguntando solo lo que falte (una pregunta a la vez):
1. Rubro o ciclo y afirmaciones que cubre.
2. **Marco (M02)**: contable (NIIF completas o PYMES) **o** legal/laboral/tributario (Código del Trabajo, IESS, MDT, LRTI) según el rubro. Sin marco no se diseña el cálculo.
3. Material de partida: HTML, Excel o prueba existente del socio (se analiza, no se copia a ciegas: M03, M09).
4. Si incluye tratamiento tributario.

## Secuencia (no saltar compuertas)

0. **`explorador-conocimiento`** (Puerta de conocimiento, M31) → si el rubro no está en `references/dominios/`, preguntar objetivo y norma; inventariar plugins y skills instalados que sirvan (p. ej. `finance:reconciliation` para conciliación bancaria); si hace falta, buscar la lógica y la norma en la web como borrador.
   Compuerta: **presentar lo hallado al socio y preguntar «¿así lo hace su firma?»**; lo que confirma se guarda en `references/dominios/<rubro>.md`. La web y los plugins proponen; el socio dispone.
1. **`analista-marco-norma`** → modelo que impone el marco al rubro y tabla párrafo → cálculo, NIA y tributario.
   Compuerta: norma leída del texto oficial; lo no verificado queda «VERIFICAR».
2. **`disenador-ficha`** → versión más simple que cumple y ficha A–E con el ejemplo numérico de control.
   Compuerta: **el socio aprueba el diseño** antes de construir.
3. **`arquitecto-calculo`** → declarativo o procesador (M18), anexos, modelos, cédulas con fórmulas y paquete de entrega
   para Claude Code (Command Center). Compuerta: especificación completa antes del código.
4. Construcción en el Command Center (Claude Code): procesador, pruebas con el ejemplo y casos límite, ciclo completo.
5. **`verificador-excel`** → cero diferencias en Excel real y prueba de mutación (M20).
6. **`revisor-pantallas`** → la vista de trabajo cumple M24 (con capturas).
7. **`auditor-cumplimiento`** → tabla M01–M24 con evidencia; cualquier Brecha bloqueante detiene la entrega.
8. **`preparador-publicacion`** → papel de muestra, cifras recalculadas a mano y lista de pendientes para el socio.
   Compuerta: **aprobación expresa del socio** para enviar al catálogo (M23). Nunca se deduce de una aprobación anterior.

Si el material de partida es un Excel ya armado, empezar por **`revisor-excel-existente`** y continuar la secuencia con
su diagnóstico.

## Cierre

Declarar: versión de memoria (v1.5.0-draft), marco y edición, compuertas superadas, resultado de la verificación en Excel,
pendientes y qué requiere aprobación del socio. Los errores encontrados y corregidos se informan.
