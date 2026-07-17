from datetime import datetime, timezone
import uuid

from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.db.session import Base


class ServerKnowledgeDocument(Base):
    """
    Registro por documento de Google Drive indexado en la base de
    conocimiento de SERVIDORES (memoria/RAM, estado). Espejo de
    KnowledgeDocument pero completamente independiente: carpeta de Drive,
    colección de ChromaDB y tabla propias, para no mezclar la búsqueda
    semántica de servidores con la de soporte general.
    """

    __tablename__ = "server_knowledge_documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Identidad en Google Drive.
    file_id = Column(String(255), unique=True, nullable=False, index=True)
    file_name = Column(String(500), nullable=False)
    doc_type = Column(String(50), nullable=True)          # google_doc | pdf | xlsx | text | docx ...
    mime_type = Column(String(255), nullable=True)
    drive_modified_at = Column(String(100), nullable=True)  # modifiedTime que reporta Drive

    # Huella del contenido para detectar cambios (sha256 del texto extraído).
    content_hash = Column(String(64), nullable=True, index=True)

    # Resultado del último procesamiento.
    chunk_count = Column(Integer, default=0)
    status = Column(String(30), default="pending", index=True)  # pending | indexed | failed | skipped
    error_message = Column(Text, nullable=True)

    # Trazabilidad temporal.
    last_indexed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )