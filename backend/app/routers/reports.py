import re
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from typing import List
from datetime import datetime, timezone

from app.database import get_db
from app.models import Election, School, ElectoralCommittee, Voter, Candidate, Vote, User
from app.schemas import ScrutinyResponse, CandidateResult, DashboardStatsResponse, ElectionResponse
from app.pdf_generator import generate_acta_apertura_pdf, generate_acta_cierre_pdf
from app.auth import (
    get_current_user, log_audit, check_election_access, is_superadmin,
    ROLE_RESPONSABLE, ROLE_COMISION
)

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
    PROTEGIDO: Solo accesible cuando la elección se encuentra en estado 'Cerrada' o 'Finalizada' (A2 - P0)
    y pertenece al ámbito autorizado del usuario (A3 - P0).
    """
    election = db.query(Election).filter(Election.id == election_id).first()
    if not election:
        raise HTTPException(status_code=404, detail="Elección no encontrada")

    check_election_access(current_user, election, write=False)

    # A2: Bloquear escrutinio en elecciones abiertas o borradores
    if election.estado not in ["Cerrada", "Finalizada"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"El escrutinio detallado y resultados no están disponibles mientras la elección "
                f"se encuentre en estado '{election.estado}'. Solo se publican una vez cerrada la elección."
            )
        )


    # Denominador de participación: según regla electoral
    if election.regla_votacion == "Un voto por familia":
        familias_count = db.query(func.count(func.distinct(Voter.familia_id))).filter(
            Voter.election_id == election_id,
            Voter.familia_id.isnot(None),
            Voter.familia_id != ""
        ).scalar() or 0
        sin_familia_count = db.query(Voter).filter(
            Voter.election_id == election_id,
            or_(Voter.familia_id.is_(None), Voter.familia_id == "")
        ).count()
        total_padron = familias_count + sin_familia_count
    else:
        total_padron = db.query(Voter).filter(Voter.election_id == election_id).count()

    total_votos = db.query(Vote).filter(Vote.election_id == election_id).count()
    
    part_rate = (total_votos / total_padron * 100.0) if total_padron > 0 else 0.0

    candidates = db.query(Candidate).filter(Candidate.election_id == election_id).order_by(Candidate.orden.asc()).all()
    
    candidates_results = []
    votos_blancos = 0
    votos_nulos = 0
    
    regular_candidates = []

    for c in candidates:
        v_count = db.query(Vote).filter(Vote.candidate_id == c.id).count()
        v_pct = (v_count / total_votos * 100.0) if total_votos > 0 else 0.0
        
        if c.es_blanco:
            votos_blancos += v_count
        elif c.es_nulo:
            votos_nulos += v_count
        else:
            regular_candidates.append({
                "candidate_id": c.id,
                "nombre": c.nombre,
                "cargo": c.cargo,
                "descripcion": c.descripcion,
                "votos": v_count,
                "porcentaje": round(v_pct, 1),
                "es_blanco": False,
                "es_nulo": False
            })

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

    # Determinación rigurosa de ganador (sin proclamación ficticia ante empates o cero votos)
    ganador_candidato = None
    if total_votos > 0 and regular_candidates:
        regular_candidates.sort(key=lambda x: x["votos"], reverse=True)
        top_cand = regular_candidates[0]
        # Verificar si hay empate en el primer lugar
        if top_cand["votos"] > 0:
            if len(regular_candidates) > 1 and regular_candidates[1]["votos"] == top_cand["votos"]:
                # Empate técnico: no proclamar ganador unívoco
                ganador_candidato = None
            else:
                ganador_candidato = top_cand

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
        ganador=CandidateResult(**ganador_candidato) if ganador_candidato else None,
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
    Verificado contra IDOR (A3 - P0).
    """
    election = db.query(Election).filter(Election.id == election_id).first()
    if not election:
        raise HTTPException(status_code=404, detail="Elección no encontrada")

    check_election_access(current_user, election, write=False)

    school = election.school or School(nombre="Institución Educativa", rbd="S/N", comuna="Santiago")
    committee = election.committee_members or []
    total_voters = db.query(Voter).filter(Voter.election_id == election_id).count()

    pdf_buffer = generate_acta_apertura_pdf(election, school, committee, total_voters)

    log_audit(
        db,
        accion="Descargó acta",
        detalle=f"Se descargó Acta de Apertura en PDF para '{election.nombre}'",
        usuario=current_user.email,
        school_id=election.school_id
    )

    clean_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', election.nombre)[:30]
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
    PROTEGIDO: Solo disponible cuando la elección se encuentra en estado 'Cerrada' o 'Finalizada' (A2 - P0)
    y pertenece al ámbito autorizado del usuario (A3 - P0).
    """
    election = db.query(Election).filter(Election.id == election_id).first()
    if not election:
        raise HTTPException(status_code=404, detail="Elección no encontrada")

    check_election_access(current_user, election, write=False)

    if election.estado not in ["Cerrada", "Finalizada"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"El Acta de Cierre y Escrutinio Definitivo solo puede generarse cuando la elección "
                f"esté Cerrada o Finalizada (Estado actual: '{election.estado}')."
            )
        )

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
        usuario=current_user.email,
        school_id=election.school_id
    )

    clean_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', election.nombre)[:30]
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
    Módulo 6: Estadísticas para el panel de control, restringidas por ámbito institucional (A3 - P0).
    """
    if is_superadmin(current_user):
        elections_query = db.query(Election)
        voters_query = db.query(Voter)
        votes_query = db.query(Vote)
    elif current_user.rol == ROLE_RESPONSABLE and current_user.school_id:
        elections_query = db.query(Election).filter(Election.school_id == current_user.school_id)
        election_ids = [e.id for e in elections_query.all()]
        voters_query = db.query(Voter).filter(Voter.election_id.in_(election_ids)) if election_ids else db.query(Voter).filter(False)
        votes_query = db.query(Vote).filter(Vote.election_id.in_(election_ids)) if election_ids else db.query(Vote).filter(False)
    elif current_user.rol == ROLE_COMISION:
        if current_user.election_id:
            elections_query = db.query(Election).filter(Election.id == current_user.election_id)
        elif current_user.school_id:
            elections_query = db.query(Election).filter(Election.school_id == current_user.school_id)
        else:
            elections_query = db.query(Election).filter(False)
        election_ids = [e.id for e in elections_query.all()]
        voters_query = db.query(Voter).filter(Voter.election_id.in_(election_ids)) if election_ids else db.query(Voter).filter(False)
        votes_query = db.query(Vote).filter(Vote.election_id.in_(election_ids)) if election_ids else db.query(Vote).filter(False)
    else:
        elections_query = db.query(Election).filter(False)
        voters_query = db.query(Voter).filter(False)
        votes_query = db.query(Vote).filter(False)

    total_elecciones = elections_query.count()
    elecciones_activas = elections_query.filter(Election.estado == "Abierta").count()
    total_padron = voters_query.count()
    total_votos = votes_query.count()

    participacion_global = (total_votos / total_padron * 100.0) if total_padron > 0 else 0.0

    ultimas = elections_query.order_by(Election.fecha_creacion.desc()).limit(5).all()

    return DashboardStatsResponse(
        total_elecciones=total_elecciones,
        elecciones_activas=elecciones_activas,
        total_padron=total_padron,
        total_votos_emitidos=total_votos,
        participacion_global=round(participacion_global, 1),
        ultimas_elecciones=ultimas
    )

