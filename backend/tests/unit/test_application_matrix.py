"""
Pruebas de regresión para application_matrix_service.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def _mock_row(app_name="SAP", portal_name=None, server_name=None,
              url_pattern=None, ip_address=None):
    row = MagicMock()
    row.app_name = app_name
    row.portal_name = portal_name
    row.server_name = server_name
    row.url_pattern = url_pattern
    row.ip_address = ip_address
    row.environment = "prod"
    row.criticality = "high"
    row.owner_area = "TI"
    row.support_group = "N2"
    row.status_source = None
    row.notes = None
    row.is_active = True
    return row


class TestTermMatches:
    def setup_method(self):
        from app.services.application_matrix_service import ApplicationMatrixService
        self.service = ApplicationMatrixService()

    def test_short_candidate_below_min_length_returns_false(self):
        assert not self.service._term_matches("ip", "portal de administración ip")
        assert not self.service._term_matches("so", "sistema operativo Windows")

    def test_word_boundary_match(self):
        assert self.service._term_matches("sistema", "El sistema de ventas está caído")

    def test_no_substring_false_positive(self):
        # _term_matches usa _MIN_CANDIDATE_LENGTH=4, así que nombres de 3 chars
        # como "sap" quedan excluidos deliberadamente para evitar falsos positivos.
        # En producción, "SAP" se identifica por URL o IP, no por nombre de texto.

        # "sapo" NO debe matchear como "sap" (substring dentro de otra palabra)
        assert not self.service._term_matches("sapo", "el proceso desaparecido del servidor")
        # "portal" SÍ debe matchear como palabra completa (4+ chars)
        assert self.service._term_matches("portal", "el portal de ventas no responde")
        # "excel" SÍ debe matchear como palabra completa
        assert self.service._term_matches("excel", "no puedo abrir excel en mi equipo")
        # "excel" NO debe matchear dentro de "excelente"
        assert not self.service._term_matches("excel", "es un resultado excelente")

    def test_none_candidate_returns_false(self):
        assert not self.service._term_matches(None, "cualquier texto")

    def test_empty_candidate_returns_false(self):
        assert not self.service._term_matches("", "cualquier texto")


class TestMatchThreshold:
    def setup_method(self):
        from app.services.application_matrix_service import _MIN_MATCH_SCORE
        self.min_score = _MIN_MATCH_SCORE

    def test_min_match_score_is_at_least_80(self):
        assert self.min_score >= 80, (
            f"_MIN_MATCH_SCORE={self.min_score} es demasiado bajo. "
            "Con 50, una sola coincidencia débil producía falsos positivos."
        )


class TestLongMessageNoFalsePositive:
    """
    Bug real: la pregunta del screenshot causaba found=True por coincidencias
    de 'sistema' y 'tareas' dentro del mensaje largo.
    La firma real de lookup es: lookup(self, db, url=None, ip=None, query=None)
    """

    @pytest.mark.asyncio
    async def test_windows7_diagnostic_question_returns_not_found(self):
        from app.services.application_matrix_service import ApplicationMatrixService
        service = ApplicationMatrixService()

        question = (
            "Un usuario reporta que su computadora con Windows 7 presenta una lentitud "
            "extrema. Al revisar el administrador de tareas, el rendimiento está al límite. "
            "¿Cuál de las siguientes acciones NO corresponde a un diagnóstico del Sistema?"
        )

        fake_rows = [
            _mock_row("Sistema ERP"),
            _mock_row("Tareas Pendientes"),
            _mock_row("SAP"),
        ]

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = fake_rows

        with patch.object(mock_db, 'execute', new=AsyncMock(return_value=mock_result)):
            # Firma correcta: lookup(db, query=...)
            result = await service.lookup(mock_db, query=question)

        assert not result.get("found"), (
            "Una pregunta de procedimiento no debe identificar ningún aplicativo. "
            "Este era el bug que causaba 'Validé el estado de <pregunta completa>'"
        )

    @pytest.mark.asyncio
    async def test_url_in_message_returns_found(self):
        from app.services.application_matrix_service import ApplicationMatrixService
        service = ApplicationMatrixService()

        fake_rows = [
            _mock_row("Portal Ventas", "portal.ventas.iq-online.com", None, "portal.ventas.iq-online.com", None),
        ]

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = fake_rows

        with patch.object(mock_db, 'execute', new=AsyncMock(return_value=mock_result)):
            # Firma correcta: lookup(db, url=...)
            result = await service.lookup(mock_db, url="portal.ventas.iq-online.com")

        assert result.get("found"), (
            "Una URL exacta que coincide con la matriz debe encontrar el aplicativo"
        )