# tests/test_diagnostics.py

import pytest
from httpx import AsyncClient
from backend.main import app

@pytest.mark.asyncio
async def test_admin_status_details():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/api/admin/status/details")
        assert response.status_code == 200
        data = response.json()

        assert "status" in data
        assert "components" in data
        assert data["status"] in ["ok", "degraded", "error"]

        # Composants critiques
        for key in ["llm", "tts", "stt", "hue", "memory_vector", "memory_symbolic"]:
            assert key in data["components"]

        # Vérifie que les statuts sont présents
        for comp, result in data["components"].items():
            assert "status" in result

        # Vérifie le système
        system = data["components"].get("system", {})
        assert "cpu" in system
        assert "memory_percent" in system
        assert "disk_percent" in system

        print("\n\n[SUCCESS] Diagnostic complet OK\n")
