import importlib.util
from pathlib import Path

import pytest
from recon.config import REPO_ROOT


@pytest.fixture(scope="session")
def fixtures(tmp_path_factory: pytest.TempPathFactory) -> Path:
    script = REPO_ROOT / "scripts/build_fixtures.py"
    spec = importlib.util.spec_from_file_location("fixture_builder", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    output = tmp_path_factory.mktemp("compiled-fixtures")
    module.build(output)
    return output
