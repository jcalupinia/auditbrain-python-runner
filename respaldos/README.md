# Respaldos

## `auditbrain-site.bundle`

Respaldo completo del repositorio **AuditBrain Sites** (`auditbrain-site`), el sitio
de auditoría externa que se publica en ChatGPT Sites.

Ese repositorio vive solo en el disco de la estación de trabajo y **no tiene remoto
propio**, así que este archivo es su única copia fuera de esa máquina.

### Qué contiene

Un *bundle* de git: un archivo único con **todo el historial**, no una copia de los
archivos. Al 2026-09-20 (noche) trae 21 commits, las ramas `master` y `motor-niif-fase-1`,
y 267 archivos versionados.

Se eligió un bundle y no una copia de la carpeta a propósito: el sitio ya tiene tres
copias del motor de cálculo que no pueden divergir (ver su `AGENTS.md`), y una cuarta
copia suelta que alguien pudiera editar por error sería exactamente el problema que
ese diseño intenta evitar. Un bundle es opaco y no se edita.

### Cómo restaurarlo

```bash
git clone auditbrain-site.bundle auditbrain-site
cd auditbrain-site
git checkout motor-niif-fase-1
npm install
```

Después, para comprobar que el motor quedó intacto:

```bash
node verif-niif16.mjs            # arrendamiento NIIF 16 contra la formula cerrada
node --test tests/tools/*.test.mjs
```

### Cómo actualizarlo

Desde el repositorio del sitio:

```bash
git bundle create "<ruta a este directorio>/auditbrain-site.bundle" --all
git bundle verify "<ruta a este directorio>/auditbrain-site.bundle"
```

**Hay que rehacerlo tras cada tanda de trabajo en el sitio.** Un bundle viejo da una
falsa sensación de respaldo: la fecha del archivo dice cuándo se hizo, no hasta dónde
llega el historial. Para saberlo con certeza:

```bash
git bundle verify auditbrain-site.bundle
```

### Verificado

El 2026-09-20 se restauró en un directorio limpio y se comprobó que recupera los 12
commits, las dos ramas, los 264 archivos y el commit correcto en `HEAD`.
