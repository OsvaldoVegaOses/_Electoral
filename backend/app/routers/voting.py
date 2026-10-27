import hmac
import hashlib
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Voter, Election, Candidate, Vote, School
from app.schemas import TokenValidateResponse, VoteSubmitRequest, VoteReceiptResponse, CandidateResponse
from app.auth import log_audit
from app.config import settings

router = APIRouter(prefix="/voting", tags=["Sala de Votación Pública"])

@router.post("/validate-token", response_model=TokenValidateResponse)
def validate_voting_token(token: str, db: Session = Depends(get_db)):
    """
    Módulo 5 & 3: Valida el token del elector y verifica las reglas de votación
    (persona vs familia, estado de la elección, sufragio previo).
    """
    token_clean = token.strip()
    voter = db.query(Voter).filter(Voter.token_votacion == token_clean).first()
    
    if not voter:
        return TokenValidateResponse(
            valido=False,
            mensaje="Token de votación no reconocido o inválido. Verifique las credenciales enviadas a su correo."
        )

    election = db.query(Election).filter(Election.id == voter.election_id).first()
    if not election:
        return TokenValidateResponse(valido=False, mensaje="Elección asociada no encontrada.")

    # 1. Validar estado de la elección
    if election.estado != "Abierta":
        return TokenValidateResponse(
            valido=False,
            mensaje=f"La elección no se encuentra abierta para recibir sufragios (Estado actual: {election.estado})."
        )

    # 2. Validar si el elector individual ya votó
    if voter.estado == "Votó":
        fecha_str = voter.fecha_voto.strftime("%d/%m/%Y a las %H:%M hrs") if voter.fecha_voto else "previamente"
        return TokenValidateResponse(
            valido=False,
            mensaje=f"Estimado/a {voter.nombre}, su voto ya fue emitido y registrado de forma irreversible el {fecha_str}."
        )

    if voter.estado == "Bloqueado":
        return TokenValidateResponse(
            valido=False,
            mensaje="Su registro se encuentra bloqueado por la Comisión Electoral. Contáctese con los administradores."
        )

    # 3. Módulo 3: Validación de Regla de Votación Familiar
    if election.regla_votacion == "Un voto por familia" and voter.familia_id:
        family_vote = db.query(Voter).filter(
            Voter.election_id == election.id,
            Voter.familia_id == voter.familia_id,
            Voter.estado == "Votó"
        ).first()
        
        if family_vote:
            return TokenValidateResponse(
                valido=False,
                mensaje=(
                    f"La regla electoral vigente para este proceso es 'Un voto por familia'. "
                    f"El representante familiar ({family_vote.nombre}) ya emitió el sufragio correspondiente al grupo {voter.familia_id}."
                )
            )

    # Cargar candidatos ordenados
    candidates = db.query(Candidate).filter(
        Candidate.election_id == election.id
    ).order_by(Candidate.orden.asc()).all()

    candidates_response = [
        CandidateResponse(
            id=c.id,
            nombre=c.nombre,
            cargo=c.cargo,
            descripcion=c.descripcion,
            foto=c.foto,
            orden=c.orden,
            es_blanco=c.es_blanco,
            es_nulo=c.es_nulo,
            election_id=c.election_id,
            votos_count=0  # Secrecía: No exponer votos acumulados en la pantalla de votación
        )
        for c in candidates
    ]

    school_nombre = election.school.nombre if election.school else "Institución Organizadora"

    return TokenValidateResponse(
        valido=True,
        mensaje="Token verificado correctamente. Elector habilitado para emitir sufragio.",
        elector_nombre=voter.nombre,
        eleccion_nombre=election.nombre,
        eleccion_tipo=election.tipo_votacion,
        regla_votacion=election.regla_votacion,
        colegio_nombre=school_nombre,
        candidatos=candidates_response
    )

@router.post("/submit", response_model=VoteReceiptResponse)
def submit_vote(vote_in: VoteSubmitRequest, db: Session = Depends(get_db)):
    """
    Módulo 5: Emisión de voto.
    - Secrecía y trazabilidad mediante HMAC-SHA256 de Integridad (CRIT-05)
    - Bloqueo con SELECT FOR UPDATE para concurrencia (HIGH-05)
    - Registro irreversible
    - Bloqueo inmediato del token
    """
    token_clean = vote_in.token.strip()
    
    # HIGH-05: Bloqueo transaccional con SELECT FOR UPDATE
    voter = db.query(Voter).filter(
        Voter.token_votacion == token_clean
    ).with_for_update().first()

    if not voter:
        raise HTTPException(status_code=400, detail="Token de votación inválido")

    election = db.query(Election).filter(Election.id == voter.election_id).first()
    if not election or election.estado != "Abierta":
        raise HTTPException(status_code=400, detail="La elección no está abierta para votación")

    if voter.estado != "Pendiente":
        raise HTTPException(status_code=400, detail="Este elector ya emitió su voto o no está habilitado")

    # Revalidar regla familiar
    if election.regla_votacion == "Un voto por familia" and voter.familia_id:
        family_vote = db.query(Voter).filter(
            Voter.election_id == election.id,
            Voter.familia_id == voter.familia_id,
            Voter.estado == "Votó"
        ).first()
        if family_vote:
            raise HTTPException(
                status_code=400,
                detail=f"Un voto ya fue emitido por un miembro de la familia {voter.familia_id}"
            )

    # Validar candidato
    candidate = db.query(Candidate).filter(
        Candidate.id == vote_in.candidate_id,
        Candidate.election_id == election.id
    ).first()
    if not candidate:
        raise HTTPException(status_code=400, detail="La opción o candidato seleccionado no pertenece a esta elección")

    now = datetime.now(timezone.utc)
    
    # CRIT-05: Generar HMAC-SHA256 de Integridad Criptográfica (con clave secreta)
    hash_seed = f"{voter.id}-{candidate.id}-{now.isoformat()}-{uuid.uuid4()}"
    hash_integridad = hmac.new(
        settings.VOTE_HMAC_KEY.encode("utf-8"),
        hash_seed.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    # 1. Registrar voto en la urna
    vote = Vote(
        candidate_id=candidate.id,
        voter_id=voter.id,
        election_id=election.id,
        fecha_voto=now,
        hash_integridad=hash_integridad
    )
    db.add(vote)

    # 2. Marcar elector como "Votó" y registrar timestamp
    voter.estado = "Votó"
    voter.fecha_voto = now

    # 3. Si es regla por familia, marcar a los demás miembros de la familia como "Bloqueado" por cuota familiar cubierta
    if election.regla_votacion == "Un voto por familia" and voter.familia_id:
        other_family_members = db.query(Voter).filter(
            Voter.election_id == election.id,
            Voter.familia_id == voter.familia_id,
            Voter.id != voter.id,
            Voter.estado == "Pendiente"
        ).all()
        for member in other_family_members:
            member.estado = "Bloqueado"

    db.commit()

    # 4. Registrar en Auditoría (sin revelar el candidato votado para garantizar voto secreto)
    log_audit(
        db,
        accion="Emitió voto",
        detalle=f"Voto verificado con Hash: {hash_integridad[:16]}... para elección '{election.nombre}' (Elector ID: {voter.id})",
        usuario="Elector Anónimo"
    )

    school_nombre = election.school.nombre if election.school else "Institución Organizadora"

    return VoteReceiptResponse(
        success=True,
        mensaje="¡Tu voto ha sido registrado y sellado con éxito!",
        hash_integridad=hash_integridad,
        fecha_voto=now,
        eleccion_nombre=election.nombre,
        colegio_nombre=school_nombre
    )
