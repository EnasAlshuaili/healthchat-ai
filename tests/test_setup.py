"""Environment and project-structure checks (step 1 of the roadmap)."""

import hashlib
import subprocess
import sys

import pytest

from querymate import config


def test_python_version_is_312():
    assert sys.version_info[:2] == (3, 12)


def test_core_dependencies_import():
    import numpy, pandas, sklearn, streamlit  # noqa: F401


def test_chat_storage_disabled_by_default():
    assert config.STORE_CHATS is False


@pytest.mark.skipif(not config.RAW_DATA_PATH.exists(), reason="raw dataset not present")
def test_raw_dataset_unchanged():
    h = hashlib.sha256()
    with open(config.RAW_DATA_PATH, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    assert h.hexdigest() == config.RAW_DATA_SHA256


@pytest.mark.skipif(not config.RAW_DATA_PATH.exists(), reason="raw dataset not present")
def test_raw_dataset_is_gitignored():
    result = subprocess.run(
        ["git", "check-ignore", "-q", str(config.RAW_DATA_PATH)],
        cwd=config.PROJECT_ROOT,
    )
    assert result.returncode == 0
