import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import Settings, get_settings
from app.main import app

TEST_KEY = "fictional-test-key-not-a-secret-123456"


@pytest.mark.parametrize("key", [None, "short"])
def test_production_rejects_missing_or_short_key(key: str | None) -> None:
    with pytest.raises(ValidationError, match="Production requires"):
        Settings(_env_file=None, app_env="production", api_key=key)


def test_config_does_not_display_key() -> None:
    settings = Settings(_env_file=None, app_env="production", api_key=TEST_KEY)
    assert TEST_KEY not in repr(settings)


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/v1/documents"),
        ("GET", "/v1/jobs/not-a-uuid"),
        ("POST", "/v1/jobs/not-a-uuid/retry"),
    ],
)
def test_operations_require_key_before_processing(method: str, path: str) -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None, app_env="production", api_key=TEST_KEY
    )
    try:
        with TestClient(app) as client:
            assert client.request(method, path).status_code == 401
            assert client.request(method, path, headers={"X-API-Key": "wrong"}).status_code == 401
            # Valid authentication reaches normal request validation, without a database call.
            assert client.request(method, path, headers={"X-API-Key": TEST_KEY}).status_code == 422
            assert client.get("/health").status_code == 200
            assert client.get("/docs").status_code == 200
            schema = client.get("/openapi.json").json()
            assert TEST_KEY not in str(schema)
            assert schema["paths"][path.replace("not-a-uuid", "{job_id}")][method.lower()][
                "security"
            ]
    finally:
        app.dependency_overrides.clear()
