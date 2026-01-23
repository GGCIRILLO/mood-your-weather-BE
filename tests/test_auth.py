"""
Tests per autenticazione (esempio)
Per eseguire: pytest tests/ -v
"""
import pytest
from fastapi.testclient import TestClient
from main import app


client = TestClient(app)


def test_root_endpoint():
    """Test root endpoint"""
    response = client.get("/")
    assert response.status_code == 200
    assert "name" in response.json()
    assert response.json()["name"] == "Mood Your Weather API"


def test_health_check():
    """Test health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_weather_missing_params():
    """Test weather endpoint senza parametri"""
    response = client.get("/weather/current")
    assert response.status_code == 422  # Validation error


# TODO: Aggiungere test con mock Firebase e OpenWeatherMap
# def test_register_user():
#     """Test registrazione utente"""
#     response = client.post(
#         "/auth/register",
#         json={
#             "email": "test@example.com",
#             "password": "test123456"
#         }
#     )
#     assert response.status_code == 201


# def test_create_mood_without_auth():
#     """Test creazione mood senza autenticazione"""
#     response = client.post(
#         "/moods",
#         json={
#             "userId": "test",
#             "emojis": ["sunny"],
#             "intensity": 75
#         }
#     )
#     assert response.status_code == 401


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
