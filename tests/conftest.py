import sys
import os
import pytest

# Ensure src is importable without installation
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture
def app_id():
    return "io.github.ymontenegr.Codex"


@pytest.fixture
def tmp_library(tmp_path):
    """Temporary directory simulating a Codex library root."""
    (tmp_path / "books").mkdir()
    return tmp_path
