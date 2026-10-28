"""Durable management intents. An uncertain mutation is never automatically retried."""
import hashlib
import json
import re
import secrets
from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from app.models import BeleniosBinding, BeleniosOperation, BeleniosUnit, Candidate, Election, Vote, Voter, VotingEntitlement
from app.belenios.client import BeleniosClient, ProviderError, require_enabled


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def units(db, binding):
    return db.query(BeleniosUnit).filter_by(binding_id=binding.id).order_by(BeleniosUnit.id).all()


def summary(binding):
    if binding is None:
        return None
    return {"policy": binding.policy, "uuid": binding.remote_uuid, "phase": binding.phase,
            "inflight": binding.inflight, "total_people": binding.total_people, "total_units": binding.total_units,
            "result": json.loads(binding.verified_result) if binding.verified_result else None}


def request_id(value):
    try:
        return str(UUID(str(value)))
    except ValueError:
        raise HTTPException(422, "Identificador de operación inválido.") from None


def reserve(db, binding, operator, key, kind):
    key = request_id(key)
    if db.get(BeleniosOperation, key):
        raise HTTPException(409, "Operación ya registrada; consulte el estado, no repita el envío.")
    if binding.phase == "UNKNOWN":
        raise HTTPException(409, "Operación desconocida: reconciliación manual requerida.")
    changed = db.query(BeleniosBinding).filter_by(id=binding.id, inflight=None, phase=binding.phase).update({"inflight": key}, synchronize_session=False)
    if changed != 1:
        db.rollback()
        raise HTTPException(409, "Existe una operación pendiente/desconocida: reconciliación manual requerida.")
    db.add(BeleniosOperation(id=key, binding_id=binding.id, operator_id=operator.id, kind=kind, phase="PENDING"))
    try:
        db.commit()  # Intent is durable before any remote mutation.
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "La operación ya fue reservada por otra petición.") from None
    db.refresh(binding)
    return key


def complete(db, binding, key, phase):
    db.query(Election.id).filter_by(id=binding.election_id).with_for_update().one()
    changed = db.query(BeleniosBinding).filter_by(id=binding.id, inflight=key).update({"phase": phase, "inflight": None}, synchronize_session=False)
    if changed != 1:
        db.rollback()
        raise HTTPException(409, "La operación ya fue reconciliada; no se sobrescribió un estado posterior.")
    db.get(Election, binding.election_id).estado = {"Draft": "Borrador", "Closed": "Cerrada", "Open": "Abierta", "EncryptedTally": "Cerrada", "Tallied": "Cerrada"}[phase]
    election = db.get(Election, binding.election_id)
    if phase == "Open" and election.fecha_inicio is None:
        election.fecha_inicio = datetime.now(timezone.utc)
    if phase == "Closed" and db.get(BeleniosOperation, key).kind == "Close":
        election.fecha_cierre_efectiva = datetime.now(timezone.utc)
    db.get(BeleniosOperation, key).phase = "CONFIRMED"
    db.commit()
    db.refresh(binding)


def unknown(db, binding, key):
    db.rollback()
    binding = db.get(BeleniosBinding, binding.id)
    changed = db.query(BeleniosBinding).filter_by(id=binding.id, inflight=key).update({"phase": "UNKNOWN"}, synchronize_session=False)
    if changed != 1:
        db.rollback()
        raise HTTPException(409, "La operación ya fue reconciliada; consulte el estado actual.")
    db.get(BeleniosOperation, key).phase = "UNKNOWN"
    db.commit()
    raise HTTPException(503, "Resultado remoto desconocido. No se reintentó; coteje y reconcilie antes de continuar.")


def prepare(db, election, operator, body, client_factory=BeleniosClient):
    require_enabled()
    election = db.query(Election).filter_by(id=election.id).populate_existing().with_for_update().one()
    if election.estado != "Borrador" or db.query(Vote.id).filter_by(election_id=election.id).first() or db.query(VotingEntitlement.id).filter_by(election_id=election.id).first():
        raise HTTPException(409, "Solo puede vincularse un borrador sin votos ni derechos MVP provisionados.")
    if db.query(BeleniosBinding.id).filter_by(election_id=election.id).first():
        raise HTTPException(409, "Ya existe una vinculación: no cree otra elección.")
    voters = db.query(Voter).filter_by(election_id=election.id).order_by(Voter.id).all()
    if not voters or any(v.estado != "Pendiente" for v in voters):
        raise HTTPException(409, "Revise y apruebe el padrón completo antes de vincular.")
    groups = {}
    for voter in voters:
        if election.regla_votacion == "Un voto por familia":
            family = (voter.familia_id or "").strip().upper()
            if not family:
                raise HTTPException(422, "Hay electores sin unidad familiar explícita.")
            group = family
        elif election.regla_votacion == "Un voto por persona":
            group = str(voter.id)
        else:
            raise HTTPException(422, "Regla electoral no soportada.")
        groups.setdefault(group, []).append(voter.id)
    representatives = body.representative_ids
    selected = set(representatives)
    if len(selected) != len(representatives) or len(selected) != len(groups) or not selected.issubset({v.id for v in voters}) or any(len(selected.intersection(group)) != 1 for group in groups.values()):
        raise HTTPException(422, "Seleccione exactamente un representante por unidad del padrón.")
    candidates = db.query(Candidate).filter_by(election_id=election.id, es_blanco=False, es_nulo=False).order_by(Candidate.orden, Candidate.id).all()
    names = [c.nombre for c in candidates]
    if len(names) < 2 or len(set(names)) != len(names):
        raise HTTPException(422, "Se requieren al menos dos opciones regulares distintas.")
    client = client_factory(body.policy)
    try:
        client.check()
        account = client.call("GET", "account")
    except ProviderError:
        raise HTTPException(503, "Proveedor no disponible o incompatible; no se creó una elección.") from None
    reference = secrets.token_hex(16)
    draft = {"version": 1, "owners": [account["id"]], "booth": 2, "group": "Ed25519", "languages": ["en"],
             "authentication": ["Configured", "email"], "questions": {
                 "name": election.nombre, "description": "Laboratorio TheoGen ref " + reference,
                 "administrator": "Comision electoral", "credential_authority": "Autoridad externa",
                 "questions": [{"question": "Elija una lista", "answers": names, "min": 1, "max": 1}]}}
    binding = BeleniosBinding(election_id=election.id, reference=reference, policy=body.policy, draft_json=canonical(draft),
                             approval_ref=body.approval_ref, total_people=len(voters), total_units=len(groups), phase="PREPARING")
    db.add(binding)
    try:
        db.flush()
        for voter_id in representatives:
            db.add(BeleniosUnit(binding_id=binding.id, representative_id=voter_id, alias="unit-" + secrets.token_hex(16) + "@ejemplo.test"))
        election.total_padron_congelado, election.total_habilitados_congelado = len(voters), len(groups)
        election.config_snapshot = canonical(draft["questions"])
        election.config_hash = hashlib.sha256(election.config_snapshot.encode()).hexdigest()
        key = reserve(db, binding, operator, body.request_id, "Prepare")
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "La elección ya está vinculada o su preparación está en curso.") from None
    try:
        uuid = client.call("POST", "elections", draft, match=True)
        if not isinstance(uuid, str) or not re.fullmatch(r"[a-zA-Z0-9]{14}", uuid):
            raise ProviderError("UUID inválido")
        binding.remote_uuid = uuid
        db.commit()  # Preserve known remote identifier even if a later step is interrupted.
        roster = [unit.alias for unit in units(db, binding)]
        client.call("PUT", f"elections/{uuid}/draft/voters", roster, match=True)
        if client.call("GET", f"elections/{uuid}/draft/voters") != roster or client.call("GET", f"elections/{uuid}/draft")["questions"] != draft["questions"]:
            raise ProviderError("Readback mismatch")
        complete(db, binding, key, "Draft")
    except Exception:
        unknown(db, binding, key)
    return summary(binding)


TRANSITIONS = {"ValidateElection": ("Draft", "Closed", "/draft"), "Open": ("Closed", "Open", ""),
               "Close": ("Open", "Closed", ""), "ComputeEncryptedTally": ("Closed", "EncryptedTally", ""),
               "ReleaseTally": ("EncryptedTally", "Tallied", "")}


def transition(db, election, binding, operator, body, client_factory=BeleniosClient):
    require_enabled()
    if binding.inflight or binding.phase == "UNKNOWN":
        raise HTTPException(409, "Hay una operación no reconciliada.")
    before, after, suffix = TRANSITIONS[body.action]
    if binding.phase != before or not binding.remote_uuid:
        raise HTTPException(409, "Transición incompatible con el estado confirmado.")
    closed = db.query(BeleniosOperation.id).filter_by(binding_id=binding.id, kind="Close", phase="CONFIRMED").first() is not None
    if (body.action == "Open" and closed) or (body.action == "ComputeEncryptedTally" and not closed):
        raise HTTPException(409, "No se reabre una elección cerrada ni se escruta antes de su cierre confirmado.")
    client = client_factory(binding.policy)
    route = "elections/" + binding.remote_uuid
    try:
        client.check()
        if before == "Draft":
            status = client.call("GET", route + "/draft/status")
            trustees = client.call("GET", route + "/draft/trustees")
            if not status.get("credentials_ready") or not status.get("trustees_ready") or trustees[0] != "Threshold" or trustees[1].get("threshold") != 2 or len(trustees[1].get("trustees", [])) != 3:
                raise HTTPException(409, "Complete fuera de TheoGen la autoridad de credenciales y la ceremonia de trustees 2/3.")
            if client.call("GET", route + "/draft")["questions"] != json.loads(binding.draft_json)["questions"]:
                raise HTTPException(409, "La configuración remota difiere de la aprobada.")
            if status.get("num_voters") != binding.total_units or client.call("GET", route + "/draft/voters") != [unit.alias for unit in units(db, binding)]:
                raise HTTPException(409, "El padrón remoto difiere del congelado.")
        elif client.call("GET", route)["state"] != before:
            raise HTTPException(409, "Estado remoto distinto: cotejo manual requerido.")
    except ProviderError:
        raise HTTPException(503, "No se confirmó el estado del proveedor; no se mutó.") from None
    key = reserve(db, binding, operator, body.request_id, body.action)
    try:
        client.call("POST", route + suffix, body.action, match=True)
        if client.call("GET", route)["state"] != after:
            raise ProviderError("Estado posterior no confirmado")
        complete(db, binding, key, after)
    except Exception:
        unknown(db, binding, key)
    return summary(binding)


def reconcile(db, binding, candidate_uuid, operation_id, client_factory=BeleniosClient):
    require_enabled()
    if not binding.inflight or binding.inflight != operation_id:
        raise HTTPException(409, "Identifique la operación pendiente exacta.")
    client = client_factory(binding.policy)
    client.check()
    uuid = binding.remote_uuid or candidate_uuid
    if not uuid or not re.fullmatch(r"[a-zA-Z0-9]{14}", uuid):
        raise HTTPException(422, "Se requiere el UUID remoto cotejado manualmente.")
    operation = db.get(BeleniosOperation, operation_id)
    route = "elections/" + uuid
    if operation.kind == "Prepare":
        draft = client.call("GET", route + "/draft")
        if draft["questions"] != json.loads(binding.draft_json)["questions"] or client.call("GET", route + "/draft/voters") != [unit.alias for unit in units(db, binding)]:
            raise HTTPException(409, "Borrador/padrón remoto no coinciden; no se adoptó ni reparó automáticamente.")
        after = "Draft"
    else:
        after = TRANSITIONS[operation.kind][1]
        if client.call("GET", route)["state"] != after:
            raise HTTPException(409, "La transición no está demostrada; la operación sigue bloqueada.")
    binding.remote_uuid = uuid
    complete(db, binding, operation_id, after)
    return summary(binding)
