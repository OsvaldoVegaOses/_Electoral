from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config import settings

# Configuración del motor de base de datos
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
elif "postgresql" in settings.DATABASE_URL:
    connect_args = {"options": "-c timezone=utc"}

engine = create_engine(
    settings.DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1),
    connect_args=connect_args,
    pool_pre_ping=True
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

from app.azure_database import configure_azure_identity
configure_azure_identity(engine)

def get_db():
    """Generador de sesiones para inyección de dependencias en endpoints FastAPI"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
