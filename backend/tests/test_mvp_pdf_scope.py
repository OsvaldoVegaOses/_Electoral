from datetime import datetime, timezone
from types import SimpleNamespace
from reportlab.platypus import Paragraph, Table, KeepTogether
import pytest
from app import pdf_generator as pdf


def fixtures():
    election=SimpleNamespace(nombre="DEMO ensayo",tipo_votacion="Ensayo",regla_votacion="Un voto por familia",
        estado="Cerrada",fecha_inicio=datetime(2026,11,1,tzinfo=timezone.utc),
        fecha_fin=datetime(2099,1,1,tzinfo=timezone.utc),fecha_cierre_efectiva=datetime(2026,11,2,10,15,tzinfo=timezone.utc))
    school=SimpleNamespace(nombre="DEMO institución",comuna="Santiago",rbd="synthetic")
    result={"total_votos":1,"participacion_porcentaje":100.,"candidatos":[
        {"nombre":"Opción A","cargo":"Ensayo","votos":1,"porcentaje":100.,"es_blanco":False,"es_nulo":False}]}
    return election,school,result


def paragraphs(value):
    if isinstance(value,Paragraph):return [value.getPlainText()]
    if isinstance(value,Table):return paragraphs(value._cellvalues)
    if isinstance(value,KeepTogether):return paragraphs(value._content)
    if isinstance(value,(list,tuple)):return [text for child in value for text in paragraphs(child)]
    return []


@pytest.mark.parametrize("opening",[True,False])
def test_pdf_is_technical_without_inventing_authorities_or_validity(monkeypatch,opening):
    election,school,result=fixtures();seen=[]
    original=pdf.build_pdf_buffer
    def capture(story):
        seen.extend(paragraphs(story));return original(story)
    monkeypatch.setattr(pdf,"build_pdf_buffer",capture)
    output=(pdf.generate_acta_apertura_pdf(election,school,[],1) if opening
            else pdf.generate_acta_cierre_pdf(election,school,[],result,1))
    text="\n".join(seen)
    assert output.read(5)==b"%PDF-"
    assert "No acredita secreto criptográfico" in text
    assert "No hay revisores registrados" in text
    for claim in ("resultados vinculantes","PROCLAMACIÓN OFICIAL","bajo juramento","DECLARADA ELECTA","Presidente(a) Comisión"):
        assert claim not in text
    if not opening:
        assert "02/11/2026 10:15 UTC" in text and "2099" not in text


def test_pdf_treats_embedded_html_as_text_and_omits_reviewers_contacts(monkeypatch):
    election,school,result=fixtures();seen=[]
    payload='<img src="http://127.0.0.1:9/private"/>'
    election.nombre=school.nombre=result["candidatos"][0]["nombre"]=payload
    reviewer=SimpleNamespace(nombre=payload,cargo="Revisión",rut="90000001",correo="private@example.test")
    original=pdf.build_pdf_buffer
    def capture(story):seen.extend(paragraphs(story));return original(story)
    monkeypatch.setattr(pdf,"build_pdf_buffer",capture)
    assert pdf.generate_acta_cierre_pdf(election,school,[reviewer],result,1).read(5)==b"%PDF-"
    text="\n".join(seen)
    assert payload in text and "private@example.test" not in text and "90000001" not in text
