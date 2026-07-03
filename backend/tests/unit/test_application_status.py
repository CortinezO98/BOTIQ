"""
Pruebas de regresión para application_status_service.

Bug principal: _demo_lookup usaba el mensaje completo del usuario como
"nombre de servicio" cuando no había URL ni IP, produciendo respuestas
tipo "Validé el estado de <pregunta de 60 palabras> y aparece operativo".
"""
import pytest
from app.services.application_status_service import ApplicationStatusService


@pytest.fixture
def service():
    return ApplicationStatusService()


# ── Bug: pregunta larga no debe usarse como nombre de servicio ────────────────

class TestDemoLookupNoLongMessage:
    """
    Bug real: el usuario enviaba una pregunta larga de diagnóstico de Windows 7,
    el bot respondía "Validé el estado de Un usuario reporta que su computadora..."
    """

    def test_long_query_without_url_ip_returns_not_found(self, service):
        long_question = (
            "Un usuario reporta que su computadora con Windows 7 presenta una "
            "lentitud extrema y en ocasiones sufre de apagados repentinos. "
            "Al revisar el administrador de tareas, notas que el rendimiento "
            "está al límite. ¿Cuál es el procedimiento para diagnosticar esto?"
        )
        result = service._demo_lookup(url=None, ip=None, query=long_question)
        assert not result.get("found"), (
            "Una pregunta larga sin URL/IP no debe encontrar ningún 'servicio'. "
            "Antes retornaba found=True con el mensaje completo como service_name."
        )
        assert result.get("status") == "unknown"

    def test_long_query_result_does_not_contain_question_text(self, service):
        question = "pregunta muy larga sobre un tema que no es un servicio específico " * 3
        result = service._demo_lookup(url=None, ip=None, query=question)
        service_name = result.get("service_name", "")
        assert question not in (service_name or ""), (
            "El mensaje completo del usuario no debe aparecer como service_name"
        )

    def test_url_lookup_returns_found(self, service):
        """Una URL real sí debe consultarse y retornar found=True en modo demo."""
        result = service._demo_lookup(url="https://portal.iq-online.com", ip=None, query=None)
        assert result.get("found")
        assert result.get("service_name") == "https://portal.iq-online.com"

    def test_ip_lookup_returns_found(self, service):
        result = service._demo_lookup(url=None, ip="192.168.1.50", query=None)
        assert result.get("found")
        assert result.get("service_name") == "192.168.1.50"

    def test_short_app_name_as_query_returns_found(self, service):
        """Un nombre corto de aplicativo (≤40 chars) sí puede usarse como target."""
        result = service._demo_lookup(url=None, ip=None, query="Portal RRHH")
        assert result.get("found")
        assert result.get("service_name") == "Portal RRHH"

    def test_no_url_no_ip_no_query_returns_unknown(self, service):
        result = service._demo_lookup(url=None, ip=None, query=None)
        assert not result.get("found")
        assert result.get("status") == "unknown"

    def test_threshold_boundary_exactly_40_chars(self, service):
        """Exactamente 40 chars debe ser aceptado como nombre de servicio."""
        name = "a" * 40
        result = service._demo_lookup(url=None, ip=None, query=name)
        assert result.get("found")

    def test_threshold_boundary_41_chars_rejected(self, service):
        """41 chars ya es demasiado largo para ser un nombre de servicio válido."""
        name = "a" * 41
        result = service._demo_lookup(url=None, ip=None, query=name)
        assert not result.get("found")