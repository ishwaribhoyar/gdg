"""
Database connection and configuration
Uses SQLite for data storage + Firebase for auth/storage
"""

from sqlalchemy import create_engine, Column, String, Integer, Float, DateTime, Text, JSON, Index
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from datetime import datetime, timezone
import os
from pathlib import Path
import logging
from sqlalchemy import event

logger = logging.getLogger(__name__)

# Always use SQLite (production and development)
logger.info("Using SQLite database with WAL mode")

# Use /data/app.db for production (Railway), or local path for development
SQLITE_DB_PATH = os.getenv("SQLITE_DB_PATH")
if SQLITE_DB_PATH:
    DB_DIR = Path(SQLITE_DB_PATH).parent
    DB_PATH = Path(SQLITE_DB_PATH)
else:
    DB_DIR = Path(__file__).parent.parent / "data"
    DB_PATH = DB_DIR / "app.db"

DB_DIR.mkdir(parents=True, exist_ok=True)

def configure_sqlite(dbapi_connection, connection_record):
    """Configure SQLite for production performance"""
    cursor = dbapi_connection.cursor()
    # Enable WAL mode for better concurrent reads
    cursor.execute("PRAGMA journal_mode=WAL")
    # Synchronous NORMAL is safe with WAL and faster than FULL
    cursor.execute("PRAGMA synchronous=NORMAL")
    # Store temp tables in memory for speed
    cursor.execute("PRAGMA temp_store=MEMORY")
    # Increase cache size (negative = KB, positive = pages)
    cursor.execute("PRAGMA cache_size=-64000")  # 64MB cache
    # Enable foreign keys
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False},  # Needed for SQLite with threads
    echo=False
)

# Register the connection event
event.listen(engine, "connect", configure_sqlite)

DB_TYPE = "sqlite"
logger.info(f"SQLite database path: {DB_PATH}")


# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Platform Model - Institution, Department, User
class Institution(Base):
    __tablename__ = "institutions"
    
    id = Column(String, primary_key=True)  # institution_id
    name = Column(String, nullable=False, index=True)
    code = Column(String, nullable=True, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    is_active = Column(Integer, default=1)  # 0 or 1


class Department(Base):
    __tablename__ = "departments"
    
    id = Column(String, primary_key=True)  # department_id
    institution_id = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False, index=True)
    code = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    is_active = Column(Integer, default=1)  # 0 or 1


class User(Base):
    __tablename__ = "users"
    
    id = Column(String, primary_key=True)  # user_id (Firebase UID)
    email = Column(String, nullable=False, unique=True, index=True)
    name = Column(String, nullable=True)
    role = Column(String, default="department")  # college, department (NO admin)
    institution_id = Column(String, nullable=True, index=True)  # For college/department users
    department_id = Column(String, nullable=True, index=True)  # For department users only
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_login = Column(DateTime, nullable=True)


# Minimal SQLite Schema
class Batch(Base):
    __tablename__ = "batches"
    
    id = Column(String, primary_key=True)  # batch_id
    mode = Column(String)  # "aicte", "nba", "naac", "nirf"
    new_university = Column(Integer, default=0)  # 0 = renewal, 1 = new university (for UGC only)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    status = Column(String, default="created")
    errors = Column(JSON, nullable=True)  # Processing errors
    
    # User ownership (PLATFORM MODEL)
    user_id = Column(String, nullable=True, index=True)  # Firebase UID
    institution_id = Column(String, nullable=True, index=True)  # Reference to Institution
    department_id = Column(String, nullable=True, index=True)  # Reference to Department
    
    # Department-wise hierarchy (Institution > Department > Year) - Legacy fields for compatibility
    institution_name = Column(String, nullable=True, index=True)
    department_name = Column(String, nullable=True, index=True)
    academic_year = Column(String, nullable=True, index=True)  # e.g., "2024-25"
    
    # Data validation flags
    is_invalid = Column(Integer, default=0)  # 0 = valid, 1 = invalid (no dummy data stored)
    authenticity_score = Column(Float, nullable=True)  # From authenticity service
    
    # Results stored as JSON (temporary)
    sufficiency_result = Column(JSON, nullable=True)
    kpi_results = Column(JSON, nullable=True)
    compliance_results = Column(JSON, nullable=True)
    trend_results = Column(JSON, nullable=True)
    approval_classification = Column(JSON, nullable=True)
    approval_readiness = Column(JSON, nullable=True)
    unified_report = Column(JSON, nullable=True)
    
    # Data source tracking (metadata only - no special logic branching)
    # "user" = uploaded PDFs, "system" = pre-seeded historical data
    data_source = Column(String, default="user")

class Block(Base):
    __tablename__ = "blocks"
    
    id = Column(String, primary_key=True)  # block_id
    batch_id = Column(String, index=True)
    block_type = Column(String, index=True)
    data = Column(JSON)  # extracted_data
    confidence = Column(Float, default=0.0)
    extraction_confidence = Column(Float, default=0.0)
    evidence_snippet = Column(Text)
    evidence_page = Column(Integer, nullable=True)
    source_doc = Column(String)  # filename
    
    # Quality flags
    is_outdated = Column(Integer, default=0)  # 0 or 1
    is_low_quality = Column(Integer, default=0)
    is_invalid = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class File(Base):
    __tablename__ = "files"
    
    id = Column(String, primary_key=True)  # file_id
    batch_id = Column(String, index=True)
    filename = Column(String)
    filepath = Column(String)
    file_size = Column(Integer)
    document_hash = Column(String, index=True)  # SHA256 hash for duplicate detection
    uploaded_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class ComplianceFlag(Base):
    __tablename__ = "compliance_flags"
    
    id = Column(String, primary_key=True)
    batch_id = Column(String, index=True)
    severity = Column(String)  # "low", "medium", "high"
    message = Column(Text)
    title = Column(String)
    reason = Column(Text)
    recommendation = Column(Text, nullable=True)


class ApprovalClassification(Base):
    __tablename__ = "approval_classification"
    
    id = Column(String, primary_key=True)
    batch_id = Column(String, index=True)
    category = Column(String)  # aicte, ugc, mixed
    subtype = Column(String)   # new, renewal, unknown
    signals = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class ApprovalRequiredDocument(Base):
    __tablename__ = "approval_required_documents"
    
    id = Column(String, primary_key=True)
    batch_id = Column(String, index=True)
    category = Column(String)
    required_key = Column(String)
    present = Column(Integer, default=0)  # 0/1
    confidence = Column(Float, default=0.0)
    evidence = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class ComparisonCache(Base):
    __tablename__ = "comparison_cache"
    
    id = Column(String, primary_key=True)
    compare_key = Column(String, unique=True, index=True)
    batch_ids = Column(Text)  # comma-separated list
    payload = Column(JSON)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class PipelineCache(Base):
    """
    Generic pipeline cache for expensive steps (embeddings, KPIs, unified report, etc.).
    Cached payloads are JSON blobs with a simple TTL-based expiry.
    """
    __tablename__ = "pipeline_cache"

    id = Column(String, primary_key=True)
    cache_key = Column(String, unique=True, index=True)
    payload = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime, nullable=True)


class HistoricalKPI(Base):
    """Historical AICTE/UGC national KPI benchmarks by year."""
    __tablename__ = "historical_kpis"
    
    year = Column(Integer, primary_key=True)
    metrics = Column(JSON, nullable=False)  # avg_fsr, avg_infra, etc.
    source = Column(String, default="AICTE/UGC")  # Data source
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class DocumentHashCache(Base):
    """Cache of document hashes for deduplication."""
    __tablename__ = "document_hash_cache"
    
    id = Column(String, primary_key=True)
    batch_id = Column(String, index=True)
    file_hash = Column(String, index=True)  # SHA256 hash
    filename = Column(String)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# Helpful composite indexes for performance
Index("idx_blocks_batch_type", Block.batch_id, Block.block_type)
Index("idx_compliance_flags_batch", ComplianceFlag.batch_id)
Index("idx_approval_required_docs_batch", ApprovalRequiredDocument.batch_id)
Index("idx_batch_status", Batch.status)
Index("idx_batch_institution_dept_year", Batch.institution_name, Batch.department_name, Batch.academic_year)
Index("idx_batch_invalid_status", Batch.is_invalid, Batch.status)
Index("idx_batch_user", Batch.user_id)
Index("idx_batch_institution", Batch.institution_id)
Index("idx_batch_department", Batch.department_id)
Index("idx_user_institution", User.institution_id)
Index("idx_user_department", User.department_id)
Index("idx_department_institution", Department.institution_id)

# Create tables
def init_db():
    """Initialize database tables"""
    Base.metadata.create_all(bind=engine)
    if DB_TYPE == "postgresql":
        logger.info("PostgreSQL database initialized (Supabase)")
    else:
        logger.info(f"SQLite database initialized at {DB_PATH}")

def get_db() -> Session:
    """Get database session"""
    db = SessionLocal()
    try:
        return db
    finally:
        pass  # Don't close here, caller should close

def close_db(db: Session):
    """Close database session"""
    db.close()

# Import all models to ensure they're registered
from models.gov_document import GovDocument

# Note: init_db() is called from main.py after .env file is loaded
# Do not call init_db() at module level to avoid connecting before .env is loaded
