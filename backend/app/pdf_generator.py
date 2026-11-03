import io
from datetime import datetime, timezone
from html import escape
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
    def footer(canvas, document):
        canvas.saveState()
        canvas.setFont('Helvetica', 7)
        canvas.setFillColor(colors.HexColor('#64748b'))
        canvas.drawString(40, 22, f'Registro técnico MVP - Página {document.page}')
        canvas.restoreState()
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
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


def _text(value, default="-"):
    return escape(str(default if value is None or value == "" else value))


def _date(value):
    if value is None:
        return "No registrada"
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")


def _header(st, title):
    return [Paragraph("THEOGEN ELECTORAL", st["title"]),
            Paragraph("Registro de participación - Plataforma de gestión electoral", st["subtitle"]),
            HRFlowable(width="100%", thickness=2, color=st["c_secondary"], spaceBefore=8, spaceAfter=12),
            Paragraph(title, st["doc_type"]),
            Paragraph("<b>Registro técnico del MVP.</b> No acredita secreto criptográfico del voto, "
                      "auditoría independiente, proclamación de cargos ni validez institucional. "
                      "La revisión y aprobación corresponden a las autoridades competentes.", st["body"]),
            Spacer(1, 10)]


def _table(rows, widths, st, header=False):
    table = Table(rows, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT")
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), st["c_primary"] if header else colors.HexColor("#f8fafc")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    return table


def _reviewers(committee_members, st, number):
    content = [Paragraph(f"{number}. REVISIÓN DEL REGISTRO", st["section"])]
    if committee_members:
        content.append(Paragraph("Personas registradas para revisión; su inclusión no acredita firma, "
                                 "ratificación de cargos ni auditoría independiente.", st["body"]))
        rows = [[Paragraph(_text(m.nombre), st["cell"]), Paragraph(_text(m.cargo), st["cell"])]
                for m in committee_members]
        content.append(_table(rows, [300, 230], st))
    else:
        content.append(Paragraph("No hay revisores registrados. Este documento no contiene firmas "
                                 "ni designa autoridades.", st["body"]))
    return KeepTogether(content)


def generate_acta_apertura_pdf(election, school, committee_members, total_voters: int):
    """MVP operational record; does not certify electoral or institutional validity."""
    st = get_theogen_styles()
    story = _header(st, "REGISTRO TÉCNICO DE APERTURA - MVP")
    story.append(Paragraph(f"Proceso: <b>{_text(election.nombre)}</b><br/>"
                           f"Institución: {_text(school.nombre)}", st["body"]))
    story.append(Paragraph("1. CONFIGURACIÓN REGISTRADA", st["section"]))
    fields = [("Tipo", election.tipo_votacion), ("Regla", election.regla_votacion),
              ("Personas en el padrón", total_voters), ("Inicio registrado", _date(election.fecha_inicio)),
              ("Estado actual", election.estado)]
    rows = [[Paragraph(_text(label), st["cell_bold"]), Paragraph(_text(value), st["cell"])]
            for label, value in fields]
    story.append(_table(rows, [180, 350], st))
    story.append(Spacer(1, 12))
    story.append(_reviewers(committee_members, st, 2))
    return build_pdf_buffer(story)


def generate_acta_cierre_pdf(election, school, committee_members, results: dict, total_voters: int):
    """Aggregate closing record; no oath, legal proclamation or inferred signature."""
    st = get_theogen_styles()
    story = _header(st, "REGISTRO TÉCNICO DE CIERRE Y RESULTADOS - MVP")
    closed_at = getattr(election, "fecha_cierre_efectiva", None)
    story.append(Paragraph(f"Proceso: <b>{_text(election.nombre)}</b><br/>"
                           f"Institución: {_text(school.nombre)}<br/>"
                           f"Cierre efectivo registrado: {_date(closed_at)}", st["body"]))
    story.append(Paragraph("1. PARTICIPACIÓN REGISTRADA", st["section"]))
    total_votes = results.get("total_votos", 0)
    fields = [("Unidades habilitadas", total_voters), ("Sufragios registrados", total_votes),
              ("Participación", f"{results.get('participacion_porcentaje', 0):.1f}%"),
              ("Unidades sin voto", total_voters - total_votes), ("Regla aplicada", election.regla_votacion)]
    rows = [[Paragraph(_text(label), st["cell_bold"]), Paragraph(_text(value), st["cell"])]
            for label, value in fields]
    story.append(_table(rows, [180, 350], st))
    story.append(Paragraph("2. CÓMPUTO POR OPCIÓN", st["section"]))
    headers = ["Opción", "Descripción de cargo", "Votos", "% del total"]
    rows = [[Paragraph(_text(label), st["header"]) for label in headers]]
    candidates = results.get("candidatos", [])
    for candidate in candidates:
        rows.append([Paragraph(_text(candidate.get("nombre")), st["cell"]),
                     Paragraph(_text(candidate.get("cargo")), st["cell"]),
                     Paragraph(_text(candidate.get("votos", 0)), st["cell"]),
                     Paragraph(f"{candidate.get('porcentaje', 0):.1f}%", st["cell"])])
    story.append(_table(rows, [205, 160, 65, 100], st, header=True))
    regular = [c for c in candidates if not c.get("es_blanco") and not c.get("es_nulo")]
    maximum = max((c.get("votos", 0) for c in regular), default=0)
    leaders = [c for c in regular if c.get("votos", 0) == maximum] if maximum else []
    if leaders:
        label = "Mayor conteo registrado" if len(leaders) == 1 else "Empate en el mayor conteo"
        names = "; ".join(_text(c.get("nombre")) for c in leaders)
        story.append(Paragraph("3. RESUMEN DEL CÓMPUTO", st["section"]))
        story.append(Paragraph(f"{label}: <b>{names}</b>. Este registro no asigna cargos "
                               "ni resuelve reglas de desempate.", st["body"]))
    story.append(Spacer(1, 8))
    story.append(_reviewers(committee_members, st, 4))
    return build_pdf_buffer(story)
