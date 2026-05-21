"""Construye un .xlsm con la macro VBA embebida a partir del .xlsx generado.

Arma un vbaProject.bin (contenedor OLE + compresion MS-OVBA), lo inserta en el
paquete OOXML, agrega un boton (forma DrawingML con atributo macro) en la hoja
"Generar XML" y reescribe el paquete como .xlsm.

Uso interno:  from _xlsm_builder import construir_xlsm
"""

from __future__ import annotations

import struct
import zipfile
from pathlib import Path

MODULO = "GenerarXmlSRI"


# --- Compresion MS-OVBA (solo literales: sin tokens de copia) ----------------

def ovba_compress(data: bytes) -> bytes:
    out = bytearray([0x01])  # SignatureByte
    pos = 0
    while pos < len(data):
        trozo = data[pos:pos + 3584]
        pos += len(trozo)
        cuerpo = bytearray()
        i = 0
        while i < len(trozo):
            cuerpo.append(0x00)               # FlagByte: 8 literales
            cuerpo += trozo[i:i + 8]
            i += 8
        size_field = (len(cuerpo) + 2) - 3
        header = (size_field & 0x0FFF) | 0x3000 | 0x8000  # firma 011, comprimido
        out += struct.pack("<H", header)
        out += cuerpo
    return bytes(out)


# --- Stream 'dir' (MS-OVBA 2.3.4.2) ------------------------------------------

def _rec(rid: int, data: bytes) -> bytes:
    return struct.pack("<HI", rid, len(data)) + data


def build_dir_stream() -> bytes:
    nombre = b"VBAProject"
    mod = MODULO.encode("latin-1")
    mod_u = MODULO.encode("utf-16-le")

    s = b""
    s += _rec(0x0001, struct.pack("<I", 1))           # SYSKIND Win32
    s += _rec(0x0002, struct.pack("<I", 0x409))       # LCID
    s += _rec(0x0014, struct.pack("<I", 0x409))       # LCIDINVOKE
    s += _rec(0x0003, struct.pack("<H", 0x04E4))      # CODEPAGE 1252
    s += _rec(0x0004, nombre)                          # NAME
    # DOCSTRING
    s += struct.pack("<HI", 0x0005, len(b"")) + b"" + \
        struct.pack("<HI", 0x0040, 0) + b""
    # HELPFILEPATH
    s += struct.pack("<HI", 0x0006, 0) + b"" + \
        struct.pack("<HI", 0x003D, 0) + b""
    s += _rec(0x0007, struct.pack("<I", 0))           # HELPCONTEXT
    s += _rec(0x0008, struct.pack("<I", 0))           # LIBFLAGS
    # VERSION: reserved=4, major(4), minor(2)
    s += struct.pack("<HI", 0x0009, 4) + struct.pack("<IH", 1, 0)
    # CONSTANTS
    s += struct.pack("<HI", 0x000C, 0) + b"" + \
        struct.pack("<HI", 0x003C, 0) + b""
    # MODULES
    s += _rec(0x000F, struct.pack("<H", 1))           # count = 1
    s += _rec(0x0013, struct.pack("<H", 0xFFFF))      # PROJECTCOOKIE
    # --- modulo ---
    s += _rec(0x0019, mod)                             # MODULENAME
    s += _rec(0x0047, mod_u)                           # MODULENAMEUNICODE
    s += struct.pack("<HI", 0x001A, len(mod)) + mod + \
        struct.pack("<HI", 0x0032, len(mod_u)) + mod_u   # STREAMNAME
    s += struct.pack("<HI", 0x001C, 0) + b"" + \
        struct.pack("<HI", 0x0048, 0) + b""              # MODULEDOCSTRING
    s += _rec(0x0031, struct.pack("<I", 0))           # MODULEOFFSET = 0
    s += _rec(0x001E, struct.pack("<I", 0))           # MODULEHELPCONTEXT
    s += _rec(0x002C, struct.pack("<H", 0xFFFF))      # MODULECOOKIE
    s += _rec(0x0021, b"")                             # MODULETYPE procedural
    s += _rec(0x002B, b"")                             # fin de modulo
    s += _rec(0x0010, b"")                             # fin del dir
    return s


def build_project_stream() -> str:
    # Sin CMG/DPB/GC: el proyecto VBA queda desbloqueado y visible.
    return (
        'ID="{5DD90D76-4BC2-11D1-886E-00608CA94CF1}"\r\n'
        f'Module={MODULO}\r\n'
        'Name="VBAProject"\r\n'
        'HelpContextID="0"\r\n'
        'VersionCompatible32="393222000"\r\n'
        '\r\n'
        '[Host Extender Info]\r\n'
        '&H00000001={3832D640-CF90-11CF-8E43-00A0C911005A};VBE;&H00000000\r\n'
        '\r\n'
        '[Workspace]\r\n'
        f'{MODULO}=0, 0, 0, 0, C\r\n'
    )


def build_projectwm() -> bytes:
    return (MODULO.encode("latin-1") + b"\x00" +
            MODULO.encode("utf-16-le") + b"\x00\x00" + b"\x00\x00")


def build_vba_project_stream() -> bytes:
    # Reserved1, Version, Reserved2, Reserved3 + PerformanceCache vacio
    return bytes([0xCC, 0x61, 0xFF, 0xFF, 0x00, 0x00, 0x00])


# --- Contenedor OLE (Compound File Binary, sectores de 512) ------------------

FREESECT = 0xFFFFFFFF
ENDOFCHAIN = 0xFFFFFFFE
FATSECT = 0xFFFFFFFD
NOSTREAM = 0xFFFFFFFF


def _dir_entry(name, etype, color, left, right, child, start, size):
    nb = name.encode("utf-16-le") + b"\x00\x00"
    nb = nb.ljust(64, b"\x00")[:64]
    namelen = (len(name) + 1) * 2
    return (nb + struct.pack("<HBB", namelen, etype, color) +
            struct.pack("<III", left, right, child) +
            b"\x00" * 16 + b"\x00" * 4 +
            b"\x00" * 8 + b"\x00" * 8 +
            struct.pack("<I", start) + struct.pack("<Q", size))


def build_cfb(vba_stream: bytes, dir_stream: bytes, project: bytes,
              projectwm: bytes) -> bytes:
    """Arma vbaProject.bin con: PROJECT, PROJECTwm y storage VBA/(_VBA_PROJECT,
    dir, GenerarXmlSRI). Las streams < 4096 van al mini-stream."""
    SEC = 512
    MINI = 64

    # streams: (nombre, datos, mini?)
    streams = [
        ("PROJECT", project, True),
        ("PROJECTwm", projectwm, True),
        ("_VBA_PROJECT", build_vba_project_stream(), True),
        ("dir", dir_stream, True),
        (MODULO, vba_stream, len(vba_stream) < 4096),
    ]

    # --- mini stream ---
    mini_blob = bytearray()
    mini_info = {}  # nombre -> (start_mini_sector, size)
    minifat = []
    for nombre, datos, es_mini in streams:
        if not es_mini:
            continue
        start = len(minifat)
        n = max(1, (len(datos) + MINI - 1) // MINI)
        for j in range(n):
            minifat.append(ENDOFCHAIN if j == n - 1 else start + j + 1)
        mini_blob += datos.ljust(n * MINI, b"\x00")
        mini_info[nombre] = (start, len(datos))
    mini_blob = bytes(mini_blob)

    # --- streams regulares (mini-stream-container + modulo si es grande) ---
    reg = []  # (clave, datos)
    reg.append(("__mini__", mini_blob))
    for nombre, datos, es_mini in streams:
        if not es_mini:
            reg.append((nombre, datos))

    # minifat empaquetado
    minifat_bytes = b"".join(struct.pack("<I", x) for x in minifat)
    minifat_bytes = minifat_bytes.ljust(
        ((len(minifat_bytes) + SEC - 1) // SEC) * SEC, b"\xff")
    n_minifat = max(1, len(minifat_bytes) // SEC) if minifat else 0
    if not minifat:
        n_minifat = 0
        minifat_bytes = b""

    # directorio: Root, VBA, PROJECT, PROJECTwm, _VBA_PROJECT, dir, MODULO
    n_dir_entries = 7
    dir_bytes_len = ((n_dir_entries * 128 + SEC - 1) // SEC) * SEC
    n_dir = dir_bytes_len // SEC

    # tamano de cada stream regular en sectores
    reg_sizes = [(k, d, max(1, (len(d) + SEC - 1) // SEC)) for k, d in reg]
    n_reg = sum(s for _k, _d, s in reg_sizes)

    # layout de sectores: [FAT][dir][miniFAT][regulares...]
    # numero de sectores FAT: iterativo
    total_no_fat = n_dir + n_minifat + n_reg
    n_fat = 1
    while True:
        total = n_fat + total_no_fat
        cap = (n_fat * SEC) // 4
        if cap >= total:
            break
        n_fat += 1

    # asignacion de sectores
    fat = []
    sec = 0
    fat_secs = list(range(sec, sec + n_fat)); sec += n_fat
    dir_secs = list(range(sec, sec + n_dir)); sec += n_dir
    minifat_secs = list(range(sec, sec + n_minifat)); sec += n_minifat
    reg_secs = {}
    for k, d, ns in reg_sizes:
        reg_secs[k] = list(range(sec, sec + ns)); sec += ns
    total_secs = sec

    # FAT
    fat = [FREESECT] * (n_fat * SEC // 4)
    for x in fat_secs:
        fat[x] = FATSECT

    def encadenar(secs):
        for i, x in enumerate(secs):
            fat[x] = ENDOFCHAIN if i == len(secs) - 1 else secs[i + 1]

    encadenar(dir_secs)
    if minifat_secs:
        encadenar(minifat_secs)
    for k, d, ns in reg_sizes:
        encadenar(reg_secs[k])

    # cabecera
    header = bytearray(512)
    header[0:8] = bytes([0xD0, 0xCF, 0x11, 0xE0, 0xA1, 0xB1, 0x1A, 0xE1])
    struct.pack_into("<HH", header, 24, 0x003E, 0x0003)   # version
    struct.pack_into("<H", header, 28, 0xFFFE)            # byte order
    struct.pack_into("<HH", header, 30, 0x0009, 0x0006)   # sector shifts
    struct.pack_into("<I", header, 44, n_fat)
    struct.pack_into("<I", header, 48, dir_secs[0])
    struct.pack_into("<I", header, 56, 0x00001000)        # mini cutoff
    struct.pack_into("<I", header, 60,
                     minifat_secs[0] if minifat_secs else ENDOFCHAIN)
    struct.pack_into("<I", header, 64, n_minifat)
    struct.pack_into("<I", header, 68, ENDOFCHAIN)        # DIFAT
    struct.pack_into("<I", header, 72, 0)
    for i in range(109):
        v = fat_secs[i] if i < n_fat else FREESECT
        struct.pack_into("<I", header, 76 + i * 4, v)

    # directorio
    mini_start = reg_secs["__mini__"][0]
    p_start, p_size = mini_info["PROJECT"]
    pw_start, pw_size = mini_info["PROJECTwm"]
    vp_start, vp_size = mini_info["_VBA_PROJECT"]
    d_start, d_size = mini_info["dir"]
    if MODULO in mini_info:
        m_start, m_size = mini_info[MODULO]
    else:
        m_start, m_size = reg_secs[MODULO][0], len(vba_stream)

    entries = b""
    # 0 Root  -> child = PROJECT (2)
    entries += _dir_entry("Root Entry", 5, 1, NOSTREAM, NOSTREAM, 2,
                          mini_start, len(mini_blob))
    # 1 VBA storage -> child = _VBA_PROJECT (4)
    entries += _dir_entry("VBA", 1, 1, NOSTREAM, NOSTREAM, 4, 0, 0)
    # 2 PROJECT  (left=VBA 1, right=PROJECTwm 3)
    entries += _dir_entry("PROJECT", 2, 1, 1, 3, NOSTREAM, p_start, p_size)
    # 3 PROJECTwm
    entries += _dir_entry("PROJECTwm", 2, 1, NOSTREAM, NOSTREAM, NOSTREAM,
                          pw_start, pw_size)
    # 4 _VBA_PROJECT (left=dir 5, right=MODULO 6)
    entries += _dir_entry("_VBA_PROJECT", 2, 1, 5, 6, NOSTREAM,
                          vp_start, vp_size)
    # 5 dir
    entries += _dir_entry("dir", 2, 1, NOSTREAM, NOSTREAM, NOSTREAM,
                          d_start, d_size)
    # 6 MODULO
    entries += _dir_entry(MODULO, 2, 1, NOSTREAM, NOSTREAM, NOSTREAM,
                          m_start, m_size)
    dir_bytes = entries.ljust(dir_bytes_len, b"\x00")

    # ensamblar archivo
    cuerpo = bytearray()
    for x in fat:
        cuerpo += struct.pack("<I", x)
    cuerpo = bytearray(b"".join(struct.pack("<I", x) for x in fat))
    cuerpo += dir_bytes
    cuerpo += minifat_bytes
    for k, d, ns in reg_sizes:
        cuerpo += d.ljust(ns * SEC, b"\x00")

    return bytes(header) + bytes(cuerpo)


def build_vba_project_bin(bas_text: str) -> bytes:
    fuente = bas_text.replace("\r\n", "\n").replace("\n", "\r\n")
    fuente_b = fuente.encode("latin-1", errors="replace")
    vba_stream = ovba_compress(fuente_b)
    dir_stream = ovba_compress(build_dir_stream())
    project = build_project_stream().encode("latin-1")
    return build_cfb(vba_stream, dir_stream, project, build_projectwm())


# --- Ensamblado del paquete .xlsm --------------------------------------------

import re  # noqa: E402

_NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

DRAWING_XML = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<xdr:wsDr xmlns:xdr="http://schemas.openxmlformats.org/drawingml/2006/'
    'spreadsheetDrawing" xmlns:a="http://schemas.openxmlformats.org/'
    'drawingml/2006/main">'
    '<xdr:twoCellAnchor editAs="oneCell">'
    '<xdr:from><xdr:col>1</xdr:col><xdr:colOff>0</xdr:colOff>'
    '<xdr:row>4</xdr:row><xdr:rowOff>0</xdr:rowOff></xdr:from>'
    '<xdr:to><xdr:col>4</xdr:col><xdr:colOff>0</xdr:colOff>'
    '<xdr:row>6</xdr:row><xdr:rowOff>0</xdr:rowOff></xdr:to>'
    '<xdr:sp macro="GenerarXmlSRI" textlink="">'
    '<xdr:nvSpPr><xdr:cNvPr id="1" name="BotonGenerarXML"/>'
    '<xdr:cNvSpPr/></xdr:nvSpPr>'
    '<xdr:spPr>'
    '<a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/></a:xfrm>'
    '<a:prstGeom prst="roundRect"><a:avLst/></a:prstGeom>'
    '<a:solidFill><a:srgbClr val="1E6B52"/></a:solidFill>'
    '<a:ln><a:solidFill><a:srgbClr val="10243E"/></a:solidFill></a:ln>'
    '</xdr:spPr>'
    '<xdr:txBody><a:bodyPr vertOverflow="clip" horzOverflow="clip" '
    'anchor="ctr"/><a:lstStyle/>'
    '<a:p><a:pPr algn="ctr"/><a:r>'
    '<a:rPr lang="es-EC" sz="1400" b="1">'
    '<a:solidFill><a:srgbClr val="FFFFFF"/></a:solidFill></a:rPr>'
    '<a:t>GENERAR XML</a:t></a:r></a:p>'
    '</xdr:txBody></xdr:sp><xdr:clientData/>'
    '</xdr:twoCellAnchor></xdr:wsDr>'
)


def construir_xlsm(xlsx_path: Path, xlsm_path: Path, bas_text: str):
    """Convierte el .xlsx en .xlsm con la macro VBA y el boton embebidos."""
    vba = build_vba_project_bin(bas_text)

    with zipfile.ZipFile(xlsx_path) as zin:
        items = {n: zin.read(n) for n in zin.namelist()}

    # numero de drawing libre
    nums = [int(m.group(1)) for n in items
            for m in [re.match(r"xl/drawings/drawing(\d+)\.xml$", n)] if m]
    dnum = (max(nums) + 1) if nums else 1
    drawing_part = f"xl/drawings/drawing{dnum}.xml"

    # 1. Content Types
    ct = items["[Content_Types].xml"].decode("utf-8")
    ct = ct.replace(
        "application/vnd.openxmlformats-officedocument.spreadsheetml."
        "sheet.main+xml",
        "application/vnd.ms-excel.sheet.macroEnabled.main+xml")
    extra = (
        '<Override PartName="/xl/vbaProject.bin" '
        'ContentType="application/vnd.ms-office.vbaProject"/>'
        f'<Override PartName="/{drawing_part}" '
        'ContentType="application/vnd.openxmlformats-officedocument.'
        'drawing+xml"/>')
    ct = ct.replace("</Types>", extra + "</Types>")
    items["[Content_Types].xml"] = ct.encode("utf-8")

    # 2. relacion del vbaProject en workbook.xml.rels
    rels = items["xl/_rels/workbook.xml.rels"].decode("utf-8")
    ids = [int(x) for x in re.findall(r'Id="rId(\d+)"', rels)]
    vba_rid = f"rId{(max(ids) + 1) if ids else 1}"
    rels = rels.replace(
        "</Relationships>",
        f'<Relationship Id="{vba_rid}" Type="http://schemas.microsoft.com/'
        f'office/2006/relationships/vbaProject" Target="vbaProject.bin"/>'
        "</Relationships>")
    items["xl/_rels/workbook.xml.rels"] = rels.encode("utf-8")

    # 3. vbaProject.bin
    items["xl/vbaProject.bin"] = vba

    # 4. localizar la hoja "Generar XML"
    wb = items["xl/workbook.xml"].decode("utf-8")
    tag = re.search(r'<sheet [^>]*name="Generar XML"[^>]*/>', wb).group(0)
    rid = re.search(r'r:id="([^"]+)"', tag).group(1)
    rel = re.search(r'<Relationship [^>]*Id="' + rid + r'"[^>]*/>',
                    rels).group(0)
    target = re.search(r'Target="([^"]+)"', rel).group(1)
    sheet_path = "xl/" + target.split("xl/", 1)[-1] if "xl/" in target \
        else target.lstrip("/")
    sheet_path = target.lstrip("/") if target.startswith("/") else \
        "xl/" + target

    # 5. <drawing> en la hoja
    ws = items[sheet_path].decode("utf-8")
    ws = ws.replace(
        "</worksheet>",
        f'<drawing xmlns:r="{_NS_R}" r:id="rId1"/></worksheet>')
    items[sheet_path] = ws.encode("utf-8")

    # 6. rels de la hoja
    nombre_hoja = sheet_path.split("/")[-1]
    wsrels = ("xl/worksheets/_rels/" + nombre_hoja + ".rels")
    items[wsrels] = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/'
        '2006/relationships">'
        f'<Relationship Id="rId1" Type="{_NS_R}/drawing" '
        f'Target="../drawings/drawing{dnum}.xml"/>'
        "</Relationships>").encode("utf-8")

    # 7. drawing con el boton
    items[drawing_part] = DRAWING_XML.encode("utf-8")

    # 8. escribir el .xlsm
    with zipfile.ZipFile(xlsm_path, "w", zipfile.ZIP_DEFLATED) as zout:
        for nombre, datos in items.items():
            zout.writestr(nombre, datos)

