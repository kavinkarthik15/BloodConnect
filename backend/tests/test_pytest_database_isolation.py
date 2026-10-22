from pathlib import Path

from app.core.config import settings
from app.db.database import engine


def test_pytest_database_is_outside_repository():
    database_path = Path(engine.url.database).resolve()
    repository_root = Path(__file__).resolve().parents[2]

    assert settings.app_env == "test"
    assert database_path.name == "pytest.db"
    assert repository_root not in database_path.parents
    assert database_path.exists()
