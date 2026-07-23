from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging_config import get_logger
from app.models.server_knowledge_document import ServerKnowledgeDocument
from app.services.gdrive_service import gdrive_service
from app.services.vertex.embeddings_service import embeddings_service
from app.services.vertex.gemini_text_service import gemini_text_service

logger = get_logger(__name__, service="servers_kb")

SERVERS_RAG_SYSTEM = """Eres BOTIQ respondiendo sobre el estado de servidores e infraestructura.

Base de conocimiento disponible (cada bloque es el estado más reciente de UN servidor):
{knowledge_context}

Reglas:
1. Responde SOLO con base en el contexto recibido: hostname, sistema operativo, CPU, RAM, disco, estado, reinicio y notas.
2. Si citas una fuente, menciona únicamente el nombre del documento en una línea final, sin enlaces ni identificadores.
3. Si el contexto no es suficiente, está desactualizado o el servidor no aparece, dilo claramente.
4. Sé breve, técnico y directo.
5. No inventes servidores, valores, fechas ni umbrales.
6. Si el servidor figura como "Inalcanzable", dilo explícitamente y no supongas la causa.
"""

NO_KNOWLEDGE = (
    "No encontré información reciente sobre ese servidor en la base de conocimiento. "
    "Verifica el hostname exacto o consulta con el equipo de infraestructura."
)

_FIELD_ALIASES = {
    "servidor hostname": "hostname",
    "servidor": "hostname",
    "hostname": "hostname",
    "ultima actualizacion": "updated_at",
    "sistema operativo": "operating_system",
    "cpu": "cpu_pct",
    "cpu porcentaje": "cpu_pct",
    "ram total gb": "ram_total_gb",
    "ram usada gb": "ram_used_gb",
    "ram disponible gb": "ram_available_gb",
    "ram": "ram_pct",
    "ram porcentaje": "ram_pct",
    "disco total gb": "disk_total_gb",
    "disco usado gb": "disk_used_gb",
    "disco disponible gb": "disk_available_gb",
    "disco": "disk_pct",
    "disco porcentaje": "disk_pct",
    "estado general": "status",
    "estado": "status",
    "ultimo reinicio": "last_restart",
    "notas acciones": "notes",
    "notas": "notes",
}

_STATUS_LABELS = {
    "saludable": "Saludable",
    "advertencia": "Advertencia",
    "critico": "Crítico",
    "critical": "Crítico",
    "inalcanzable": "Inalcanzable",
    "unreachable": "Inalcanzable",
}

_SERVER_CONTEXT_TERMS = {
    "servidor",
    "servidores",
    "server",
    "servers",
    "hostname",
    "infraestructura",
}

_SERVER_QUERY_HEALTH_TERMS = {
    "estado",
    "estado general",
    "salud",
    "inventario",
    "ultimo reinicio",
    "último reinicio",
    "reinicio",
    "uptime",
    "inalcanzable",
    "inalcanzables",
    "cpu",
    "ram",
    "memoria",
    "disco",
    "saludable",
    "saludables",
    "advertencia",
    "advertencias",
    "critico",
    "crítico",
    "criticos",
    "críticos",
}

_SERVER_QUERY_METRIC_TERMS = {
    "cpu",
    "ram",
    "memoria",
    "disco",
    "saludable",
    "saludables",
    "advertencia",
    "advertencias",
    "critico",
    "crítico",
    "criticos",
    "críticos",
}

_GLOBAL_QUERY_TERMS = {
    "todos",
    "servidores",
    "infraestructura",
    "todas",
    "resumen",
    "general",
    "cuantos",
    "cuántos",
    "cuales",
    "cuáles",
    "lista",
    "listar",
    "top",
    "peores",
    "mayor",
    "mayores",
    "superior",
    "superiores",
    "encima",
    "criticos",
    "críticos",
    "inalcanzables",
    "saludables",
    "advertencias",
}

_HOSTNAME_STOPWORDS = {
    "esta",
    "está",
    "estan",
    "están",
    "tiene",
    "tienen",
    "con",
    "sin",
    "caido",
    "caído",
    "lento",
    "critico",
    "crítico",
    "saludable",
}


def _strip_leaked_context_markers(text: str) -> str:
    if not text:
        return text
    cleaned = re.sub(r"\[Fuente:[^\]]*\]\s*", "", text)
    cleaned = re.sub(r"#{1,3}\s*Documento:.*", "", cleaned)
    return cleaned.strip()


class ServersKnowledgeService:
    """RAG independiente para el inventario y la salud de servidores.

    La hoja configurada se indexa fila por fila. Cada fila representa un
    servidor completo y se conserva en una colección Chroma separada. Para
    consultas globales (conteos, críticos, inalcanzables o umbrales) el
    servicio analiza todos los registros de manera determinística; para una
    consulta de un hostname exacto responde directamente sin depender de que
    Gemini realice cálculos; y para preguntas abiertas usa recuperación
    semántica más Gemini, restringido al contexto recuperado.
    """

    def __init__(self) -> None:
        self._collection = None
        self._snapshot_cache: List[Dict[str, Any]] = []
        self._snapshot_cache_at: Optional[datetime] = None

    def _get_collection(self):
        if self._collection is None:
            import chromadb

            client = chromadb.HttpClient(
                host=settings.CHROMA_HOST,
                port=settings.CHROMA_PORT,
            )
            self._collection = client.get_or_create_collection(
                name=settings.CHROMA_SERVERS_COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )
        return self._collection

    def is_configured(self) -> bool:
        return gdrive_service.is_configured(
            folder_ids=settings.get_servers_folder_ids(),
            file_ids=settings.get_servers_file_ids(),
        )

    def _invalidate_snapshot_cache(self) -> None:
        self._snapshot_cache = []
        self._snapshot_cache_at = None

    @staticmethod
    def _normalize_text(value: Any) -> str:
        text = str(value or "").strip().lower()
        text = "".join(
            char
            for char in unicodedata.normalize("NFD", text)
            if unicodedata.category(char) != "Mn"
        )
        text = re.sub(r"[^a-z0-9]+", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _hash_text(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()

    @classmethod
    def _canonical_field(cls, raw_label: str) -> str:
        normalized = cls._normalize_text(raw_label)
        return _FIELD_ALIASES.get(normalized, normalized.replace(" ", "_"))

    @classmethod
    def _status_key(cls, value: Any) -> str:
        normalized = cls._normalize_text(value)
        if normalized in {"critico", "critical"}:
            return "critical"
        if normalized in {"advertencia", "warning", "degradado", "degraded"}:
            return "warning"
        if normalized in {"saludable", "healthy", "ok", "operativo"}:
            return "healthy"
        if normalized in {"inalcanzable", "unreachable", "offline", "down"}:
            return "unreachable"
        return "unknown"

    @classmethod
    def _status_label(cls, value: Any) -> str:
        normalized = cls._normalize_text(value)
        return _STATUS_LABELS.get(normalized, str(value or "Sin dato"))

    @staticmethod
    def _parse_percentage(value: Any) -> Optional[float]:
        if value is None:
            return None
        match = re.search(r"-?\d+(?:[\.,]\d+)?", str(value))
        if not match:
            return None
        try:
            return float(match.group(0).replace(",", "."))
        except ValueError:
            return None

    @staticmethod
    def _parse_timestamp(value: Any) -> Optional[datetime]:
        raw = str(value or "").strip()
        if not raw or raw.lower() in {"sin dato", "n/a", "none"}:
            return None

        formats = (
            "%d-%m-%Y %H:%M:%S",
            "%d/%m/%Y %H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%S.%f",
        )
        parsed: Optional[datetime] = None
        for fmt in formats:
            try:
                parsed = datetime.strptime(raw.replace("Z", ""), fmt)
                break
            except ValueError:
                continue

        if parsed is None:
            try:
                parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            except ValueError:
                return None

        if parsed.tzinfo is None:
            try:
                parsed = parsed.replace(tzinfo=ZoneInfo(settings.APP_TIMEZONE))
            except Exception:  # noqa: BLE001
                parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    @staticmethod
    def _row_to_block(headers: List[str], row: List[str]) -> str:
        parts: List[str] = []
        for index, header in enumerate(headers):
            value = row[index].strip() if index < len(row) and row[index] is not None else ""
            parts.append(f"{header.strip()}: {value or 'sin dato'}")
        return " | ".join(parts)

    @classmethod
    def _parse_server_block(
        cls,
        block: str,
        *,
        source: str = "Inventario de servidores",
    ) -> Dict[str, Any]:
        record: Dict[str, Any] = {"source": source, "raw_block": block}
        for item in re.split(r"\s+\|\s+", block or ""):
            if ":" not in item:
                continue
            label, value = item.split(":", 1)
            record[cls._canonical_field(label)] = value.strip()

        hostname = str(record.get("hostname") or "").strip()
        record["hostname"] = hostname
        record["status_key"] = cls._status_key(record.get("status"))
        record["status_label"] = cls._status_label(record.get("status"))
        record["cpu_value"] = cls._parse_percentage(record.get("cpu_pct"))
        record["ram_value"] = cls._parse_percentage(record.get("ram_pct"))
        record["disk_value"] = cls._parse_percentage(record.get("disk_pct"))
        record["updated_datetime"] = cls._parse_timestamp(record.get("updated_at"))
        return record

    async def _extract_row_chunks(self, doc: Dict) -> Optional[List[str]]:
        gid = settings.GDRIVE_SERVERS_SHEET_GID.strip()
        if not gid or doc.get("doc_type") != "google_sheet":
            return None

        sheet = gdrive_service.get_sheet_tab_rows(doc["file_id"], gid)
        if not sheet or not sheet.get("rows"):
            logger.warning(
                "sheet_tab_empty_or_unreadable",
                doc=doc.get("name"),
                gid=gid,
            )
            return None

        headers = sheet["headers"]
        chunks = [
            self._row_to_block(headers, row)
            for row in sheet["rows"]
            if any(str(cell or "").strip() for cell in row)
        ]
        logger.info(
            "sheet_tab_read",
            doc=doc.get("name"),
            gid=gid,
            rows=len(chunks),
            sheet_title=sheet.get("sheet_title"),
        )
        return chunks

    async def _extract_text(self, doc: Dict) -> str:
        if doc.get("doc_type") == "pdf" and doc.get("bytes"):
            pdf_bytes = doc["bytes"]
            try:
                import io
                from pypdf import PdfReader

                reader = PdfReader(io.BytesIO(pdf_bytes))
                pages = []
                for index, page in enumerate(reader.pages, start=1):
                    text = page.extract_text() or ""
                    if text.strip():
                        pages.append(f"[Página {index}]\n{text.strip()}")
                local_text = "\n\n".join(pages).strip()
                if local_text:
                    return local_text
            except Exception as exc:  # noqa: BLE001
                logger.warning("pdf_extraction_error", doc=doc.get("name"), error=str(exc))

            try:
                from app.services.vertex.document_ai_service import document_ai_service

                text = await document_ai_service.process_pdf(pdf_bytes)
                if text and text.strip():
                    return text.strip()
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "documentai_extraction_error",
                    doc=doc.get("name"),
                    error=str(exc),
                )
            return ""

        return doc.get("content", "")

    @staticmethod
    def _metadata_for_chunk(doc: Dict, chunk: str, index: int, total: int) -> Dict[str, Any]:
        metadata: Dict[str, Any] = {
            "file_id": doc["file_id"],
            "file_name": doc["name"],
            "doc_type": doc.get("doc_type", ""),
            "modified_at": doc.get("modified_at", ""),
            "chunk_index": index,
            "total_chunks": total,
        }
        record = ServersKnowledgeService._parse_server_block(
            chunk,
            source=doc["name"],
        )
        scalar_fields = {
            "hostname": record.get("hostname"),
            "server_status": record.get("status_label"),
            "updated_at": record.get("updated_at"),
            "cpu_pct": record.get("cpu_value"),
            "ram_pct": record.get("ram_value"),
            "disk_pct": record.get("disk_value"),
        }
        for key, value in scalar_fields.items():
            if value is not None and value != "":
                metadata[key] = value
        return metadata

    @staticmethod
    def _delete_chunks_for_file(collection, file_id: str) -> None:
        try:
            collection.delete(where={"file_id": file_id})
        except Exception as exc:  # noqa: BLE001
            logger.warning("chroma_delete_failed", file_id=file_id, error=str(exc))

    async def _index_document(
        self,
        collection,
        doc: Dict,
        text: str,
        row_chunks: Optional[List[str]] = None,
    ) -> int:
        chunks = row_chunks if row_chunks is not None else self._chunk_text(text)
        self._delete_chunks_for_file(collection, doc["file_id"])

        for index, chunk in enumerate(chunks):
            chunk_id = f"{doc['file_id']}_chunk_{index}"
            embedding = await embeddings_service.embed_text(chunk)
            collection.upsert(
                ids=[chunk_id],
                embeddings=[embedding],
                documents=[chunk],
                metadatas=[self._metadata_for_chunk(doc, chunk, index, len(chunks))],
            )
        self._invalidate_snapshot_cache()
        return len(chunks)

    async def sync_knowledge_base(self, db: AsyncSession, force: bool = False) -> Dict:
        folder_ids = settings.get_servers_folder_ids()
        file_ids = settings.get_servers_file_ids()

        if not gdrive_service.is_configured(folder_ids=folder_ids, file_ids=file_ids):
            return {
                "status": "error",
                "message": (
                    "Google Drive no configurado para la base de servidores. "
                    "Verifica GDRIVE_SERVERS_FOLDER_ID(S), "
                    "GDRIVE_SERVERS_FILE_ID(S) y service-account.json."
                ),
                "documents_processed": 0,
            }

        documents = await gdrive_service.get_all_documents_content_with_type(
            folder_ids=folder_ids,
            file_ids=file_ids,
        )
        collection = self._get_collection()

        existing_rows = (
            await db.execute(select(ServerKnowledgeDocument))
        ).scalars().all()
        by_file = {row.file_id: row for row in existing_rows}
        drive_file_ids = set()

        indexed = updated = skipped = errors = 0

        for doc in documents:
            file_id = doc["file_id"]
            drive_file_ids.add(file_id)
            row = by_file.get(file_id)

            try:
                row_chunks = await self._extract_row_chunks(doc)
                text_for_hash = (
                    "\n".join(row_chunks)
                    if row_chunks is not None
                    else await self._extract_text(doc)
                )

                if not text_for_hash.strip():
                    logger.warning("doc_no_content", doc=doc["name"])
                    self._upsert_doc_record(
                        db,
                        row,
                        doc,
                        content_hash=None,
                        chunk_count=0,
                        status="failed",
                        error="Sin contenido extraíble",
                    )
                    errors += 1
                    continue

                new_hash = self._hash_text(text_for_hash)
                unchanged = (
                    row is not None
                    and row.status == "indexed"
                    and row.content_hash == new_hash
                )

                if unchanged and not force:
                    self._touch_doc_record(row, status="indexed")
                    skipped += 1
                    logger.debug("doc_skipped_unchanged", doc=doc["name"])
                    continue

                chunk_count = await self._index_document(
                    collection,
                    doc,
                    text_for_hash,
                    row_chunks=row_chunks,
                )
                self._upsert_doc_record(
                    db,
                    row,
                    doc,
                    content_hash=new_hash,
                    chunk_count=chunk_count,
                    status="indexed",
                    error=None,
                    mark_indexed=True,
                )
                if row is None:
                    indexed += 1
                    action = "new"
                else:
                    updated += 1
                    action = "reindexed"
                logger.info(
                    "doc_indexed",
                    doc=doc["name"],
                    chunks=chunk_count,
                    action=action,
                )
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "doc_processing_error",
                    doc=doc.get("name"),
                    error=str(exc),
                )
                self._upsert_doc_record(
                    db,
                    row,
                    doc,
                    content_hash=None,
                    chunk_count=(row.chunk_count if row else 0),
                    status="failed",
                    error=str(exc),
                )
                errors += 1

        removed = 0
        for file_id, row in by_file.items():
            if file_id not in drive_file_ids:
                self._delete_chunks_for_file(collection, file_id)
                await db.delete(row)
                removed += 1
                logger.info("doc_removed_from_index", doc=row.file_name)

        if removed:
            self._invalidate_snapshot_cache()

        await db.commit()
        return {
            "status": "success",
            "mode": "full" if force else "incremental",
            "documents_in_drive": len(documents),
            "indexed_new": indexed,
            "reindexed": updated,
            "skipped_unchanged": skipped,
            "removed": removed,
            "errors": errors,
            "total_chunks": collection.count(),
        }

    async def reindex_document(self, db: AsyncSession, file_id: str) -> Dict:
        folder_ids = settings.get_servers_folder_ids()
        file_ids = settings.get_servers_file_ids()

        if not gdrive_service.is_configured(folder_ids=folder_ids, file_ids=file_ids):
            return {
                "status": "error",
                "message": "Google Drive no configurado para servidores",
            }

        documents = await gdrive_service.get_all_documents_content_with_type(
            folder_ids=folder_ids,
            file_ids=file_ids,
        )
        doc = next((item for item in documents if item["file_id"] == file_id), None)
        if not doc:
            return {
                "status": "not_found",
                "message": "Documento no encontrado en Drive",
            }

        collection = self._get_collection()
        row = (
            await db.execute(
                select(ServerKnowledgeDocument).where(
                    ServerKnowledgeDocument.file_id == file_id
                )
            )
        ).scalar_one_or_none()

        try:
            row_chunks = await self._extract_row_chunks(doc)
            text_for_hash = (
                "\n".join(row_chunks)
                if row_chunks is not None
                else await self._extract_text(doc)
            )
            if not text_for_hash.strip():
                self._upsert_doc_record(
                    db,
                    row,
                    doc,
                    content_hash=None,
                    chunk_count=0,
                    status="failed",
                    error="Sin contenido extraíble",
                )
                await db.commit()
                return {"status": "failed", "message": "Sin contenido extraíble"}

            chunk_count = await self._index_document(
                collection,
                doc,
                text_for_hash,
                row_chunks=row_chunks,
            )
            self._upsert_doc_record(
                db,
                row,
                doc,
                content_hash=self._hash_text(text_for_hash),
                chunk_count=chunk_count,
                status="indexed",
                error=None,
                mark_indexed=True,
            )
            await db.commit()
            return {
                "status": "indexed",
                "file_name": doc["name"],
                "chunk_count": chunk_count,
                "total_chunks": collection.count(),
            }
        except Exception as exc:  # noqa: BLE001
            self._upsert_doc_record(
                db,
                row,
                doc,
                content_hash=None,
                chunk_count=(row.chunk_count if row else 0),
                status="failed",
                error=str(exc),
            )
            await db.commit()
            return {"status": "failed", "message": str(exc)}

    async def list_documents(self, db: AsyncSession) -> List[Dict]:
        rows = (
            await db.execute(
                select(ServerKnowledgeDocument).order_by(
                    ServerKnowledgeDocument.file_name
                )
            )
        ).scalars().all()
        return [
            {
                "file_id": row.file_id,
                "file_name": row.file_name,
                "doc_type": row.doc_type,
                "chunk_count": row.chunk_count or 0,
                "status": row.status,
                "error_message": row.error_message,
                "drive_modified_at": row.drive_modified_at,
                "last_indexed_at": (
                    row.last_indexed_at.isoformat()
                    if row.last_indexed_at
                    else None
                ),
            }
            for row in rows
        ]

    def _upsert_doc_record(
        self,
        db: AsyncSession,
        row: Optional[ServerKnowledgeDocument],
        doc: Dict,
        content_hash: Optional[str],
        chunk_count: int,
        status: str,
        error: Optional[str],
        mark_indexed: bool = False,
    ) -> None:
        now = datetime.now(timezone.utc)
        if row is None:
            row = ServerKnowledgeDocument(file_id=doc["file_id"])
            db.add(row)
        row.file_name = doc["name"]
        row.doc_type = doc.get("doc_type")
        row.mime_type = doc.get("mime_type")
        row.drive_modified_at = doc.get("modified_at")
        row.content_hash = (
            content_hash if content_hash is not None else row.content_hash
        )
        row.chunk_count = chunk_count
        row.status = status
        row.error_message = error
        if mark_indexed:
            row.last_indexed_at = now
        row.updated_at = now

    @staticmethod
    def _touch_doc_record(row: ServerKnowledgeDocument, status: str) -> None:
        row.status = status
        row.updated_at = datetime.now(timezone.utc)

    def _get_all_server_records(self) -> List[Dict[str, Any]]:
        """Lee todos los chunks del índice y los convierte en registros.

        Esto evita usar top-k para preguntas globales. El snapshot se mantiene
        en memoria durante unos segundos para que una conversación normal no
        descargue todos los chunks desde ChromaDB en cada mensaje. La caché se
        invalida inmediatamente después de indexar o eliminar contenido.
        """
        now = datetime.now(timezone.utc)
        if self._snapshot_cache and self._snapshot_cache_at:
            age_seconds = (now - self._snapshot_cache_at).total_seconds()
            if age_seconds < settings.SERVERS_KB_SNAPSHOT_CACHE_SECONDS:
                return list(self._snapshot_cache)

        try:
            collection = self._get_collection()
            if collection.count() == 0:
                self._invalidate_snapshot_cache()
                return []
            payload = collection.get(include=["documents", "metadatas"])
            documents = payload.get("documents") or []
            metadatas = payload.get("metadatas") or []
            records: Dict[str, Dict[str, Any]] = {}

            for index, block in enumerate(documents):
                metadata = metadatas[index] if index < len(metadatas) else {}
                source = (metadata or {}).get("file_name", "Inventario de servidores")
                record = self._parse_server_block(block, source=source)
                hostname = str(record.get("hostname") or "").strip()
                if not hostname or self._normalize_text(hostname) == "sin dato":
                    continue
                records[hostname.upper()] = record

            snapshot = sorted(
                records.values(),
                key=lambda item: str(item.get("hostname") or "").upper(),
            )
            self._snapshot_cache = snapshot
            self._snapshot_cache_at = now
            return list(snapshot)
        except Exception as exc:  # noqa: BLE001
            logger.error("servers_snapshot_error", error=str(exc))
            return []

    @staticmethod
    def _hostname_matches(query: str, hostname: str) -> bool:
        query_upper = query.upper()
        hostname_upper = hostname.upper().strip()
        if not hostname_upper:
            return False
        pattern = rf"(?<![A-Z0-9_-]){re.escape(hostname_upper)}(?![A-Z0-9_-])"
        return re.search(pattern, query_upper) is not None

    def _find_exact_records(
        self,
        query: str,
        records: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        matches = [
            record
            for record in records
            if self._hostname_matches(query, str(record.get("hostname") or ""))
        ]
        return sorted(
            matches,
            key=lambda item: len(str(item.get("hostname") or "")),
            reverse=True,
        )

    @staticmethod
    def _extract_hostname_candidate(query: str) -> Optional[str]:
        match = re.search(
            r"\b(?:servidor|server|hostname)\s+([A-Za-z0-9._-]{2,80})",
            query,
            flags=re.IGNORECASE,
        )
        if not match:
            return None
        candidate = match.group(1).strip(".,;:!?()[]{}")
        if candidate.lower() in _HOSTNAME_STOPWORDS:
            return None
        return candidate

    def is_server_health_query(self, query: str) -> bool:
        """Determina si la fachada del chat debe usar esta KB especializada."""
        normalized = self._normalize_text(query)
        if not normalized:
            return False

        records = self._get_all_server_records()
        if records and self._find_exact_records(query, records):
            return True

        context_hits = sum(
            1 for term in _SERVER_CONTEXT_TERMS if term in normalized
        )
        health_hits = sum(
            1 for term in _SERVER_QUERY_HEALTH_TERMS if term in normalized
        )
        global_hits = sum(
            1 for term in _GLOBAL_QUERY_TERMS if term in normalized
        )

        # Consultas como "Dame un resumen de todos los servidores" expresan
        # claramente un análisis global aunque no incluyan las palabras
        # "estado" o "salud". Exigimos contexto de servidores + término
        # global para no interceptar preguntas técnicas genéricas como
        # "¿Cómo configuro un certificado en un servidor?".
        if context_hits > 0 and (health_hits > 0 or global_hits > 0):
            return True

        # Preguntas abreviadas como "¿cuáles están críticos?" no incluyen la
        # palabra servidor, pero dentro de una sesión de soporte son claras si
        # combinan una métrica/estado con un término global.
        metric_hits = sum(
            1 for term in _SERVER_QUERY_METRIC_TERMS if term in normalized
        )
        return metric_hits > 0 and global_hits > 0

    def _is_global_query(
        self,
        query: str,
        exact_records: List[Dict[str, Any]],
    ) -> bool:
        if exact_records:
            return False
        normalized = self._normalize_text(query)
        return any(term in normalized for term in _GLOBAL_QUERY_TERMS)

    @staticmethod
    def _extract_threshold(query: str, default: float) -> float:
        match = re.search(
            r"(?:>|mayor(?:es)?\s+(?:a|de)|superior(?:es)?\s+(?:a|de)|"
            r"por\s+encima\s+de)\s*(\d+(?:[\.,]\d+)?)\s*%?",
            query,
            flags=re.IGNORECASE,
        )
        if not match:
            standalone = re.search(r"(\d+(?:[\.,]\d+)?)\s*%", query)
            match = standalone
        if not match:
            return default
        try:
            return float(match.group(1).replace(",", "."))
        except ValueError:
            return default

    @staticmethod
    def _source_names(records: List[Dict[str, Any]]) -> List[str]:
        return sorted(
            {
                str(record.get("source") or "Inventario de servidores")
                for record in records
            }
        )

    def _freshness_payload(self, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        timestamps = [
            record.get("updated_datetime")
            for record in records
            if record.get("updated_datetime") is not None
        ]
        if not timestamps:
            return {
                "latest_update": None,
                "age_minutes": None,
                "stale": True,
            }

        latest = max(timestamps)
        age_minutes = max(
            0,
            int((datetime.now(timezone.utc) - latest).total_seconds() / 60),
        )
        return {
            "latest_update": latest.isoformat(),
            "age_minutes": age_minutes,
            "stale": age_minutes > settings.SERVERS_KB_STALE_AFTER_MINUTES,
        }

    def _format_server_detail(self, record: Dict[str, Any]) -> str:
        lines = [
            f"### {record.get('hostname') or 'Servidor sin nombre'}",
            f"- **Estado general:** {record.get('status_label') or 'Sin dato'}",
            f"- **Última actualización:** {record.get('updated_at') or 'Sin dato'}",
            f"- **Sistema operativo:** {record.get('operating_system') or 'Sin dato'}",
            f"- **CPU:** {record.get('cpu_pct') or 'Sin dato'}",
            (
                "- **RAM:** "
                f"{record.get('ram_pct') or 'Sin dato'} usada "
                f"({record.get('ram_used_gb') or 'Sin dato'} GB de "
                f"{record.get('ram_total_gb') or 'Sin dato'} GB; "
                f"disponible {record.get('ram_available_gb') or 'Sin dato'} GB)"
            ),
            (
                "- **Disco:** "
                f"{record.get('disk_pct') or 'Sin dato'} usado "
                f"({record.get('disk_used_gb') or 'Sin dato'} GB de "
                f"{record.get('disk_total_gb') or 'Sin dato'} GB; "
                f"disponible {record.get('disk_available_gb') or 'Sin dato'} GB)"
            ),
            f"- **Último reinicio:** {record.get('last_restart') or 'Sin dato'}",
            f"- **Notas / acciones:** {record.get('notes') or 'Sin observaciones registradas'}",
        ]

        if record.get("status_key") == "unreachable":
            lines.append(
                "- **Interpretación:** el inventario lo reporta como inalcanzable; "
                "no hay métricas suficientes para confirmar su consumo actual."
            )
        return "\n".join(lines)

    @staticmethod
    def _format_server_names(records: List[Dict[str, Any]], limit: int = 20) -> str:
        names = [str(record.get("hostname")) for record in records[:limit]]
        if not names:
            return "Ninguno"
        suffix = f" y {len(records) - limit} más" if len(records) > limit else ""
        return ", ".join(names) + suffix

    def _metric_report(
        self,
        query: str,
        records: List[Dict[str, Any]],
        *,
        metric_key: str,
        label: str,
        default_threshold: float,
    ) -> Dict[str, Any]:
        threshold = self._extract_threshold(query, default_threshold)
        matches = [
            record
            for record in records
            if record.get(metric_key) is not None
            and float(record[metric_key]) >= threshold
        ]
        matches.sort(key=lambda item: float(item.get(metric_key) or 0), reverse=True)

        if matches:
            detail = "\n".join(
                f"- **{record['hostname']}**: {float(record[metric_key]):g}% "
                f"({record.get('status_label') or 'Sin estado'})"
                for record in matches[:20]
            )
            text = (
                f"### Servidores con {label} igual o superior a {threshold:g}%\n"
                f"Encontré **{len(matches)}** servidor(es):\n{detail}"
            )
        else:
            text = (
                f"No encontré servidores con {label} igual o superior a "
                f"{threshold:g}% en el inventario indexado."
            )

        return {
            "text": text,
            "matched": matches,
            "threshold": threshold,
            "metric": label,
        }

    def _build_global_health_response(
        self,
        query: str,
        records: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        normalized = self._normalize_text(query)

        if "ram" in normalized or "memoria" in normalized:
            report = self._metric_report(
                query,
                records,
                metric_key="ram_value",
                label="RAM",
                default_threshold=settings.SERVERS_KB_RAM_ALERT_PCT,
            )
            mode = "ram_threshold"
        elif "cpu" in normalized:
            report = self._metric_report(
                query,
                records,
                metric_key="cpu_value",
                label="CPU",
                default_threshold=settings.SERVERS_KB_CPU_ALERT_PCT,
            )
            mode = "cpu_threshold"
        elif "disco" in normalized:
            report = self._metric_report(
                query,
                records,
                metric_key="disk_value",
                label="disco",
                default_threshold=settings.SERVERS_KB_DISK_ALERT_PCT,
            )
            mode = "disk_threshold"
        else:
            by_status = {
                "healthy": [r for r in records if r.get("status_key") == "healthy"],
                "warning": [r for r in records if r.get("status_key") == "warning"],
                "critical": [r for r in records if r.get("status_key") == "critical"],
                "unreachable": [r for r in records if r.get("status_key") == "unreachable"],
                "unknown": [r for r in records if r.get("status_key") == "unknown"],
            }

            if "inalcanzable" in normalized:
                selected = by_status["unreachable"]
                report = {
                    "text": (
                        f"Hay **{len(selected)}** servidor(es) inalcanzable(s): "
                        f"{self._format_server_names(selected)}."
                    ),
                    "matched": selected,
                }
                mode = "unreachable"
            elif "critico" in normalized or "criticos" in normalized:
                selected = by_status["critical"]
                report = {
                    "text": (
                        f"Hay **{len(selected)}** servidor(es) en estado crítico: "
                        f"{self._format_server_names(selected)}."
                    ),
                    "matched": selected,
                }
                mode = "critical"
            elif "advertencia" in normalized:
                selected = by_status["warning"]
                report = {
                    "text": (
                        f"Hay **{len(selected)}** servidor(es) en advertencia: "
                        f"{self._format_server_names(selected)}."
                    ),
                    "matched": selected,
                }
                mode = "warning"
            elif "saludable" in normalized:
                selected = by_status["healthy"]
                report = {
                    "text": (
                        f"Hay **{len(selected)}** servidor(es) saludables: "
                        f"{self._format_server_names(selected)}."
                    ),
                    "matched": selected,
                }
                mode = "healthy"
            else:
                cpu_alerts = [
                    r
                    for r in records
                    if r.get("cpu_value") is not None
                    and float(r["cpu_value"]) >= settings.SERVERS_KB_CPU_ALERT_PCT
                ]
                ram_alerts = [
                    r
                    for r in records
                    if r.get("ram_value") is not None
                    and float(r["ram_value"]) >= settings.SERVERS_KB_RAM_ALERT_PCT
                ]
                disk_alerts = [
                    r
                    for r in records
                    if r.get("disk_value") is not None
                    and float(r["disk_value"]) >= settings.SERVERS_KB_DISK_ALERT_PCT
                ]

                report = {
                    "text": (
                        "### Resumen general de salud de servidores\n"
                        f"- **Total:** {len(records)}\n"
                        f"- **Saludables:** {len(by_status['healthy'])}\n"
                        f"- **En advertencia:** {len(by_status['warning'])}\n"
                        f"- **Críticos:** {len(by_status['critical'])} "
                        f"({self._format_server_names(by_status['critical'], 10)})\n"
                        f"- **Inalcanzables:** {len(by_status['unreachable'])} "
                        f"({self._format_server_names(by_status['unreachable'], 10)})\n"
                        f"- **CPU ≥ {settings.SERVERS_KB_CPU_ALERT_PCT:g}%:** {len(cpu_alerts)}\n"
                        f"- **RAM ≥ {settings.SERVERS_KB_RAM_ALERT_PCT:g}%:** {len(ram_alerts)}\n"
                        f"- **Disco ≥ {settings.SERVERS_KB_DISK_ALERT_PCT:g}%:** {len(disk_alerts)}"
                    ),
                    "matched": by_status["critical"] + by_status["unreachable"],
                    "counts": {key: len(value) for key, value in by_status.items()},
                    "alerts": {
                        "cpu": len(cpu_alerts),
                        "ram": len(ram_alerts),
                        "disk": len(disk_alerts),
                    },
                }
                mode = "global_summary"

        freshness = self._freshness_payload(records)
        text = report["text"]
        if freshness["latest_update"]:
            text += (
                "\n\n**Última actualización detectada:** "
                f"{freshness['latest_update']}"
            )
        if freshness["stale"]:
            text += (
                "\n\n⚠️ **Advertencia de frescura:** los datos superan "
                f"{settings.SERVERS_KB_STALE_AFTER_MINUTES} minutos. "
                "La respuesta puede no representar el estado actual."
            )

        sources = self._source_names(records)
        if sources:
            text += f"\n\nFuente: {', '.join(sources)}"

        return {
            "text": text,
            "sources": sources,
            "avg_confidence": 1.0,
            "best_confidence": 1.0,
            "knowledge_gap": False,
            "tokens_used": 0,
            "response_time_ms": 0,
            "mode": mode,
            "structured_data": {
                "mode": mode,
                "total_servers": len(records),
                "matched_servers": [
                    record.get("hostname")
                    for record in report.get("matched", [])
                ],
                "freshness": freshness,
                "counts": report.get("counts"),
                "alerts": report.get("alerts"),
                "threshold": report.get("threshold"),
                "metric": report.get("metric"),
            },
        }

    async def retrieve_context(self, query: str, top_k: int = None) -> List[Dict]:
        top_k = top_k or settings.RAG_TOP_K
        try:
            collection = self._get_collection()
            if collection.count() == 0:
                return []

            embedding = await embeddings_service.embed_text(query)
            results = collection.query(
                query_embeddings=[embedding],
                n_results=min(top_k, collection.count()),
                include=["documents", "metadatas", "distances"],
            )

            chunks: List[Dict] = []
            if results["documents"] and results["documents"][0]:
                for document, metadata, distance in zip(
                    results["documents"][0],
                    results["metadatas"][0],
                    results["distances"][0],
                ):
                    chunks.append(
                        {
                            "content": document,
                            "source": metadata.get("file_name", "Desconocido"),
                            "relevance_score": max(0.0, 1 - distance),
                        }
                    )

            chunks.sort(key=lambda item: item["relevance_score"], reverse=True)
            return chunks
        except Exception as exc:  # noqa: BLE001
            logger.error("chroma_error", error=str(exc))
            return []

    async def generate_response(
        self,
        user_message: str,
        history: Optional[List[Dict]] = None,
    ) -> Dict:
        records = self._get_all_server_records()
        if not records:
            return {
                "text": NO_KNOWLEDGE,
                "sources": [],
                "avg_confidence": 0.0,
                "best_confidence": 0.0,
                "knowledge_gap": True,
                "tokens_used": 0,
                "response_time_ms": 0,
                "mode": "empty_index",
                "structured_data": {"mode": "empty_index", "total_servers": 0},
            }

        exact_records = self._find_exact_records(user_message, records)
        if exact_records:
            selected = exact_records[:5]
            text = "\n\n---\n\n".join(
                self._format_server_detail(record) for record in selected
            )
            freshness = self._freshness_payload(selected)
            if freshness["stale"]:
                text += (
                    "\n\n⚠️ Los datos consultados superan el límite de frescura de "
                    f"{settings.SERVERS_KB_STALE_AFTER_MINUTES} minutos."
                )
            sources = self._source_names(selected)
            if sources:
                text += f"\n\nFuente: {', '.join(sources)}"
            return {
                "text": text,
                "sources": sources,
                "avg_confidence": 1.0,
                "best_confidence": 1.0,
                "knowledge_gap": False,
                "tokens_used": 0,
                "response_time_ms": 0,
                "mode": "exact_hostname",
                "structured_data": {
                    "mode": "exact_hostname",
                    "total_servers": len(records),
                    "matched_servers": [
                        record.get("hostname") for record in selected
                    ],
                    "freshness": freshness,
                },
            }

        explicit_candidate = self._extract_hostname_candidate(user_message)
        if explicit_candidate:
            return {
                "text": (
                    f"No encontré el hostname **{explicit_candidate}** en el inventario "
                    "de servidores indexado. Verifica la escritura exacta."
                ),
                "sources": self._source_names(records),
                "avg_confidence": 0.0,
                "best_confidence": 0.0,
                "knowledge_gap": True,
                "tokens_used": 0,
                "response_time_ms": 0,
                "mode": "hostname_not_found",
                "structured_data": {
                    "mode": "hostname_not_found",
                    "candidate": explicit_candidate,
                    "total_servers": len(records),
                },
            }

        if self._is_global_query(user_message, exact_records):
            return self._build_global_health_response(user_message, records)

        chunks = await self.retrieve_context(user_message)
        average_confidence = (
            sum(chunk["relevance_score"] for chunk in chunks) / len(chunks)
            if chunks
            else 0.0
        )
        best_confidence = max(
            (chunk["relevance_score"] for chunk in chunks),
            default=0.0,
        )

        if not chunks or best_confidence < settings.RAG_MIN_CONFIDENCE:
            return {
                "text": NO_KNOWLEDGE,
                "sources": [],
                "avg_confidence": average_confidence,
                "best_confidence": best_confidence,
                "knowledge_gap": True,
                "tokens_used": 0,
                "response_time_ms": 0,
                "mode": "semantic_no_match",
                "structured_data": {
                    "mode": "semantic_no_match",
                    "total_servers": len(records),
                },
            }

        selected_chunks = chunks[: max(1, settings.RAG_MAX_CHUNKS_TO_PROMPT)]
        context_parts: List[str] = []
        remaining = max(1000, settings.RAG_MAX_CONTEXT_CHARS)
        for chunk in selected_chunks:
            block = f"### Documento: {chunk['source']}\n{chunk['content']}"
            if len(block) > remaining:
                block = block[:remaining]
            context_parts.append(block)
            remaining -= len(block)
            if remaining <= 0:
                break

        context = "\n\n---\n\n".join(context_parts)
        result = await gemini_text_service.generate(
            prompt=user_message,
            system_instruction=SERVERS_RAG_SYSTEM.format(
                knowledge_context=context
            ),
            history=history,
            temperature=0.15,
            max_output_tokens=settings.RAG_ANSWER_MAX_OUTPUT_TOKENS,
            model=settings.VERTEX_FAST_MODEL,
        )

        if not result.get("success", True):
            return {
                "text": NO_KNOWLEDGE,
                "tokens_used": result.get("tokens_used") or 0,
                "response_time_ms": result.get("response_time_ms") or 0,
                "sources": list({chunk["source"] for chunk in chunks}),
                "avg_confidence": average_confidence,
                "best_confidence": best_confidence,
                "knowledge_gap": True,
                "llm_error": result.get("error") or result.get("finish_reason"),
                "mode": "semantic_llm_error",
                "structured_data": {
                    "mode": "semantic_llm_error",
                    "total_servers": len(records),
                },
            }

        return {
            "text": _strip_leaked_context_markers(result["text"]),
            "tokens_used": result.get("tokens_used"),
            "response_time_ms": result.get("response_time_ms"),
            "sources": list({chunk["source"] for chunk in chunks}),
            "avg_confidence": average_confidence,
            "best_confidence": best_confidence,
            "knowledge_gap": False,
            "mode": "semantic_rag",
            "structured_data": {
                "mode": "semantic_rag",
                "total_servers": len(records),
            },
        }

    def _chunk_text(self, text: str, chunk_size: int = None) -> List[str]:
        chunk_size = chunk_size or settings.RAG_CHUNK_SIZE_WORDS
        words = text.split()
        return [
            " ".join(words[index:index + chunk_size])
            for index in range(0, len(words), chunk_size)
            if words[index:index + chunk_size]
        ]


servers_kb_service = ServersKnowledgeService()
