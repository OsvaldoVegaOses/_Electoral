"""Human-readable export of verified aggregate evidence; no claims of legal signatures."""
from io import BytesIO
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

def pdf_record(record):
    output=BytesIO()
    styles=getSampleStyleSheet()
    story=[Paragraph('Expediente electoral Belenios',styles['Title']),Spacer(1,12)]
    for label,key in [('Urna','uuid'),('Política','policy'),('Personas','total_people'),('Unidades habilitadas','enabled_units'),
                      ('Boletas computadas','counted_ballots'),('Archivo SHA-256','archive_sha256'),
                      ('Evento final','final_event_hash'),('Resultado','result_object_hash'),('Anclaje','anchor_reference')]:
        story.append(Paragraph(escape(label+': '+str(record.get(key,''))),styles['BodyText']))
    story.append(Spacer(1,12))
    rows=[[Paragraph('Opción',styles['BodyText']),'Votos']]
    rows += [[Paragraph(escape(str(item['label'])),styles['BodyText']),str(item['votes'])] for item in record['options']]
    table=Table(rows,colWidths=[380,80],repeatRows=1)
    table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e7eef6')),('GRID',(0,0),(-1,-1),.5,colors.grey)]))
    story.extend([table,Spacer(1,12),Paragraph('Documento de evidencia agregada. Blanco/nulo no modelados. '
        'Firmas, quórum y aceptación institucional deben constar en el expediente aprobado. '
        'La verificación técnica no acredita por sí sola validez jurídica ni custodia independiente.',styles['BodyText'])])
    SimpleDocTemplate(output,title='Expediente electoral Belenios').build(story)
    output.seek(0)
    return output
