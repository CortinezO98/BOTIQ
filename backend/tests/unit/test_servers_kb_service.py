from datetime import datetime, timezone

import pytest

from app.modules.servers_kb.service import ServersKnowledgeService


def _record(
    hostname: str,
    status: str,
    cpu: str = "10%",
    ram: str = "40%",
    disk: str = "50%",
):
    block = (
        f"Servidor (Hostname): {hostname} | "
        "Ultima Actualizacion: 23-07-2026 15:00:00 | "
        "Sistema Operativo: Microsoft Windows Server 2022 Standard | "
        f"CPU (%): {cpu} | "
        "RAM Total (GB): 16 | RAM Usada (GB): 8 | "
        "RAM Disponible (GB): 8 | "
        f"RAM (%): {ram} | "
        "Disco Total (GB): 100 | Disco Usado (GB): 50 | "
        "Disco Disponible (GB): 50 | "
        f"Disco (%): {disk} | "
        f"Estado General: {status} | "
        "Ultimo Reinicio: 4 dias | Notas / Acciones: Validar capacidad."
    )
    record = ServersKnowledgeService._parse_server_block(
        block,
        source="Inventario servidores",
    )
    # Evita que la prueba dependa de la fecha actual para la alerta de frescura.
    record["updated_datetime"] = datetime.now(timezone.utc)
    return record


def test_parse_server_block_preserves_metrics_and_status():
    record = _record("LETO", "Critico", cpu="99%", ram="86%", disk="89%")

    assert record["hostname"] == "LETO"
    assert record["status_key"] == "critical"
    assert record["status_label"] == "Crítico"
    assert record["cpu_value"] == 99
    assert record["ram_value"] == 86
    assert record["disk_value"] == 89


def test_detects_exact_hostname_and_global_health_queries(monkeypatch):
    service = ServersKnowledgeService()
    records = [_record("AGNES", "Advertencia"), _record("LETO", "Critico")]
    monkeypatch.setattr(service, "_get_all_server_records", lambda: records)

    assert service.is_server_health_query("¿Cómo está LETO?") is True
    assert service.is_server_health_query("Dame un resumen de todos los servidores") is True
    assert service.is_server_health_query("¿Cómo configuro una impresora?") is False
    assert service.is_server_health_query("¿Cómo configuro un certificado en un servidor?") is False


@pytest.mark.asyncio
async def test_exact_hostname_response_is_deterministic(monkeypatch):
    service = ServersKnowledgeService()
    records = [_record("LETO", "Critico", cpu="99%", ram="86%", disk="89%")]
    monkeypatch.setattr(service, "_get_all_server_records", lambda: records)

    result = await service.generate_response("¿Cómo está el servidor LETO?")

    assert result["knowledge_gap"] is False
    assert result["mode"] == "exact_hostname"
    assert result["tokens_used"] == 0
    assert "LETO" in result["text"]
    assert "99%" in result["text"]
    assert "Crítico" in result["text"]
    assert result["structured_data"]["matched_servers"] == ["LETO"]


@pytest.mark.asyncio
async def test_global_summary_uses_all_records_not_top_k(monkeypatch):
    service = ServersKnowledgeService()
    records = [
        _record("AGNES", "Advertencia", cpu="74%", ram="68%", disk="76%"),
        _record("LETO", "Critico", cpu="99%", ram="86%", disk="89%"),
        _record("AZR-ETB3", "Inalcanzable", cpu="sin dato", ram="sin dato", disk="sin dato"),
        _record("LIBER", "Saludable", cpu="14%", ram="35%", disk="60%"),
    ]
    monkeypatch.setattr(service, "_get_all_server_records", lambda: records)

    result = await service.generate_response(
        "Dame un resumen general de salud de todos los servidores"
    )

    assert result["knowledge_gap"] is False
    assert result["mode"] == "global_summary"
    assert result["structured_data"]["total_servers"] == 4
    assert result["structured_data"]["counts"]["critical"] == 1
    assert result["structured_data"]["counts"]["unreachable"] == 1
    assert "LETO" in result["text"]
    assert "AZR-ETB3" in result["text"]


@pytest.mark.asyncio
async def test_metric_threshold_query(monkeypatch):
    service = ServersKnowledgeService()
    records = [
        _record("APOLO", "Critico", ram="93%"),
        _record("LETO", "Critico", ram="86%"),
        _record("AGNES", "Advertencia", ram="68%"),
    ]
    monkeypatch.setattr(service, "_get_all_server_records", lambda: records)

    result = await service.generate_response(
        "¿Qué servidores tienen RAM por encima de 90%?"
    )

    assert result["mode"] == "ram_threshold"
    assert result["structured_data"]["threshold"] == 90
    assert result["structured_data"]["matched_servers"] == ["APOLO"]
    assert "APOLO" in result["text"]
    assert "LETO" not in result["text"]


@pytest.mark.asyncio
async def test_unknown_explicit_hostname_does_not_return_another_server(monkeypatch):
    service = ServersKnowledgeService()
    monkeypatch.setattr(
        service,
        "_get_all_server_records",
        lambda: [_record("AGNES", "Advertencia")],
    )

    result = await service.generate_response("¿Cómo está el servidor ZEUS-99?")

    assert result["knowledge_gap"] is True
    assert result["mode"] == "hostname_not_found"
    assert "ZEUS-99" in result["text"]
    assert "AGNES" not in result["text"]
