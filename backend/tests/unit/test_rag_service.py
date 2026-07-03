"""
Pruebas de regresión para support_rag_service.

Bug principal: _build_retrieval_query no enriquecía mensajes cortos de
seguimiento con el contexto anterior, causando que ChromaDB no encontrara
los chunks relevantes y el bot respondiera "no encontré información".
"""
import pytest
from app.modules.support_rag.service import (
    _build_retrieval_query,
    _has_meaningful_overlap,
    _strip_leaked_context_markers,
    SupportRAGService,
)


# ── Tests de _build_retrieval_query ───────────────────────────────────────────

class TestBuildRetrievalQuery:
    """
    Bug: mensajes de seguimiento cortos usaban solo el mensaje actual
    para buscar en ChromaDB. Sin términos técnicos propios, la búsqueda
    no encontraba nada y el bot fallaba silenciosamente.
    """

    def test_short_followup_prepends_previous_user_message(self):
        history = [
            {"role": "user", "content": "Tengo un equipo con Windows 7 que presenta lentitud"},
            {"role": "model", "content": "Para Windows 7 con lentitud, verifica la RAM..."},
        ]
        query = _build_retrieval_query("DAME EL PASO A PASO", history)
        assert "Windows 7" in query or "lentitud" in query, (
            "La query enriquecida debe incluir contexto del mensaje anterior"
        )
        assert "DAME EL PASO A PASO" in query

    def test_long_message_uses_itself_directly(self):
        """Mensajes largos con contenido técnico propio no necesitan enriquecimiento."""
        history = [{"role": "user", "content": "contexto anterior"}]
        long_msg = ("Tengo un error 500 al intentar acceder al portal de ventas "
                    "desde Firefox. El error ocurre solo a usuarios del área comercial.")
        query = _build_retrieval_query(long_msg, history)
        assert query == long_msg, (
            "Mensajes largos (>60 chars) deben usarse tal cual, sin prepend"
        )

    def test_no_history_uses_message_directly(self):
        query = _build_retrieval_query("GUIAME", None)
        assert query == "GUIAME"

    def test_empty_history_uses_message_directly(self):
        query = _build_retrieval_query("continúa", [])
        assert query == "continúa"

    @pytest.mark.parametrize("followup", [
        "GUIAME",
        "no funcionó",
        "sigue",
        "y ahora?",
        "continúa",
        "dame más",
        "ok",
    ])
    def test_common_followups_are_enriched(self, followup):
        history = [
            {"role": "user", "content": "el portal de Aranda no deja crear tickets"},
            {"role": "model", "content": "Validé el estado del portal..."},
        ]
        query = _build_retrieval_query(followup, history)
        assert len(query) > len(followup), (
            f"'{followup}' (seguimiento corto) debe enriquecerse con contexto anterior"
        )

    def test_previous_context_capped_at_300_chars(self):
        """El contexto anterior no debe inflar demasiado el prompt de ChromaDB."""
        history = [
            {"role": "user", "content": "x" * 500},
        ]
        query = _build_retrieval_query("GUIAME", history)
        # La parte del contexto anterior debe ser máx 300 chars
        context_part = query.replace("GUIAME", "")
        assert len(context_part) <= 301, (
            "El contexto anterior inyectado debe estar limitado a 300 chars"
        )


# ── Tests de _has_meaningful_overlap ─────────────────────────────────────────

class TestHasMeaningfulOverlap:
    """
    El filtro de relevancia evita que Gemini genere respuestas con chunks
    no relacionados. Pero no debe bloquear cuando el overlap es real.
    """

    def test_empty_chunks_returns_false(self):
        assert not _has_meaningful_overlap("Windows 7 lentitud", [])

    def test_matching_terms_returns_true(self):
        chunks = [{"source": "Anexo19.xlsx", "content": "Windows 7 requiere mínimo 2GB RAM"}]
        assert _has_meaningful_overlap("Windows 7 RAM", chunks)

    def test_unrelated_chunks_returns_false(self):
        chunks = [{"source": "Manual.pdf", "content": "procedimiento de canje bancolombia"}]
        assert not _has_meaningful_overlap("impresora driver Windows", chunks)

    def test_empty_query_returns_true(self):
        """Query vacía no debe bloquear — no hay términos que verificar."""
        chunks = [{"source": "doc.pdf", "content": "contenido cualquiera"}]
        assert _has_meaningful_overlap("", chunks)


# ── Tests de _strip_leaked_context_markers ────────────────────────────────────

class TestStripLeakedContextMarkers:
    """
    Bug: Gemini reproducía las etiquetas internas del prompt ([Fuente: ...])
    en la respuesta al usuario. El sanitizador debe limpiarlas.
    """

    def test_strips_fuente_brackets(self):
        text = "Según [Fuente: Anexo 19.xlsx] debes verificar la RAM."
        clean = _strip_leaked_context_markers(text)
        assert "[Fuente:" not in clean
        assert "Anexo 19.xlsx" not in clean or "Fuente" not in clean

    def test_strips_documento_header(self):
        text = "### Documento: Manual Usuario.pdf\nEl procedimiento es..."
        clean = _strip_leaked_context_markers(text)
        assert "### Documento:" not in clean
        assert "El procedimiento es..." in clean

    def test_preserves_normal_content(self):
        text = "Para resolver el problema, reinicia el equipo y verifica la RAM."
        assert _strip_leaked_context_markers(text) == text

    def test_handles_empty_string(self):
        assert _strip_leaked_context_markers("") == ""

    def test_handles_none(self):
        assert _strip_leaked_context_markers(None) == None  # noqa


# ── Tests de _chunk_text ──────────────────────────────────────────────────────

class TestChunkText:
    """Tests ya existentes preservados como regresión."""

    def test_chunk_splits_correctly(self):
        service = SupportRAGService()
        texto = " ".join([f"p{i}" for i in range(1200)])
        chunks = service._chunk_text(texto, 500)
        assert len(chunks) == 3
        assert len(chunks[0].split()) == 500

    def test_chunk_empty_returns_empty_list(self):
        assert SupportRAGService()._chunk_text("") == []

    def test_chunk_smaller_than_size(self):
        service = SupportRAGService()
        chunks = service._chunk_text("hola mundo test", 500)
        assert len(chunks) == 1