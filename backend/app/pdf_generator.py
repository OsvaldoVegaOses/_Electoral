import io
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY

def build_pdf_buffer(story):
    """Compila el story en un buffer en memoria y lo retorna"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=40,
        rightMargin=40,
        topMargin=40,
        bottomMargin=40
    )
    doc.build(story)
    buffer.seek(0)
    return buffer

def get_theogen_styles():
    styles = getSampleStyleSheet()
    
    # Colores corporativos TheoGen
    c_primary = colors.HexColor("#0d233a")
    c_secondary = colors.HexColor("#1e40af")
    c_text = colors.HexColor("#1e293b")
    c_muted = colors.HexColor("#64748b")
    
    title_style = ParagraphStyle(
        'TheoGenTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=c_primary,
        alignment=TA_CENTER
    )
    
    subtitle_style = ParagraphStyle(
        'TheoGenSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=10,
        leading=14,
        textColor=c_secondary,
        alignment=TA_CENTER
    )
    
    doc_type_style = ParagraphStyle(
        'TheoGenDocType',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=14,
        leading=18,
        textColor=c_primary,
        alignment=TA_CENTER,
        spaceAfter=15
    )
    
    section_style = ParagraphStyle(
        'TheoGenSection',
        parent=styles['Heading3'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=16,
        textColor=c_secondary,
        spaceBefore=12,
        spaceAfter=6
    )
    
    body_style = ParagraphStyle(
        'TheoGenBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=15,
        textColor=c_text,
        alignment=TA_JUSTIFY
    )
    
    table_cell = ParagraphStyle(
        'TheoGenCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=c_text
    )
    
    table_cell_bold = ParagraphStyle(
        'TheoGenCellBold',
        parent=table_cell,
        fontName='Helvetica-Bold'
    )
    
    table_header = ParagraphStyle(
        'TheoGenHeaderCell',
        parent=table_cell,
        fontName='Helvetica-Bold',
        textColor=colors.white,
        alignment=TA_CENTER
    )
    
    sig_label = ParagraphStyle(
        'TheoGenSig',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=11,
        textColor=c_muted,
        alignment=TA_CENTER
    )

    return {
        "title": title_style,
        "subtitle": subtitle_style,
        "doc_type": doc_type_style,
        "section": section_style,
        "body": body_style,
        "cell": table_cell,
        "cell_bold": table_cell_bold,
        "header": table_header,
        "sig": sig_label,
        "c_primary": c_primary,
        "c_secondary": c_secondary
    }

def generate_acta_apertura_pdf(election, school, committee_members, total_voters: int):
    """Genera el PDF oficial del Acta de Apertura de la Elección"""
    st = get_theogen_styles()
    story = []
    
    # Encabezado TheoGen
    story.append(Paragraph("THEOGEN ELECTORAL", st["title"]))
    story.append(Paragraph("Participación transparente y verificable • Plataforma de Gestión Electoral", st["subtitle"]))
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=2, color=st["c_secondary"], spaceBefore=5, spaceAfter=15))
    
    # Título del Acta
    story.append(Paragraph("ACTA OFICIAL DE APERTURA DE MESA Y PROCESO ELECTORAL", st["doc_type"]))
    
    # Párrafo introductorio
    fecha_str = election.fecha_inicio.strftime("%d de %B de %Y a las %H:%M hrs") if election.fecha_inicio else datetime.utcnow().strftime("%d/%m/%Y %H:%M hrs")
    intro_text = (
        f"En la comuna de <b>{school.comuna or 'Santiago'}</b>, con fecha <b>{fecha_str}</b>, se reúne la Comisión Electoral "
        f"designada en dependencias de <b>{school.nombre}</b> (RBD: {school.rbd or 'S/N'}), para formalizar y certificar "
        f"la apertura oficial del proceso de votación electrónica denominado: <b>\"{election.nombre}\"</b>."
    )
    story.append(Paragraph(intro_text, st["body"]))
    story.append(Spacer(1, 12))
    
    # Datos del Proceso
    story.append(Paragraph("1. INFORMACIÓN GENERAL DEL PROCESO", st["section"]))
    info_data = [
        [Paragraph("<b>Entidad Organizadora:</b>", st["cell"]), Paragraph(school.nombre, st["cell"])],
        [Paragraph("<b>RBD / Identificador:</b>", st["cell"]), Paragraph(school.rbd or "No especificado", st["cell"])],
        [Paragraph("<b>Tipo de Elección:</b>", st["cell"]), Paragraph(election.tipo_votacion, st["cell"])],
        [Paragraph("<b>Regla de Votación:</b>", st["cell"]), Paragraph(f"<b>{election.regla_votacion}</b>", st["cell"])],
        [Paragraph("<b>Padrón Habilitado Total:</b>", st["cell"]), Paragraph(f"<b>{total_voters} electores</b> registrados con credenciales generadas", st["cell"])],
        [Paragraph("<b>Fecha y Hora Apertura:</b>", st["cell"]), Paragraph(fecha_str, st["cell"])],
        [Paragraph("<b>Estado del Proceso:</b>", st["cell"]), Paragraph(f"<font color='#047857'><b>{election.estado.upper()}</b></font>", st["cell"])]
    ]
    info_table = Table(info_data, colWidths=[160, 370])
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 14))
    
    # Declaración de Integridad de la Urna
    story.append(Paragraph("2. CONSTATACIÓN DE URNA ELECTRÓNICA Y CREDENCIALES", st["section"]))
    constata_text = (
        "La Comisión Electoral certifica que la urna digital se encuentra en estado inicial con <b>cero (0) votos emitidos</b>. "
        "Las credenciales únicas criptográficas (Tokens UUID) han sido emitidas bajo estándares de aleatoriedad garantizando "
        "un voto único e intransferible conforme a la regla electoral vigente."
    )
    story.append(Paragraph(constata_text, st["body"]))
    story.append(Spacer(1, 14))
    
    # Miembros de la Comisión Electoral
    story.append(Paragraph("3. MIEMBROS DE LA COMISIÓN ELECTORAL SUPERVISORA", st["section"]))
    com_headers = [
        Paragraph("<b>Nombre Completo</b>", st["header"]),
        Paragraph("<b>RUT</b>", st["header"]),
        Paragraph("<b>Cargo</b>", st["header"]),
        Paragraph("<b>Correo Contacto</b>", st["header"])
    ]
    com_rows = [com_headers]
    for m in committee_members:
        com_rows.append([
            Paragraph(m.nombre, st["cell"]),
            Paragraph(m.rut, st["cell"]),
            Paragraph(f"<b>{m.cargo}</b>", st["cell"]),
            Paragraph(m.correo or "-", st["cell"])
        ])
    if not committee_members:
        com_rows.append([Paragraph("No se registraron miembros de comisión", st["cell"]), Paragraph("-", st["cell"]), Paragraph("-", st["cell"]), Paragraph("-", st["cell"])])
        
    com_table = Table(com_rows, colWidths=[170, 90, 110, 160])
    com_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), st["c_primary"]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(com_table)
    story.append(Spacer(1, 24))
    
    # Firmas
    story.append(Paragraph("4. CONSTANCIA Y FIRMAS DE APERTURA", st["section"]))
    story.append(Spacer(1, 15))
    
    sig_data = []
    # Generar hasta 3 columnas de firmas
    if committee_members:
        row_lines = []
        row_names = []
        for m in committee_members[:3]:
            row_lines.append(Paragraph("____________________________", st["sig"]))
            row_names.append(Paragraph(f"<b>{m.nombre}</b><br/>{m.cargo}<br/>RUT: {m.rut}", st["sig"]))
        sig_data = [row_lines, row_names]
    else:
        sig_data = [
            [Paragraph("____________________________", st["sig"]), Paragraph("____________________________", st["sig"])],
            [Paragraph("<b>Presidente(a) Comisión</b>", st["sig"]), Paragraph("<b>Secretario(a) Comisión</b>", st["sig"])]
        ]
        
    sig_table = Table(sig_data, colWidths=[530 / len(sig_data[0])] * len(sig_data[0]))
    sig_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(KeepTogether(sig_table))
    
    return build_pdf_buffer(story)

def generate_acta_cierre_pdf(election, school, committee_members, results: dict, total_voters: int):
    """Genera el PDF oficial del Acta de Cierre y Escrutinio de la Elección"""
    st = get_theogen_styles()
    story = []
    
    # Encabezado TheoGen
    story.append(Paragraph("THEOGEN ELECTORAL", st["title"]))
    story.append(Paragraph("Participación transparente y verificable • Plataforma de Gestión Electoral", st["subtitle"]))
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=2, color=st["c_secondary"], spaceBefore=5, spaceAfter=15))
    
    # Título del Acta
    story.append(Paragraph("ACTA DEFINITIVA DE CIERRE Y ESCRUTINIO ELECTORAL", st["doc_type"]))
    
    fecha_cierre_str = election.fecha_fin.strftime("%d de %B de %Y a las %H:%M hrs") if election.fecha_fin else datetime.utcnow().strftime("%d/%m/%Y %H:%M hrs")
    intro_text = (
        f"En la comuna de <b>{school.comuna or 'Santiago'}</b>, siendo las <b>{fecha_cierre_str}</b>, se declara formalmente "
        f"<b>CERRADO</b> el proceso de votación electrónica correspondiente a: <b>\"{election.nombre}\"</b> de la institución "
        f"<b>{school.nombre}</b>. A continuación se certifica el escrutinio general y sus resultados vinculantes."
    )
    story.append(Paragraph(intro_text, st["body"]))
    story.append(Spacer(1, 12))
    
    # Resumen de Participación
    story.append(Paragraph("1. RESUMEN GENERAL DE PARTICIPACIÓN", st["section"]))
    part_rate = results.get("participacion_porcentaje", 0.0)
    total_votos = results.get("total_votos", 0)
    
    summary_data = [
        [Paragraph("<b>Padrón Electoral Total:</b>", st["cell"]), Paragraph(f"{total_voters} electores habilitados", st["cell"])],
        [Paragraph("<b>Total Sufragios Emitidos:</b>", st["cell"]), Paragraph(f"<b>{total_votos} votos</b>", st["cell"])],
        [Paragraph("<b>Porcentaje de Participación:</b>", st["cell"]), Paragraph(f"<b><font color='#1e40af'>{part_rate:.1f}%</font></b>", st["cell"])],
        [Paragraph("<b>Votos No Emitidos (Abstención):</b>", st["cell"]), Paragraph(f"{total_voters - total_votos} electores", st["cell"])],
        [Paragraph("<b>Regla Aplicada:</b>", st["cell"]), Paragraph(election.regla_votacion, st["cell"])]
    ]
    summary_table = Table(summary_data, colWidths=[170, 360])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 14))
    
    # Tabla de Resultados y Escrutinio
    story.append(Paragraph("2. ESCRUTINIO DETALLADO POR CANDIDATO / LISTA", st["section"]))
    res_headers = [
        Paragraph("<b>Candidato / Lista</b>", st["header"]),
        Paragraph("<b>Cargo Postulado</b>", st["header"]),
        Paragraph("<b>Votos Obtenidos</b>", st["header"]),
        Paragraph("<b>% Válidos</b>", st["header"])
    ]
    res_rows = [res_headers]
    for c in results.get("candidatos", []):
        highlight = "<b>" if c.get("votos", 0) > 0 else ""
        end_highlight = "</b>" if highlight else ""
        res_rows.append([
            Paragraph(f"{highlight}{c.get('nombre')}{end_highlight}", st["cell"]),
            Paragraph(c.get("cargo") or "-", st["cell"]),
            Paragraph(f"<para align='center'>{highlight}{c.get('votos', 0)}{end_highlight}</para>", st["cell"]),
            Paragraph(f"<para align='center'>{highlight}{c.get('porcentaje', 0.0):.1f}%{end_highlight}</para>", st["cell"])
        ])
        
    res_table = Table(res_rows, colWidths=[200, 150, 90, 90])
    res_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), st["c_primary"]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(res_table)
    story.append(Spacer(1, 14))
    
    # Proclamación del Ganador
    ganador = results.get("ganador")
    if ganador and ganador.get("votos", 0) > 0:
        story.append(Paragraph("3. PROCLAMACIÓN OFICIAL", st["section"]))
        proclama_box = [
            [Paragraph(
                f"<font size='11'><b>OPCIÓN GANADORA DECLARADA ELECTA:</b></font><br/>"
                f"<font size='13' color='#0d233a'><b>{ganador.get('nombre')}</b></font><br/>"
                f"Cargo: <b>{ganador.get('cargo') or 'Directiva Electa'}</b> • Con un total de <b>{ganador.get('votos')} votos ({ganador.get('porcentaje', 0.0):.1f}%)</b>",
                st["body"]
            )]
        ]
        p_table = Table(proclama_box, colWidths=[530])
        p_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#ecfdf5")),
            ('BOX', (0, 0), (-1, -1), 1.5, colors.HexColor("#059669")),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('LEFTPADDING', (0, 0), (-1, -1), 14),
            ('RIGHTPADDING', (0, 0), (-1, -1), 14),
        ]))
        story.append(p_table)
        story.append(Spacer(1, 16))
        
    # Firmas de Cierre
    story.append(Paragraph("4. CERTIFICACIÓN Y FIRMAS DE LA COMISIÓN ELECTORAL", st["section"]))
    story.append(Paragraph(
        "Los abajo firmantes, en su calidad de miembros acreditados de la Comisión Electoral, declaran bajo juramento "
        "la total conformidad del proceso, la inexistencia de reclamos no resueltos y la plena validez de los resultados expuestos.",
        st["body"]
    ))
    story.append(Spacer(1, 20))
    
    if committee_members:
        row_lines = []
        row_names = []
        for m in committee_members[:3]:
            row_lines.append(Paragraph("____________________________", st["sig"]))
            row_names.append(Paragraph(f"<b>{m.nombre}</b><br/>{m.cargo}<br/>RUT: {m.rut}", st["sig"]))
        sig_data = [row_lines, row_names]
    else:
        sig_data = [
            [Paragraph("____________________________", st["sig"]), Paragraph("____________________________", st["sig"])],
            [Paragraph("<b>Presidente(a) Comisión</b>", st["sig"]), Paragraph("<b>Secretario(a) Comisión</b>", st["sig"])]
        ]
        
    sig_table = Table(sig_data, colWidths=[530 / len(sig_data[0])] * len(sig_data[0]))
    sig_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(KeepTogether(sig_table))
    
    return build_pdf_buffer(story)
