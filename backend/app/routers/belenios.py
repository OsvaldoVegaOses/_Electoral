from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.auth import get_current_user, check_election_access
from app.config import settings
from app.database import get_db
from app.models import BeleniosBinding, BeleniosOperation, Election, User
from app.belenios import service
from app.belenios.client import BeleniosClient, ProviderError, require_enabled
from app.belenios.verification import verify_result
from app.belenios.deployment import enabled, public_url

def private_response(response: Response):
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"


router = APIRouter(prefix="/elections/{election_id}/belenios", tags=["Motor Belenios"], dependencies=[Depends(private_response)])


class StrictInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PrepareInput(StrictInput):
    request_id: UUID
    policy: Literal["R1", "R2"]
    representative_ids: list[int] = Field(min_length=1, max_length=100)
    approval_ref: str = Field(pattern=r"^[A-Za-z0-9_.-]{1,100}$")
    ballot_mode: Literal["mandatory_single_choice_no_blank_no_null"]
    synthetic_laboratory: bool


class TransitionInput(StrictInput):
    request_id: UUID
    action: Literal["ValidateElection", "Open", "Close", "ComputeEncryptedTally", "ReleaseTally"]


class ReconcileInput(StrictInput):
    operation_id: UUID
    candidate_uuid: str | None = Field(default=None, pattern=r"^[a-zA-Z0-9]{14}$")
    manually_reviewed: Literal[True]


class VerifyInput(StrictInput):
    final_event_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    result_object_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    archive_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    anchor_reference: str = Field(pattern=r"^[A-Za-z0-9_.-]{1,100}$")


def context(election_id, db, user, write=False):
    election = db.get(Election, election_id)
    if election is None:
        raise HTTPException(404, "Elección no encontrada.")
    check_election_access(user, election, write=write, allow_belenios=True)
    if write:
        require_enabled(election)
    return election, db.query(BeleniosBinding).filter_by(election_id=election_id).first()


def required(binding):
    if binding is None:
        raise HTTPException(404, "Elección sin vinculación Belenios.")
    return binding


@router.get("")
def status(election_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    election, binding = context(election_id, db, user)
    data = service.summary(binding)
    if data and binding.remote_uuid:
        try:
            base = public_url(binding.policy)
        except HTTPException:
            base = None
        if base:
            data["public_url"] = base + "/election#" + binding.remote_uuid
            data["admin_url"] = base + "/admin#elections/" + binding.remote_uuid
    if data:
        closed = db.query(BeleniosOperation.id).filter_by(binding_id=binding.id, kind="Close", phase="CONFIRMED").first() is not None
        data["available_actions"] = [action for action, (before, _, _) in service.TRANSITIONS.items() if before == binding.phase
                                     and not binding.inflight and not (action == "Open" and closed) and not (action == "ComputeEncryptedTally" and not closed)]
    return {"enabled": enabled(election), "mode": settings.BELENIOS_MODE, "max_units": 100, "binding": data}


@router.post("/prepare", status_code=201)
def prepare(election_id: int, body: PrepareInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    election, _ = context(election_id, db, user, write=True)
    if not body.synthetic_laboratory and settings.BELENIOS_MODE != "pilot":
        raise HTTPException(422, "Participantes reales requieren el piloto aprobado.")
    return service.prepare(db, election, user, body)


@router.get("/units")
def units(election_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _, binding = context(election_id, db, user)
    return {"private_mapping": True, "units": [{"representative_id": unit.representative_id, "alias": unit.alias} for unit in service.units(db, required(binding))]}


@router.post("/transition")
def transition(election_id: int, body: TransitionInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    election, binding = context(election_id, db, user, write=True)
    return service.transition(db, election, required(binding), user, body)


@router.post("/reconcile")
def reconcile(election_id: int, body: ReconcileInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _, binding = context(election_id, db, user, write=True)
    try:
        return service.reconcile(db, required(binding), body.candidate_uuid, str(body.operation_id))
    except ProviderError:
        raise HTTPException(503, "No se pudo cotejar el proveedor; no se modificó la operación pendiente.") from None


@router.post("/verify")
def verify(election_id: int, body: VerifyInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _, binding = context(election_id, db, user, write=True)
    require_enabled(db.get(Election, election_id))
    binding = required(binding)
    try:
        return verify_result(db, binding, body, BeleniosClient(binding.policy))
    except ProviderError:
        raise HTTPException(503, "No se confirmó la verificación externa; no se publicó resultado.") from None


@router.get("/record")
def record(election_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _, binding = context(election_id, db, user)
    binding = required(binding)
    if binding.phase != "Verified" or not binding.verified_result:
        raise HTTPException(409, "Todavía no existe resultado verificado.")
    import json
    return json.loads(binding.verified_result)


@router.get("/record/pdf")
def record_pdf(election_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from fastapi.responses import StreamingResponse
    from app.belenios.record import pdf_record
    evidence=record(election_id,db,user)
    return StreamingResponse(pdf_record(evidence),media_type="application/pdf",
        headers={"Content-Disposition":f'attachment; filename="Expediente_Belenios_{election_id}.pdf"',"Cache-Control":"no-store"})
