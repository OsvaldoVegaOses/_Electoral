import hashlib
import hmac
import json
import re
from fastapi import APIRouter, Depends, HTTPException, status
from app.belenios.client import legacy_guard
from app.models import BeleniosBinding
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
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


def _require_verified_snapshot(election: Election) -> dict:
    if (
        not election.config_snapshot
        or not election.config_hash
        or election.total_padron_congelado is None
        or election.total_habilitados_congelado is None
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "No existe una instantánea electoral verificable para esta elección. "
                "Requiere conciliación antes de emitir resultados o actas definitivas."
            ),
        )

    try:
        snapshot = json.loads(election.config_snapshot)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La instantánea electoral está dañada; se bloqueó la emisión del informe.",
        ) from exc

    if not isinstance(snapshot, dict):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La instantánea electoral tiene un formato inválido.",
        )

    canonical = json.dumps(snapshot, sort_keys=True, separators=(",", ":"))
    calculated_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    if (
        not hmac.compare_digest(calculated_hash, election.config_hash)
        or snapshot.get("election_id") != election.id
        or snapshot.get("total_padron") != election.total_padron_congelado
        or snapshot.get("total_habilitados") != election.total_habilitados_congelado
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La instantánea electoral no coincide con sus compromisos congelados.",
        )
    return snapshot


@router.get("/election/{election_id}/scrutiny", response_model=ScrutinyResponse)
def get_election_scrutiny(
    election_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),  # CRIT-03
):
    """
    Módulo 7: Calcula y presenta resultados de la plataforma.
    Calcula votos por candidato, votos nulos, votos blancos y porcentaje de participación.
    PROTEGIDO: Solo accesible cuando la elección se encuentra en estado 'Cerrada' o 'Finalizada' (A2 - P0)
    y pertenece al ámbito autorizado del usuario (A3 - P0).
    """
    election = db.query(Election).filter(Election.id == election_id).first()
    if not election:
        raise HTTPException(status_code=404, detail="Elección no encontrada")

    check_election_access(current_user, election, write=False)
    legacy_guard(db, election.id)

    # A2: Bloquear escrutinio en elecciones abiertas o borradores
    if election.estado not in ["Cerrada", "Finalizada"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"El escrutinio detallado y resultados no están disponibles mientras la elección "
                f"se encuentre en estado '{election.estado}'. Solo se publican una vez cerrada la elección."
            )
        )

    _require_verified_snapshot(election)
    total_padron = election.total_habilitados_congelado

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
        fecha_cierre=election.fecha_cierre_efectiva or election.fecha_fin
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
    legacy_guard(db, election.id)

    if election.estado in ["Abierta", "Cerrada", "Finalizada"]:
        _require_verified_snapshot(election)

    school = election.school or School(nombre="Institución Educativa", rbd="S/N", comuna="Santiago")
    committee = election.committee_members or []
    total_voters = (
        election.total_padron_congelado
        if election.total_padron_congelado is not None
        else db.query(Voter).filter(Voter.election_id == election_id).count()
    )

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
    legacy_guard(db, election.id)

    if election.estado not in ["Cerrada", "Finalizada"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"El Acta de Cierre y Escrutinio Definitivo solo puede generarse cuando la elección "
                f"esté Cerrada o Finalizada (Estado actual: '{election.estado}')."
            )
        )

    _require_verified_snapshot(election)

    school = election.school or School(nombre="Institución Educativa", rbd="S/N", comuna="Santiago")
    committee = election.committee_members or []
    total_voters = election.total_habilitados_congelado

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
def get_dashboard_stats(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    query=db.query(Election)
    if is_superadmin(current_user):
        pass
    elif current_user.rol == ROLE_RESPONSABLE and current_user.school_id:
        query=query.filter(Election.school_id == current_user.school_id)
    elif current_user.rol == ROLE_COMISION and current_user.school_id and current_user.election_id:
        query=query.filter(Election.id == current_user.election_id, Election.school_id == current_user.school_id)
    else:
        query=query.filter(False)
    elections=query.order_by(Election.fecha_creacion.desc()).all()
    totals={}
    people, known_votes, enabled_units, pending=0,0,0,0
    unknown_units=False
    for election in elections:
        binding=db.query(BeleniosBinding).filter_by(election_id=election.id).first()
        motor="belenios" if binding or election.motor == "belenios" else "mvp"
        entry=totals.setdefault(motor,{"motor":motor,"elecciones":0,"votos_verificados":0,"resultados_pendientes":0})
        entry["elecciones"]+=1
        count=db.query(Voter).filter_by(election_id=election.id).count()
        people+=election.total_padron_congelado if election.total_padron_congelado is not None else count
        units=election.total_habilitados_congelado
        if units is None and election.estado == "Borrador":
            voters=db.query(Voter).filter_by(election_id=election.id).all()
            if election.regla_votacion == "Un voto por persona":
                units=len(voters)
            elif all((v.familia_id or "").strip() for v in voters):
                units=len({v.familia_id.strip().upper() for v in voters})
        if units is None:
            unknown_units=True
        else:
            enabled_units+=units
        if motor == "belenios":
            if not binding or binding.phase != "Verified" or not binding.verified_result:
                pending+=1
                entry["resultados_pendientes"]+=1
                continue
            try:
                result=json.loads(binding.verified_result)
                votes=result["counted_ballots"]
                if not isinstance(votes,int) or votes<0 or votes>binding.total_units:
                    raise ValueError
            except (ValueError,TypeError,KeyError):
                raise HTTPException(503,"El resultado almacenado requiere revisión de integridad.") from None
        else:
            votes=db.query(Vote).filter_by(election_id=election.id).count()
        known_votes+=votes
        entry["votos_verificados"]+=votes
    participation=None if pending or unknown_units else (round(known_votes/enabled_units*100,1) if enabled_units else 0)
    return DashboardStatsResponse(total_elecciones=len(elections), elecciones_activas=sum(e.estado=="Abierta" for e in elections),
        total_padron=people,total_votos_emitidos=None if pending else known_votes,participacion_global=participation,
        total_habilitados=None if unknown_units else enabled_units,resultados_pendientes=pending,
        motores=list(totals.values()),ultimas_elecciones=elections[:5])
