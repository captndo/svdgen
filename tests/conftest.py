from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def minimal_svd() -> Path:
    return FIXTURES_DIR / "minimal.svd"


@pytest.fixture
def invalid_access_svd() -> Path:
    return FIXTURES_DIR / "invalid_access.svd"


@pytest.fixture
def malformed_svd() -> Path:
    return FIXTURES_DIR / "malformed.svd"
