from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timezone

from app.database import get_db
from app.models import Election, School, ElectoralCommittee, Voter, Candidate, Vote, User
from app.schemas import ScrutinyResponse, CandidateResult, DashboardStatsResponse, ElectionResponse
from app.pdf_generator import generate_acta_apertura_pdf, generate_acta_cierre_pdf
from app.auth import get_current_user, log_audit

router = APIRouter(prefix="/reports", tags=["Informes, Escrutinio y Actas PDF"])

@router.get("/election/{election_id}/scrutiny", response_model=ScrutinyResponse)
def get_election_scrutiny(
    election_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),  # CRIT-03
):
    """
    Módulo 7: Escrutinio oficial.
    Calcula votos por candidato, votos nulos, votos blancos, porcentaje de participación y proclamación de ganador.
    """
    election = db.query(Election).filter(Election.id == election_id).first()
    if not election:
        raise HTTPException(status_code=404, detail="Elección no encontrada")

    total_padron = db.query(Voter).filter(Voter.election_id == election_id).count()
    total_votos = db.query(Vote).filter(Vote.election_id == election_id).count()
    
    part_rate = (total_votos / total_padron * 100.0) if total_padron > 0 else 0.0

    candidates = db.query(Candidate).filter(Candidate.election_id == election_id).order_by(Candidate.orden.asc()).all()
    
    candidates_results = []
    votos_blancos = 0
    votos_nulos = 0
    
    highest_votes = -1
    ganador_candidato = None

    for c in candidates:
        v_count = db.query(Vote).filter(Vote.candidate_id == c.id).count()
        v_pct = (v_count / total_votos * 100.0) if total_votos > 0 else 0.0
        
        if c.es_blanco:
            votos_blancos += v_count
        elif c.es_nulo:
            votos_nulos += v_count
        else:
            if v_count > highest_votes:
                highest_votes = v_count
                ganador_candidato = {
                    "candidate_id": c.id,
                    "nombre": c.nombre,
                    "cargo": c.cargo,
                    "descripcion": c.descripcion,
                    "votos": v_count,
                    "porcentaje": v_pct,
                    "es_blanco": False,
                    "es_nulo": False
                }

        candidates_results.append(CandidateResult(
            candidate_id=c.id,
            nombre=c.nombre,
            cargo=c.cargo,
            descripcion=c.descripcion,
            votos=v_count,
            porcentaje=round(v_pct, 1),
            es_blanco=c.es_blanco,
            es_nulo=c.es_nulo
        ))

    return ScrutinyResponse(
        election_id=election.id,
        election_nombre=election.nombre,
        estado=election.estado,
        total_padron=total_padron,
        total_votos=total_votos,
        participacion_porcentaje=round(part_rate, 1),
        votos_pendientes=max(0, total_padron - total_votos),
        votos_blancos=votos_blancos,
        votos_nulos=votos_nulos,
        candidatos=candidates_results,
        ganador=CandidateResult(**ganador_candidato) if ganador_candidato and highest_votes > 0 else None,
        fecha_cierre=election.fecha_fin
    )

@router.get("/election/{election_id}/acta-apertura/pdf")
def download_acta_apertura_pdf(
    election_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),  # CRIT-03
):
    """
    Módulo 8: Generación y descarga directa del PDF del Acta de Apertura de la Elección.
    """
    election = db.query(Election).filter(Election.id == election_id).first()
    if not election:
        raise HTTPException(status_code=404, detail="Elección no encontrada")

    school = election.school or School(nombre="Institución Educativa", rbd="S/N", comuna="Santiago")
    committee = election.committee_members or []
    total_voters = db.query(Voter).filter(Voter.election_id == election_id).count()

    pdf_buffer = generate_acta_apertura_pdf(election, school, committee, total_voters)

    log_audit(
        db,
        accion="Descargó acta",
        detalle=f"Se descargó Acta de Apertura en PDF para '{election.nombre}'",
        usuario=current_user.email
    )

    clean_name = election.nombre.replace(" ", "_").replace("/", "-")[:30]
    filename = f"Acta_Apertura_{clean_name}_{datetime.now(timezone.utc).strftime('%Y%m%d')}.pdf"

    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

@router.get("/election/{election_id}/acta-cierre/pdf")
def download_acta_cierre_pdf(
    election_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),  # CRIT-03
):
    """
    Módulo 8: Generación y descarga directa del PDF del Acta de Cierre y Escrutinio Definitivo.
    """
    election = db.query(Election).filter(Election.id == election_id).first()
    if not election:
        raise HTTPException(status_code=404, detail="Elección no encontrada")

    school = election.school or School(nombre="Institución Educativa", rbd="S/N", comuna="Santiago")
    committee = election.committee_members or []
    total_voters = db.query(Voter).filter(Voter.election_id == election_id).count()

    scrutiny = get_election_scrutiny(election_id, db, current_user)
    results_dict = scrutiny.model_dump()

    pdf_buffer = generate_acta_cierre_pdf(election, school, committee, results_dict, total_voters)

    log_audit(
        db,
        accion="Descargó acta",
        detalle=f"Se descargó Acta de Cierre en PDF para '{election.nombre}'",
        usuario=current_user.email
    )

    clean_name = election.nombre.replace(" ", "_").replace("/", "-")[:30]
    filename = f"Acta_Cierre_{clean_name}_{datetime.now(timezone.utc).strftime('%Y%m%d')}.pdf"

    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

@router.get("/dashboard-stats", response_model=DashboardStatsResponse)
def get_dashboard_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),  # CRIT-03
):
    """
    Módulo 6: Estadísticas generales para el panel de control.
    """
    total_elecciones = db.query(Election).count()
    elecciones_activas = db.query(Election).filter(Election.estado == "Abierta").count()
    total_padron = db.query(Voter).count()
    total_votos = db.query(Vote).count()

    participacion_global = (total_votos / total_padron * 100.0) if total_padron > 0 else 0.0

    ultimas = db.query(Election).order_by(Election.fecha_creacion.desc()).limit(5).all()

    return DashboardStatsResponse(
        total_elecciones=total_elecciones,
        elecciones_activas=elecciones_activas,
        total_padron=total_padron,
        total_votos_emitidos=total_votos,
        participacion_global=round(participacion_global, 1),
        ultimas_elecciones=ultimas
    )
