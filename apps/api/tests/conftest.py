from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from unihub_insight_api.config import Settings
from unihub_insight_api.main import create_app


@pytest.fixture
def client() -> Iterator[TestClient]:
    settings = Settings(
        environment="test",
        data_mode="demo",
        allowed_origins="http://localhost:3100",
    )
    with TestClient(create_app(settings)) as test_client:
        yield test_client
