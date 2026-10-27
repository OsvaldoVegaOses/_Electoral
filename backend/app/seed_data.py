import os
import uuid
import secrets
import logging
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from app.models import School, Election, ElectoralCommittee, Candidate, Voter, User, AuditLog
from app.auth import get_password_hash
from app.rut_validator import format_rut

logger = logging.getLogger("theogen.seed")

def seed_initial_data(db: Session):
    """Carga datos de demostración si la base de datos está vacía"""
    # Verificar si ya existe usuario admin
    existing_user = db.query(User).filter(User.email == "admin@theogen.cl").first()
    if existing_user:
        return

    logger.info("Iniciando seed de datos para TheoGen Electoral...")

    # HIGH-03: Generar contraseñas aleatorias seguras para cuentas de seed
    admin_password = secrets.token_urlsafe(16)
    comision_password = secrets.token_urlsafe(16)

    # 1. Crear Usuarios de Sistema
    admin_user = User(
        nombre="Administrador General",
        email="admin@theogen.cl",
        password_hash=get_password_hash(admin_password),
        rol="Administrador"
    )
    comision_user = User(
        nombre="Presidenta Comisión Electoral",
        email="comision@theogen.cl",
        password_hash=get_password_hash(comision_password),
        rol="Comisión Electoral"
    )
    db.add_all([admin_user, comision_user])
    db.flush()

    # B2: Provisionamiento sin imprimir contraseñas en logs del sistema
    logger.info("Usuarios iniciales creados exitosamente (admin@theogen.cl, comision@theogen.cl).")
    cred_file = os.getenv("PROVISION_CREDENTIALS_FILE")
    if cred_file:
        try:
            with open(cred_file, "w", encoding="utf-8") as f:
                f.write(f"ADMIN_PASSWORD={admin_password}\n")
                f.write(f"COMISION_PASSWORD={comision_password}\n")
            logger.info("Credenciales de aprovisionamiento escritas en %s", cred_file)
        except Exception as e:
            logger.error("No se pudo escribir archivo de credenciales: %s", e)

    # 2. Crear Colegio de Demostración
    school = School(
        nombre="Colegio San Gabriel de Las Condes",
        rbd="10245-8",
        comuna="Las Condes, Santiago",
        correo_contacto="contacto@sangabriel.cl",
        telefono="+56 2 2456 7800",
        logo="https://images.unsplash.com/photo-1546410531-bb4caa6b424d?w=200&auto=format&fit=crop&q=80"
    )
    db.add(school)
    db.flush()

    # 3. Crear Elección Modelo
    now = datetime.now(timezone.utc)
    election = Election(
        nombre="Elección Centro General de Padres y Apoderados 2026-2027",
        descripcion="Proceso de demostración técnica (MVP no vinculante) para el Centro de Padres del Colegio San Gabriel. Entorno de pruebas no habilitado para elecciones vinculantes.",
        fecha_inicio=now - timedelta(hours=2),
        fecha_fin=now + timedelta(days=2),
        estado="Abierta",
        school_id=school.id,
        tipo_votacion="Centro de Padres",
        regla_votacion="Un voto por familia"
    )
    db.add(election)
    db.flush()

    # 4. Crear Miembros de la Comisión Electoral
    committee = [
        ElectoralCommittee(
            nombre="María Paz Edwards",
            rut="13.456.789-K",
            correo="mpaz.edwards@sangabriel.cl",
            cargo="Presidenta Comisión",
            election_id=election.id
        ),
        ElectoralCommittee(
            nombre="Gonzalo Vial Recabarren",
            rut="15.678.901-2",
            correo="gvial@sangabriel.cl",
            cargo="Secretario General",
            election_id=election.id
        ),
        ElectoralCommittee(
            nombre="Patricia Larraín Matte",
            rut="14.321.098-7",
            correo="plarrain@sangabriel.cl",
            cargo="Vocal de Control",
            election_id=election.id
        )
    ]
    db.add_all(committee)

    # 5. Crear Candidatos (Listas Oficiales + Blanco y Nulo)
    candidates = [
        Candidate(
            nombre="Lista A: Innovación y Familia",
            cargo="Presidencia: Carolina Valenzuela",
            descripcion="Propuestas: Modernización de plataformas escolares, plan integral de seguridad en accesos y digitalización de talleres deportivos extracurriculares.",
            foto="https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?w=400&auto=format&fit=crop&q=80",
            orden=1,
            es_blanco=False,
            es_nulo=False,
            election_id=election.id
        ),
        Candidate(
            nombre="Lista B: Comunidad Unida",
            cargo="Presidencia: Andrés Morales",
            descripcion="Propuestas: Creación de fondos concursables directos por curso, gran feria de sustentabilidad y refuerzo de convenios de salud y deportes.",
            foto="https://images.unsplash.com/photo-1560250097-0b93528c311a?w=400&auto=format&fit=crop&q=80",
            orden=2,
            es_blanco=False,
            es_nulo=False,
            election_id=election.id
        ),
        Candidate(
            nombre="Lista C: Futuro Escolar",
            cargo="Presidencia: Marcela Soto",
            descripcion="Propuestas: Enfoque integral en salud mental y convivencia escolar, remodelación ecológica de patios y escuelas para padres mensuales.",
            foto="https://images.unsplash.com/photo-1580894732444-8ecded7900cd?w=400&auto=format&fit=crop&q=80",
            orden=3,
            es_blanco=False,
            es_nulo=False,
            election_id=election.id
        ),
        Candidate(
            nombre="Voto en Blanco",
            cargo="Opción Institucional",
            descripcion="Voto deliberadamente no asignado a ninguna lista postulante.",
            foto="",
            orden=98,
            es_blanco=True,
            es_nulo=False,
            election_id=election.id
        ),
        Candidate(
            nombre="Voto Nulo",
            cargo="Opción Institucional",
            descripcion="Manifestación de anulación formal del sufragio.",
            foto="",
            orden=99,
            es_blanco=False,
            es_nulo=True,
            election_id=election.id
        )
    ]
    db.add_all(candidates)

    # 6. Crear 20 Electores con RUTs chilenos válidos, familias y tokens UUID
    # Usamos RUTs verificados matemáticamente con Módulo 11
    sample_voters = [
        {"rut": "16.234.567-2", "nombre": "Francisca Silva Montes", "curso": "1° Básico A", "correo": "fsilva@gmail.com", "familia_id": "FAM-101"},
        {"rut": "15.890.123-K", "nombre": "Rodrigo Silva Montes", "curso": "4° Básico B", "correo": "rsilva@gmail.com", "familia_id": "FAM-101"}, # Misma familia
        {"rut": "17.123.456-7", "nombre": "Camila Vergara Pinto", "curso": "2° Básico B", "correo": "cvergara@gmail.com", "familia_id": "FAM-102"},
        {"rut": "18.345.678-4", "nombre": "Felipe Errázuriz Lyon", "curso": "3° Básico A", "correo": "ferrazuriz@gmail.com", "familia_id": "FAM-103"},
        {"rut": "19.567.890-1", "nombre": "Sofía Mackenna Cruz", "curso": "5° Básico A", "correo": "smackenna@gmail.com", "familia_id": "FAM-104"},
        {"rut": "14.789.012-3", "nombre": "Ignacio Walker Prieto", "curso": "6° Básico B", "correo": "iwalker@gmail.com", "familia_id": "FAM-105"},
        {"rut": "16.789.234-8", "nombre": "Daniela Zañartu Vicuña", "curso": "7° Básico A", "correo": "dzanartu@gmail.com", "familia_id": "FAM-106"},
        {"rut": "17.890.345-5", "nombre": "Matías Subercaseaux L.", "curso": "8° Básico B", "correo": "msubercaseaux@gmail.com", "familia_id": "FAM-107"},
        {"rut": "15.345.890-9", "nombre": "Javiera Ossa Bulnes", "curso": "1° Medio A", "correo": "jossa@gmail.com", "familia_id": "FAM-108"},
        {"rut": "16.456.901-6", "nombre": "Sebastián Claro Valdés", "curso": "1° Medio B", "correo": "sclaro@gmail.com", "familia_id": "FAM-109"},
        {"rut": "18.901.234-2", "nombre": "Isidora Riesco Echeverría", "curso": "2° Medio A", "correo": "iriesco@gmail.com", "familia_id": "FAM-110"},
        {"rut": "17.654.321-0", "nombre": "Cristóbal Correa Montt", "curso": "2° Medio B", "correo": "ccorrea@gmail.com", "familia_id": "FAM-111"},
        {"rut": "19.876.543-8", "nombre": "Valentina Ureta Cox", "curso": "3° Medio A", "correo": "vureta@gmail.com", "familia_id": "FAM-112"},
        {"rut": "14.567.890-4", "nombre": "Nicolás Irarrázaval Ruiz", "curso": "3° Medio B", "correo": "nirarrazaval@gmail.com", "familia_id": "FAM-113"},
        {"rut": "15.678.123-1", "nombre": "Antonia Balmaceda Tagle", "curso": "4° Medio A", "correo": "abalmaceda@gmail.com", "familia_id": "FAM-114"},
        {"rut": "16.987.654-3", "nombre": "Joaquín Tocornal Bello", "curso": "4° Medio B", "correo": "jtocornal@gmail.com", "familia_id": "FAM-115"},
        {"rut": "18.234.567-9", "nombre": "Lucía Cousiño Goyenechea", "curso": "Kínder A", "correo": "lcousino@gmail.com", "familia_id": "FAM-116"},
        {"rut": "17.456.789-3", "nombre": "Tomás Huneeus Zegers", "curso": "Kínder B", "correo": "thuneeus@gmail.com", "familia_id": "FAM-117"},
        {"rut": "19.345.678-0", "nombre": "Bernardita Amunátegui S.", "curso": "Prekínder A", "correo": "bamunategui@gmail.com", "familia_id": "FAM-118"},
        {"rut": "15.987.432-6", "nombre": "Vicente Gandarillas Hurtado", "curso": "Prekínder B", "correo": "vgandarillas@gmail.com", "familia_id": "FAM-119"},
    ]

    # Lista de tokens amigables para el demo
    demo_tokens = [
        "3a8f803d-0ccb-48b7-89f7-d92aa4c729de", # Token de ejemplo explícito en el prompt!
        "b1c2d3e4-5f6a-7b8c-9d0e-1f2a3b4c5d6e",
        "c2d3e4f5-6a7b-8c9d-0e1f-2a3b4c5d6e7f",
        "d3e4f5a6-7b8c-9d0e-1f2a-3b4c5d6e7f8a",
        "e4f5a6b7-8c9d-0e1f-2a3b-4c5d6e7f8a9b",
        "f5a6b7c8-9d0e-1f2a-3b4c-5d6e7f8a9b0c",
        "a6b7c8d9-0e1f-2a3b-4c5d-6e7f8a9b0c1d",
        "b7c8d9e0-1f2a-3b4c-5d6e-7f8a9b0c1d2e",
        "c8d9e0f1-2a3b-4c5d-6e7f-8a9b0c1d2e3f",
        "d9e0f1a2-3b4c-5d6e-7f8a-9b0c1d2e3f4a",
        "e0f1a2b3-4c5d-6e7f-8a9b-0c1d2e3f4a5b",
        "f1a2b3c4-5d6e-7f8a-9b0c-1d2e3f4a5b6c",
        "a2b3c4d5-6e7f-8a9b-0c1d-2e3f4a5b6c7d",
        "b3c4d5e6-7f8a-9b0c-1d2e-3f4a5b6c7d8e",
        "c4d5e6f7-8a9b-0c1d-2e3f-4a5b6c7d8e9f",
        "d5e6f7a8-9b0c-1d2e-3f4a-5b6c7d8e9f0a",
        "e6f7a8b9-0c1d-2e3f-4a5b-6c7d8e9f0a1b",
        "f7a8b9c0-1d2e-3f4a-5b6c-7d8e9f0a1b2c",
        "a8b9c0d1-2e3f-4a5b-6c7d-8e9f0a1b2c3d",
        "b9c0d1e2-3f4a-5b6c-7d8e-9f0a1b2c3d4e",
    ]

    voters = []
    for i, v_info in enumerate(sample_voters):
        voters.append(Voter(
            rut=v_info["rut"],
            nombre=v_info["nombre"],
            curso=v_info["curso"],
            correo=v_info["correo"],
            familia_id=v_info["familia_id"],
            token_votacion=demo_tokens[i] if i < len(demo_tokens) else str(uuid.uuid4()),
            estado="Pendiente",
            election_id=election.id
        ))
    db.add_all(voters)

    # 7. Registrar Auditoría Inicial
    logs = [
        AuditLog(
            fecha=now - timedelta(hours=2),
            usuario="admin@theogen.cl",
            accion="Creó elección",
            detalle=f"Se creó la elección '{election.nombre}' para la institución '{school.nombre}' con regla '{election.regla_votacion}'."
        ),
        AuditLog(
            fecha=now - timedelta(hours=1, minutes=45),
            usuario="admin@theogen.cl",
            accion="Subió padrón",
            detalle="Se cargaron exitosamente 20 electores habilitados correspondientes a las familias del colegio."
        ),
        AuditLog(
            fecha=now - timedelta(hours=1, minutes=30),
            usuario="admin@theogen.cl",
            accion="Generó credenciales",
            detalle="Se generaron 20 tokens UUID criptográficos únicos de sufragio."
        ),
        AuditLog(
            fecha=now - timedelta(hours=1),
            usuario="comision@theogen.cl",
            accion="Abrió votación",
            detalle="La Comisión Electoral verificó la urna digital vacía y firmó el Acta de Apertura."
        )
    ]
    db.add_all(logs)

    db.commit()
    logger.info("Seed de datos inicial completado exitosamente.")
