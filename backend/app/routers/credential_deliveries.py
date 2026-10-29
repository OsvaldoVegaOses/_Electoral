from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import CredentialDelivery, Election, User, Voter
from app.auth import get_current_user, check_election_access
from app import credentials

router=APIRouter(prefix="/elections/{election_id}/voters/{voter_id}/deliveries",tags=["Entrega de credenciales MVP"])

class IssueInput(BaseModel):
    model_config=ConfigDict(extra="forbid")
    operation_id: UUID

def context(db,election_id,voter_id,user):
    election=db.get(Election,election_id)
    if election is None:
        raise HTTPException(404,"Elección no encontrada")
    check_election_access(user,election,write=True)
    voter=db.query(Voter).filter_by(id=voter_id,election_id=election_id).first()
    if voter is None:
        raise HTTPException(404,"Elector no encontrado")
    return election,voter

def public(operation):
    return {"operation_id":operation.id,"status":operation.status,"created_at":operation.created_at,
            "confirmed_at":operation.confirmed_at}

@router.get("")
def listing(election_id:int,voter_id:int,response:Response,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    response.headers["Cache-Control"]="no-store"
    context(db,election_id,voter_id,user)
    return [public(op) for op in db.query(CredentialDelivery).filter_by(voter_id=voter_id).order_by(CredentialDelivery.created_at.desc()).all()]

@router.post("",status_code=201)
def issue(election_id:int,voter_id:int,body:IssueInput,response:Response,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    response.headers["Cache-Control"]="no-store"
    election,voter=context(db,election_id,voter_id,user)
    return public(credentials.issue(db,voter,election,body.operation_id))

@router.post("/{operation_id}/reconcile")
def reconcile(election_id:int,voter_id:int,operation_id:UUID,response:Response,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    response.headers["Cache-Control"]="no-store"
    election,voter=context(db,election_id,voter_id,user)
    operation=db.get(CredentialDelivery,str(operation_id))
    if operation is None or operation.voter_id != voter.id:
        raise HTTPException(404,"Operación no encontrada")
    return public(credentials.reconcile(db,operation,voter,election))
