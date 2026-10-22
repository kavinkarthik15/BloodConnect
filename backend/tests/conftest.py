import os
import sys
import tempfile
from pathlib import Path


_TEST_DATABASE_DIRECTORY = tempfile.TemporaryDirectory(prefix="nss-bloodconnect-pytest-")
_TEST_DATABASE_PATH = Path(_TEST_DATABASE_DIRECTORY.name) / "pytest.db"

os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DATABASE_PATH.as_posix()}"


def pytest_unconfigure(config):
    database_module = sys.modules.get("app.db.database")
    if database_module is not None:
        database_module.engine.dispose()
    _TEST_DATABASE_DIRECTORY.cleanup()
