Attribute VB_Name = "GenerarXmlSRI"
' ============================================================================
'  Motor VBA para generar el XML de la Declaracion Patrimonial del SRI
'  a partir del libro Excel producido por declaracion_patrimonial_excel.py.
'
'  INSTALACION (una sola vez):
'    1. Abra el editor con Alt + F11.
'    2. Archivo > Importar archivo... y seleccione este archivo .bas.
'    3. Guarde el libro como .xlsm (habilitado para macros).
'    4. Inserte un boton (Programador > Insertar) y asigne la macro
'       "GenerarXmlSRI".
'
'  La macro lee la hoja oculta "_Mapa" (etiquetas XML), las hojas de los
'  modulos, "Datos del XML" y "Justificacion", y escribe el archivo .xml.
' ============================================================================
Option Explicit


Public Sub GenerarXmlSRI()
    On Error GoTo Fallo

    Dim sAnio As String, anio As Long
    sAnio = InputBox("Anio de la declaracion a generar para el SRI:", _
                     "Generar XML para el SRI", CStr(AnioPorDefecto()))
    If Trim$(sAnio) = "" Then Exit Sub
    If Not IsNumeric(sAnio) Then
        MsgBox "El anio ingresado no es valido.", vbExclamation
        Exit Sub
    End If
    anio = CLng(sAnio)

    Dim xml As String
    xml = ConstruirXml(anio)

    Dim ruta As Variant
    ruta = Application.GetSaveAsFilename( _
        InitialFileName:=RutaLibro() & "DeclaracionPatrimonial_" & anio & ".xml", _
        FileFilter:="Archivo XML (*.xml), *.xml")
    If ruta = False Then Exit Sub

    GuardarTexto CStr(ruta), xml
    MsgBox "XML generado correctamente:" & vbCrLf & vbCrLf & ruta, _
           vbInformation, "Generar XML para el SRI"
    Exit Sub

Fallo:
    MsgBox "No se pudo generar el XML:" & vbCrLf & vbCrLf & Err.Description, _
           vbCritical, "Generar XML para el SRI"
End Sub


Private Function RutaLibro() As String
    RutaLibro = ThisWorkbook.Path
    If RutaLibro <> "" Then RutaLibro = RutaLibro & Application.PathSeparator
End Function


Private Function AnioPorDefecto() As Long
    Dim ws As Worksheet, c As Long, h As String, mx As Long
    Set ws = ThisWorkbook.Sheets("Dinero")
    For c = 1 To 80
        h = CStr(ws.Cells(5, c).Value)
        If Left$(h, 6) = "Valor " And IsNumeric(Mid$(h, 7)) Then
            If CLng(Mid$(h, 7)) > mx Then mx = CLng(Mid$(h, 7))
        End If
    Next c
    If mx = 0 Then mx = Year(Date)
    AnioPorDefecto = mx
End Function


Private Function ConstruirXml(anio As Long) As String
    Const L As String = vbLf
    Dim shMapa As Worksheet, ult As Long, mapa As Variant
    Set shMapa = ThisWorkbook.Sheets("_Mapa")
    ult = shMapa.Cells(shMapa.Rows.Count, 1).End(xlUp).Row
    mapa = shMapa.Range("A2:I" & ult).Value

    ' modulos (key -> ordenXml)
    Dim keys As Object: Set keys = CreateObject("Scripting.Dictionary")
    Dim i As Long
    For i = 1 To UBound(mapa, 1)
        If Not keys.Exists(CStr(mapa(i, 1))) Then
            keys.Add CStr(mapa(i, 1)), CLng(mapa(i, 6))
        End If
    Next i

    ' construir contenedor y total de cada modulo
    Dim contXml As Object: Set contXml = CreateObject("Scripting.Dictionary")
    Dim totMod As Object: Set totMod = CreateObject("Scripting.Dictionary")
    Dim totAct As Double, totPas As Double
    Dim k As Variant, clase As String, tt As Double
    For Each k In keys.Keys
        contXml(k) = ModuloXml(CStr(k), mapa, anio, tt, clase)
        totMod(k) = tt
        If clase = "activo" Then
            totAct = totAct + tt
        Else
            totPas = totPas + tt
        End If
    Next k

    Dim totalDecl As Double
    totalDecl = Redondear(totAct - totPas)

    Dim s As String
    s = "<?xml version=""1.0"" encoding=""ISO-8859-1"" standalone=""yes""?>" & L
    s = s & "<decPat>" & L
    s = s & "    <anio>" & anio & "</anio>" & L
    s = s & Linea("tipoDec", Codigo(DatoXml("Tipo de declaracion")))
    s = s & Linea("tipoIdent", Codigo(DatoXml("Tipo de identificacion")))
    s = s & Linea("numIdent", DatoXml("Numero de identificacion"))
    s = s & Linea("nombre", DatoXml("Nombre del declarante"))

    Dim nIdCony As String: nIdCony = DatoXml("Numero ident. conyuge")
    If nIdCony <> "" Then
        s = s & Linea("tipoIdentCony", Codigo(DatoXml("Identificacion del conyuge")))
        s = s & Linea("numIdentCony", nIdCony)
        s = s & Linea("nombreCony", DatoXml("Nombre del conyuge"))
    End If

    Dim regul As String: regul = Codigo(DatoXml("Regularizacion de activos"))
    If regul <> "" Then s = s & Linea("regularizacionActivos", regul)

    s = s & "    <totalCreditos>" & Num2(ValDic(totMod, "cxc")) & _
        "</totalCreditos>" & L
    If ValDic(totMod, "derechos") > 0 Then
        s = s & "    <totalDerechos>" & Num2(ValDic(totMod, "derechos")) & _
            "</totalDerechos>" & L
    End If

    ' patrimonio
    Dim anioAnt As Double
    anioAnt = PatrimonioAnio(anio - 1)
    If anioAnt = -1 Then anioAnt = ValTexto(DatoXml("Patrimonio del anio anterior"))
    Dim dif As Double: dif = Redondear(totalDecl - anioAnt)

    Dim atr As Double, soc As Double, ind As Double
    atr = ValTexto(DatoXml("Atribuible a hijos no emancipados"))
    soc = ValTexto(DatoXml("Patrimonio en la sociedad conyugal"))
    ind = ValTexto(DatoXml("Patrimonio individual del declarante"))
    If Abs(atr + soc + ind - totalDecl) > 0.01 Then
        atr = 0
        If Codigo(DatoXml("Tipo de declaracion")) = "SOC" Then
            soc = totalDecl: ind = 0
        Else
            soc = 0: ind = totalDecl
        End If
    End If

    s = s & "    <patrimonio>" & L
    s = s & "        <totalDeclarado>" & Num2(totalDecl) & "</totalDeclarado>" & L
    s = s & "        <atribuibleHijos>" & Num2(atr) & "</atribuibleHijos>" & L
    s = s & "        <sociedadConyugal>" & Num2(soc) & "</sociedadConyugal>" & L
    s = s & "        <individual>" & Num2(ind) & "</individual>" & L
    s = s & "        <anioAnterior>" & Num2(anioAnt) & "</anioAnterior>" & L
    If dif >= 0 Then
        s = s & "        <crecimientoPat>" & Num2(dif) & "</crecimientoPat>" & L
    Else
        s = s & "        <decrecimientoPat>" & Num2(-dif) & _
            "</decrecimientoPat>" & L
    End If
    ' La justificacion solo aplica cuando hay CRECIMIENTO patrimonial (SRI).
    s = s & "    <justificacion>" & L
    If dif > 0.005 Then s = s & JustificacionXml()
    s = s & "</justificacion></patrimonio>" & L

    ' contenedores en el orden del XML del SRI
    Dim ordenados() As String
    ordenados = ClavesOrdenadas(keys)
    For i = 0 To UBound(ordenados)
        s = s & contXml(ordenados(i))
    Next i

    s = s & "</decPat>"
    ConstruirXml = s
End Function


Private Function ModuloXml(key As String, mapa As Variant, anio As Long, _
                           ByRef total As Double, ByRef clase As String) As String
    Const L As String = vbLf
    Dim idx() As Long, n As Long, i As Long
    ReDim idx(1 To 200)
    Dim hoja As String, contenedor As String, detalle As String
    For i = 1 To UBound(mapa, 1)
        If CStr(mapa(i, 1)) = key Then
            n = n + 1
            idx(n) = i
            hoja = CStr(mapa(i, 2))
            contenedor = CStr(mapa(i, 3))
            detalle = CStr(mapa(i, 4))
            clase = CStr(mapa(i, 5))
        End If
    Next i

    Dim ws As Worksheet: Set ws = ThisWorkbook.Sheets(hoja)
    Dim colVal As Long: colVal = ColumnaValor(ws, anio)

    Dim cuerpo As String, r As Long
    total = 0
    r = 6
    Do While r < 5000
        If CStr(ws.Cells(r, 1).Value) = "TOTAL" Then Exit Do
        Dim valor As Double: valor = ValTexto(CStr(ws.Cells(r, colVal).Value))
        total = total + valor
        If valor > 0 Then
            Dim det As String: det = "<" & detalle & ">" & L
            For i = 1 To n
                Dim tipo As String, etiqueta As String, di As Long
                tipo = CStr(mapa(idx(i), 7))
                etiqueta = CStr(mapa(idx(i), 8))
                di = CLng(mapa(idx(i), 9))
                If tipo = "val" Then
                    det = det & "    <" & etiqueta & ">" & Num2(valor) & _
                        "</" & etiqueta & ">" & L
                Else
                    Dim celda As String
                    celda = Trim$(CStr(ws.Cells(r, di).Value))
                    If etiqueta = "_ifi" Then
                        If celda <> "" Then
                            If IsNumeric(Codigo(celda)) Then
                                det = det & "    <ifiEcuador>" & _
                                    Codigo(celda) & "</ifiEcuador>" & L
                            Else
                                det = det & "    <nombreIfiExterior>" & _
                                    Esc(celda) & "</nombreIfiExterior>" & L
                            End If
                        End If
                    ElseIf celda <> "" Then
                        Dim valor2 As String
                        If tipo = "cod" Then
                            valor2 = Codigo(celda)
                        Else
                            valor2 = celda
                        End If
                        det = det & "    <" & etiqueta & ">" & Esc(valor2) & _
                            "</" & etiqueta & ">" & L
                    End If
                End If
            Next i
            det = det & "</" & detalle & ">" & L
            cuerpo = cuerpo & det
        End If
        r = r + 1
    Loop

    total = Redondear(total)
    If cuerpo = "" Then
        ModuloXml = ""
    Else
        ModuloXml = "<" & contenedor & ">" & L & cuerpo & _
                    "</" & contenedor & ">" & L
    End If
End Function


Private Function PatrimonioAnio(anio As Long) As Double
    Dim ws As Worksheet: Set ws = ThisWorkbook.Sheets("Dinero")
    If ColumnaValorExacta(ws, anio) = 0 Then
        PatrimonioAnio = -1
        Exit Function
    End If

    Dim shMapa As Worksheet, ult As Long, mapa As Variant
    Set shMapa = ThisWorkbook.Sheets("_Mapa")
    ult = shMapa.Cells(shMapa.Rows.Count, 1).End(xlUp).Row
    mapa = shMapa.Range("A2:I" & ult).Value

    Dim visto As Object: Set visto = CreateObject("Scripting.Dictionary")
    Dim act As Double, pas As Double, i As Long
    For i = 1 To UBound(mapa, 1)
        Dim key As String: key = CStr(mapa(i, 1))
        If Not visto.Exists(key) Then
            visto.Add key, 1
            Dim t As Double: t = SumaModulo(CStr(mapa(i, 2)), anio)
            If CStr(mapa(i, 5)) = "activo" Then
                act = act + t
            Else
                pas = pas + t
            End If
        End If
    Next i
    PatrimonioAnio = Redondear(act - pas)
End Function


Private Function SumaModulo(hoja As String, anio As Long) As Double
    Dim ws As Worksheet: Set ws = ThisWorkbook.Sheets(hoja)
    Dim colVal As Long: colVal = ColumnaValor(ws, anio)
    Dim r As Long, t As Double
    r = 6
    Do While r < 5000
        If CStr(ws.Cells(r, 1).Value) = "TOTAL" Then Exit Do
        t = t + ValTexto(CStr(ws.Cells(r, colVal).Value))
        r = r + 1
    Loop
    SumaModulo = Redondear(t)
End Function


Private Function JustificacionXml() As String
    Const L As String = vbLf
    Dim ws As Worksheet, r As Long, s As String
    Set ws = ThisWorkbook.Sheets("Justificacion")
    For r = 1 To 300
        Dim et As String: et = CStr(ws.Cells(r, 2).Value)
        If InStr(et, " - ") > 0 Then
            Dim marca As String
            marca = LCase$(Trim$(CStr(ws.Cells(r, 5).Value)))
            If marca = "si" Or marca = "s" & Chr$(237) Or marca = "x" Then
                s = s & "<detalleJustificacion>" & L
                s = s & "    <justificVariacion>" & Codigo(et) & _
                    "</justificVariacion>" & L
                s = s & "</detalleJustificacion>" & L
            End If
        End If
    Next r
    JustificacionXml = s
End Function


Private Function DatoXml(etiqueta As String) As String
    Dim ws As Worksheet, r As Long
    Set ws = ThisWorkbook.Sheets("Datos del XML")
    For r = 1 To 300
        If Trim$(CStr(ws.Cells(r, 1).Value)) = etiqueta Then
            DatoXml = Trim$(CStr(ws.Cells(r, 2).Value))
            Exit Function
        End If
    Next r
    DatoXml = ""
End Function


Private Function ColumnaValor(ws As Worksheet, anio As Long) As Long
    ' columna "Valor <anio>"; si no existe, la del anio mas alto.
    Dim c As Long, h As String, mejor As Long, mejorAnio As Long
    For c = 1 To 80
        h = CStr(ws.Cells(5, c).Value)
        If Left$(h, 6) = "Valor " And IsNumeric(Mid$(h, 7)) Then
            If CLng(Mid$(h, 7)) = anio Then
                ColumnaValor = c
                Exit Function
            End If
            If CLng(Mid$(h, 7)) > mejorAnio Then
                mejorAnio = CLng(Mid$(h, 7))
                mejor = c
            End If
        End If
    Next c
    ColumnaValor = mejor
End Function


Private Function ColumnaValorExacta(ws As Worksheet, anio As Long) As Long
    Dim c As Long, h As String
    For c = 1 To 80
        h = CStr(ws.Cells(5, c).Value)
        If h = "Valor " & anio Then
            ColumnaValorExacta = c
            Exit Function
        End If
    Next c
    ColumnaValorExacta = 0
End Function


Private Function ClavesOrdenadas(d As Object) As String()
    Dim ks() As String, n As Long, i As Long, j As Long
    n = d.Count
    ReDim ks(0 To n - 1)
    Dim arrK As Variant: arrK = d.Keys
    For i = 0 To n - 1
        ks(i) = CStr(arrK(i))
    Next i
    For i = 0 To n - 2
        For j = 0 To n - 2 - i
            If CLng(d(ks(j))) > CLng(d(ks(j + 1))) Then
                Dim tmp As String
                tmp = ks(j): ks(j) = ks(j + 1): ks(j + 1) = tmp
            End If
        Next j
    Next i
    ClavesOrdenadas = ks
End Function


Private Function ValDic(d As Object, key As String) As Double
    If d.Exists(key) Then ValDic = CDbl(d(key)) Else ValDic = 0
End Function


Private Function Linea(etiqueta As String, valor As String) As String
    Linea = "    <" & etiqueta & ">" & Esc(valor) & "</" & etiqueta & ">" & vbLf
End Function


Private Function Codigo(s As String) As String
    Dim p As Long
    p = InStr(s, " - ")
    If p > 0 Then
        Codigo = Trim$(Left$(s, p - 1))
    Else
        Codigo = Trim$(s)
    End If
End Function


Private Function Esc(s As String) As String
    s = Replace(s, "&", "&amp;")
    s = Replace(s, "<", "&lt;")
    s = Replace(s, ">", "&gt;")
    Esc = s
End Function


Private Function Num2(v As Double) As String
    Dim s As String
    s = Format$(Redondear(v), "0.00")
    s = Replace(s, ",", ".")
    Num2 = s
End Function


Private Function Redondear(v As Double) As Double
    Redondear = Int(v * 100 + IIf(v >= 0, 0.5, -0.5)) / 100
End Function


Private Function ValTexto(v As Variant) As Double
    Dim s As String
    s = Trim$(CStr(v))
    If s = "" Then
        ValTexto = 0
        Exit Function
    End If
    s = Replace(s, "$", "")
    s = Replace(s, " ", "")
    If IsNumeric(s) Then
        ValTexto = CDbl(s)
    Else
        ValTexto = 0
    End If
End Function


Private Sub GuardarTexto(ruta As String, texto As String)
    Dim st As Object
    Set st = CreateObject("ADODB.Stream")
    st.Type = 2                 ' texto
    st.Charset = "iso-8859-1"
    st.Open
    st.WriteText texto
    st.SaveToFile ruta, 2       ' sobrescribe si existe
    st.Close
End Sub
