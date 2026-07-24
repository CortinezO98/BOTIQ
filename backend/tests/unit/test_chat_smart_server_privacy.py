from app.api.v1.routes.chat_smart import _build_employee_server_response


def test_employee_critical_response_hides_internal_metrics():
    result = {
        "mode": "exact_hostname",
        "knowledge_gap": False,
        "text": "APOLO CPU 1%, RAM 93%, disco 84%, Windows Server 2016",
        "structured_data": {
            "mode": "exact_hostname",
            "matched_servers": ["APOLO"],
            "servers": [
                {
                    "hostname": "APOLO",
                    "status_key": "critical",
                    "status_label": "Crítico",
                }
            ],
            "freshness": {"stale": False},
        },
    }

    response = _build_employee_server_response(result)

    assert response["health"] == "critical"
    assert response["requires_support"] is True
    assert "APOLO" in response["text"]
    assert "condición crítica" in response["text"]
    assert "CPU" not in response["text"]
    assert "RAM" not in response["text"]
    assert "disco" not in response["text"].lower()
    assert "Windows" not in response["text"]


def test_employee_healthy_response_is_basic():
    result = {
        "mode": "exact_hostname",
        "knowledge_gap": False,
        "structured_data": {
            "servers": [
                {
                    "hostname": "AZR-CONT-WEB",
                    "status_key": "healthy",
                    "status_label": "Saludable",
                }
            ],
            "freshness": {"stale": False},
        },
    }

    response = _build_employee_server_response(result)

    assert response["health"] == "healthy"
    assert response["requires_support"] is False
    assert "operativo" in response["text"]
    assert "porcentaje" not in response["text"].lower()


def test_employee_global_response_hides_counts_and_server_names():
    result = {
        "mode": "global_summary",
        "knowledge_gap": False,
        "structured_data": {
            "counts": {
                "healthy": 10,
                "warning": 26,
                "critical": 6,
                "unreachable": 7,
            },
            "alerts": {"cpu": 3, "ram": 5, "disk": 3},
            "matched_servers": ["LETO", "APOLO", "FREY"],
            "freshness": {"stale": False},
        },
    }

    response = _build_employee_server_response(result)

    assert response["health"] == "attention_required"
    assert response["requires_support"] is True
    assert "alertas" in response["text"]
    assert "LETO" not in response["text"]
    assert "APOLO" not in response["text"]
    assert "6" not in response["text"]
    assert "7" not in response["text"]


def test_employee_unreachable_response_is_safe():
    result = {
        "mode": "exact_hostname",
        "knowledge_gap": False,
        "structured_data": {
            "servers": [
                {
                    "hostname": "AZR-ETB3",
                    "status_key": "unreachable",
                    "status_label": "Inalcanzable",
                }
            ],
            "freshness": {"stale": False},
        },
    }

    response = _build_employee_server_response(result)

    assert response["health"] == "unreachable"
    assert response["requires_support"] is True
    assert "inalcanzable" in response["text"]
    assert "causa" not in response["text"].lower()
