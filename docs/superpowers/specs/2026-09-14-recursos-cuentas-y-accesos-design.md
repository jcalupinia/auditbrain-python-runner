# Recursos gratuitos v2 — Cuentas con clave personal y accesos por recurso

Fecha: 2026-09-14 · Estado: **aprobado por el dueño** ("apruebo el diseño completo").
Reemplaza el acceso por enlace mágico del diseño v1
(`2026-09-14-registro-recursos-gratuitos-design.md`), que queda como histórico.

## Objetivo

Que `recursos.audit-ia.ec` funcione como una aplicación con cuentas:

- Quien se registra en la **Calculadora de Impuesto a la Renta de Personas Naturales 2026**
  recibe por correo **usuario (su correo) y una clave personal generada automáticamente**, y
  queda con acceso **solo** a esa calculadora.
- La **Calculadora del Anticipo IR 2026** pasa a **acceso restringido**: solo entran las
  cuentas a las que la firma otorga acceso desde la consola. Su tarjeta muestra "NUEVO"
  animado y "Acceso bajo solicitud" para generar interés y contacto.
- El personal gestiona cuentas desde la consola (pestaña REC) igual que en **Cuentas**:
  casillas de acceso por recurso, **Resetear clave** (clave escrita por el admin o generada;
  se muestra una sola vez; opcional enviarla por correo) y **Desactivar/Activar**.
- Los botones de acción de ambas calculadoras suben debajo del bloque de datos y adoptan
  un estilo de botón "tipo software" con relieve 3D.

Fuera de alcance: "una sesión a la vez" (se agrega si se detecta clave compartida),
claves elegidas por el usuario final, borrado/purga LOPDP desde la consola.

## Modelo de datos (tablas nuevas; `recurso_leads` no cambia)

`recurso_cuentas` — una por persona:

| Columna | Tipo | Nota |
|---|---|---|
| id | int PK | |
| email | str(320), único, index | minúsculas |
| hashed_clave | str(255) | `auth.password.hash_password` |
| clave_generada | bool | True = clave generada (se compara normalizada: sin guiones/espacios, mayúsculas); False = escrita por el admin (comparación exacta) |
| activo | bool, default true | desactivada = no puede ingresar |
| ultimo_ingreso_at | datetime null | |
| clave_actualizada_at | datetime | |
| created_at | datetime | |

`recurso_accesos` — permisos: `id`, `cuenta_id` (FK recurso_cuentas.id), `recurso_slug`
str(64), `otorgado_por` str(320) (`"registro"` o email del admin), `created_at`;
`UniqueConstraint(cuenta_id, recurso_slug)`.

`recurso_leads` sigue siendo el registro de consentimiento (nombre, empresa, correo,
fecha y versión de la política) de la calculadora donde la persona se registró.

Tablas nuevas vía `create_all` (sin ALTER sobre tablas existentes).

## Catálogo

`catalog.py`: cada `Recurso` gana `registro_abierto: bool`.
- `ir-personas-naturales-2026` — registro abierto; el registro otorga este acceso.
- `anticipo-ir-2026` — **registro cerrado**; acceso solo por otorgamiento del admin.
  URL `https://recursos.audit-ia.ec/anticipo-ir-2026/`.

## Clave personal

`generar_clave()`: 9 caracteres de `ABCDEFGHJKMNPQRSTUVWXYZ23456789` (sin O/0/I/1/L) con
`secrets`, presentados como `XXX-XXX-XXX`. Se guarda solo el hash. La verificación ignora
guiones, espacios y mayúsculas/minúsculas en lo que escribe el usuario. Si el admin escribe
una clave (mín. 8 caracteres), se guarda tal cual (hash) y se compara exacta.

## Endpoints (prefijo `/api/v1/recursos`)

Públicos (`registros` y `olvide-clave` comparten el límite por IP `recurso-reg:{ip}`
10/600 s; `ingresar` tiene el suyo, `recurso-login-ip:{ip}` 30/600 s; más los topes de
correo 3/h por correo y 30/h global ya existentes):

| Ruta | Comportamiento |
|---|---|
| `POST /{slug}/registros` | Solo si `registro_abierto` (si no, 404). Guarda/conserva el lead (igual que hoy). Si la cuenta **no existe**: la crea con clave nueva, otorga el acceso a `slug` y envía el correo con usuario y clave. Si **ya existe**: se comporta como "olvidé mi clave" (clave nueva por correo; asegura el acceso a `slug`). Respuesta 201 idéntica en ambos casos. |
| `POST /{slug}/ingresar` `{email, clave}` | 401 `"Usuario o clave incorrectos."` si la cuenta no existe, está inactiva o la clave no coincide. Si las credenciales son válidas pero no hay acceso a `slug`: 403 `"Su usuario aún no tiene acceso a esta herramienta. Solicítelo por WhatsApp 0990 609 811 o a jcalupinia@auditconsulting.ec."`. 200 `{ok, nombre}` si todo es válido; actualiza `ultimo_ingreso_at` y marca `verificado_at` del lead (probó que recibió el correo). Límite adicional por correo: 10 intentos/10 min (`recurso-login:{email}`; el contador se reinicia al ingresar bien; bloqueado, ni la clave correcta pasa) → 429. |
| `POST /{slug}/olvide-clave` `{email}` | Si la cuenta existe y está activa: clave nueva por correo (la anterior deja de servir). Si existe el lead pero no la cuenta (registros previos a v2): crea la cuenta con acceso a los recursos de sus leads y envía la clave. Respuesta 200 genérica siempre. Sujeto a los topes de correo. |

Se **eliminan** `GET /{slug}/acceso` (enlace mágico) y el módulo `tokens.py`, y el endpoint
`/{slug}/reenviar` (reemplazado por `olvide-clave`).

Staff (`require_staff` para leer; **`require_admin`** para modificar, igual que Cuentas):

| Ruta | Comportamiento |
|---|---|
| `GET /cuentas` | Lista de cuentas con: email, nombre y empresa (del lead más reciente), activo, accesos (slugs), ultimo_ingreso_at, created_at, consentimiento_at, email_enviado. |
| `PUT /cuentas/{id}/accesos/{slug}` / `DELETE …` | Otorga / quita acceso (slug debe existir en el catálogo). `otorgado_por` = email del admin. |
| `POST /cuentas/{id}/reset-clave` `{new_password?: str, enviar_correo: bool}` | Igual que Cuentas: con `new_password` (mín. 8) queda esa; sin ella se genera. Devuelve `{email, temp_password, note}` **una sola vez**. Si `enviar_correo`, envía el correo con la clave. |
| `POST /cuentas/{id}/activo` `{activo: bool}` | Activa/desactiva. |

`GET /registros` se mantiene (histórico de leads).

### Límites y riesgos aceptados

- Cualquiera que conozca un correo puede provocar una clave nueva (registro u "olvidé mi
  clave"): máx. 3/h por correo y la clave nueva llega solo a la víctima, que puede
  seguir entrando con ella. Aceptado.
- La restricción de acceso por recurso vive en la interfaz del mini-sitio (sitio
  estático): **no es una frontera de seguridad**; quien lea el HTML ve la calculadora.
- Bloqueo de ingreso: 10 intentos/10 min por correo y 30/10 min por IP. La verificación
  corre bcrypt siempre (señuelo si la cuenta no existe) para no revelar correos por tiempo.
- Claves escritas por el admin: 8 a 72 bytes (límite de bcrypt).
- Sin accesos otorgados no se envía clave por correo (no hay a dónde enlazar).

## Correo (plantilla `recurso_acceso.html`, línea gráfica navy/lime ya aprobada)

Asunto: `Su usuario y clave — {titulo}`. Contenido: "Su usuario: {email}", "Su clave:
{clave}" (recuadro destacado, fuente monoespaciada), botón **"Ingresar a mi calculadora"** →
URL del recurso (muestra la pantalla de acceso), texto: "Guarde este correo. Puede ingresar
cuando quiera desde recursos.audit-ia.ec. Si olvida su clave, use '¿Olvidó su clave?'".
El resto (contacto, LOPDP, BAJA) igual. Sin texto escrito por el usuario (anti-suplantación).

## Mini-sitio

**Pantalla de acceso** (bloque `#gate` en ambas calculadoras; `SLUG` y `REGISTRO_ABIERTO`
por página):
- Vista **Ingresar**: logo, "Ingrese a su calculadora", Usuario (correo), Clave (con botón
  mostrar/ocultar), botón **Ingresar**, enlace "¿Olvidó su clave?".
  - PN: debajo "¿No tiene cuenta? **Regístrese**" → vista Registro (formulario actual).
  - Anticipo: debajo, recuadro "Herramienta de acceso restringido para clientes y usuarios
    autorizados. Solicite su acceso:" + botones WhatsApp (`https://wa.me/593990609811` con
    texto prellenado "Hola, quiero acceso a la Calculadora del Anticipo IR 2026") y correo.
- Vista **Registro** (solo PN): igual que hoy; al enviar → "Listo. Le enviamos su usuario y
  clave a {correo}…" + botón "Ya tengo mi clave → Ingresar".
- Vista **Olvidé mi clave**: correo → mensaje genérico.
- Errores: 401/403/429 con los textos del backend; red → "No pudimos conectar…".
- Éxito: `localStorage["acg_acceso_<slug>"]="1"`, se oculta el recuadro. Hash `#registro`
  abre directo la vista Registro; `#ingresar` la de Ingresar. Se elimina el manejo de
  `?acceso=`.

**Página de recursos**: tarjeta 01 con botones **Ingresar** (`ir-personas-naturales-2026/#ingresar`)
y **Quiero la calculadora gratis** (`#registro`). Tarjeta 02 con etiqueta **NUEVO** animada
(pulso suave, respeta `prefers-reduced-motion`), texto "Acceso bajo solicitud", botones
**Ingresar** y **Solicitar acceso** (WhatsApp prellenado).

**Botones de las calculadoras**: la fila de acciones sube debajo de la tarjeta de datos
(PN: después de "Identificación y Parámetros"; Anticipo: después de los datos de la
empresa, incluidos Guardar/Cargar/Eliminar cliente). Estilo 3D: degradado navy con brillo
superior, sombra inferior, se eleva en hover y se hunde en active; primario "Procesar
Cálculo" en lima; secundarios blancos con relieve y borde navy; íconos ▶ ⧉ ↺ 🖨. Mismo estilo
en los botones del recuadro de acceso y de las tarjetas.

## Consola — pestaña REC

Tabla de **cuentas** (una fila por persona): nombre, empresa, correo, fecha, último ingreso,
columnas de acceso con una casilla por recurso del catálogo (PN / Anticipo), estado, y
acciones **Resetear clave** (ventana igual a Cuentas: escribir clave + confirmar, o dejar
vacío para generar; casilla "Enviar la clave por correo"; la clave resultante se muestra una
vez con aviso de canal seguro) y **Desactivar/Activar**. Casillas y acciones solo para
admin (operadores ven la tabla). CSV incluye accesos y estado.

## Pruebas

Backend: generador de clave (formato/alfabeto), registro nuevo crea cuenta+acceso+correo con
clave, registro repetido rota clave, registro en recurso cerrado → 404, ingresar
200/401/403/429, clave con guiones/minúsculas válida, cuenta inactiva → 401, olvidé clave
(existente / lead sin cuenta / inexistente genérico), endpoints staff (auth 401/403 para
operador en modificaciones, 200 admin), reset con y sin clave, correo sin texto de usuario.
Frontend: vitest de la tabla/acciones si hay patrón; build. Mini-sitio: E2E local de ambas
páginas (registro, correo simulado, ingresar, 403 anticipo, otorgar acceso en consola,
ingresar anticipo), móvil, capturas de botones para el dueño.

## Despliegue

PR del portal (aprobación del dueño) → Render despliega → commit/push del mini-sitio con
aprobación. Ojo: al publicar, el anticipo deja de estar abierto.
